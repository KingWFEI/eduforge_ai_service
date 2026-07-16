import unittest
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.course import Course
from app.models.course_structure import CourseChapter
from app.models.tutor import TutorMessage, TutorSession
from app.services.tutor_service import TutorService
from app.utils.response import AppException


class FakeLLM:
    def __init__(self, chunks=None):
        self.chunks = chunks or ["核心", "答案"]
        self.messages = None

    async def chat_stream(self, messages):
        self.messages = messages
        for chunk in self.chunks:
            yield chunk


class FakeRetrieval:
    def __init__(self):
        self.calls = []

    async def search(self, **kwargs):
        self.calls.append(kwargs)
        return [{"section": "第一节", "content": "课程知识"}]

    @staticmethod
    def format_context(chunks):
        return "课程知识"


class TutorServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Course.__table__.create(self.engine)
        CourseChapter.__table__.create(self.engine)
        TutorSession.__table__.create(self.engine)
        TutorMessage.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    async def test_enter_reuses_active_session_and_close_allows_new_one(self):
        service = TutorService(self.db, llm=FakeLLM(), retrieval=FakeRetrieval())

        first = await service.enter_session(7, None, None)
        second = await service.enter_session(7, None, None)

        self.assertTrue(first["is_new"])
        self.assertFalse(second["is_new"])
        self.assertEqual(first["session_id"], second["session_id"])

        await service.close_session(first["session_id"])
        third = await service.enter_session(7, None, None)
        self.assertTrue(third["is_new"])
        self.assertNotEqual(first["session_id"], third["session_id"])

    async def test_general_and_tutoring_entries_do_not_reuse_each_other(self):
        self.db.add(Course(course_id="course-1", name="算法"))
        self.db.add(
            CourseChapter(
                id="section-1",
                course_id="course-1",
                title="递归",
                level=2,
            )
        )
        self.db.commit()
        service = TutorService(self.db, llm=FakeLLM(), retrieval=FakeRetrieval())

        general = await service.enter_session(7, None, None)
        tutoring = await service.enter_session(7, "course-1", "section-1")
        general_again = await service.enter_session(7, None, None)

        self.assertNotEqual(general["session_id"], tutoring["session_id"])
        self.assertEqual(general["session_id"], general_again["session_id"])
        self.assertEqual(general["session_type"], "general")
        self.assertEqual(tutoring["session_type"], "tutoring")

    async def test_stream_persists_messages_title_and_done_event(self):
        llm = FakeLLM(["你好", "！"])
        service = TutorService(self.db, llm=llm, retrieval=FakeRetrieval())
        entered = await service.enter_session(7, None, None)

        events = [
            event
            async for event in service.process_message(
                entered["session_id"], 7, "请解释递归"
            )
        ]

        self.assertIn("event: delta", events[0])
        done_payload = json.loads(events[-1].split("data: ", 1)[1])
        self.assertEqual(done_payload["code"], 0)
        self.assertEqual(done_payload["message"], "success")
        self.assertEqual(done_payload["data"]["answer"], "你好！")
        messages = await service.get_messages(entered["session_id"])
        self.assertEqual(
            [(item.role, item.content) for item in messages],
            [("user", "请解释递归"), ("assistant", "你好！")],
        )
        session = self.db.get(TutorSession, entered["session_id"])
        self.assertEqual(session.title, "请解释递归")
        self.assertEqual(llm.messages[-1], {"role": "user", "content": "请解释递归"})

    async def test_simple_greeting_returns_short_answer_without_calling_llm(self):
        llm = FakeLLM(["不应调用"])
        service = TutorService(self.db, llm=llm, retrieval=FakeRetrieval())
        entered = await service.enter_session(7, None, None)

        events = [
            event
            async for event in service.process_message(
                entered["session_id"], 7, "你好"
            )
        ]

        done_payload = json.loads(events[-1].split("data: ", 1)[1])
        answer = done_payload["data"]["answer"]
        self.assertEqual(
            answer,
            "你好！我是 EduForge AI 学习助手。有什么学习问题需要我帮你吗？",
        )
        self.assertNotIn("循环", answer)
        self.assertNotIn("核心答案", answer)
        self.assertIsNone(llm.messages)

    def test_general_prompt_does_not_force_template_for_casual_messages(self):
        prompt = TutorService._build_system_prompt(False, "", None)
        self.assertIn("不要机械使用", prompt)
        self.assertIn("一到两句话", prompt)

    async def test_tutoring_session_injects_retrieved_and_selected_context(self):
        self.db.add(Course(course_id="course-1", name="算法"))
        self.db.add(
            CourseChapter(
                id="section-1",
                course_id="course-1",
                title="递归",
                level=2,
            )
        )
        self.db.commit()
        llm = FakeLLM()
        retrieval = FakeRetrieval()
        service = TutorService(self.db, llm=llm, retrieval=retrieval)
        entered = await service.enter_session(7, "course-1", "section-1")

        events = [
            event
            async for event in service.process_message(
                entered["session_id"],
                7,
                "递归是什么？",
                course_id="course-1",
                section_id="section-1",
                context="函数调用自身",
            )
        ]

        self.assertIn("event: done", events[-1])
        self.assertEqual(retrieval.calls[0]["section_id"], "section-1")
        system_prompt = llm.messages[0]["content"]
        self.assertIn("课程知识", system_prompt)
        self.assertIn("函数调用自身", system_prompt)

    async def test_ownership_is_enforced(self):
        service = TutorService(self.db, llm=FakeLLM(), retrieval=FakeRetrieval())
        entered = await service.enter_session(7, None, None)

        with self.assertRaises(AppException) as caught:
            await service.verify_ownership(entered["session_id"], 8)

        self.assertEqual(caught.exception.status_code, 403)

    async def test_course_and_section_must_be_provided_together(self):
        service = TutorService(self.db, llm=FakeLLM(), retrieval=FakeRetrieval())
        with self.assertRaises(AppException) as caught:
            await service.enter_session(7, "course-1", None)
        self.assertEqual(caught.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
