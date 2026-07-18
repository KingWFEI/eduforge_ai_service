import json
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.profile_dialogue_messages import ProfileDialogueMessage
from app.models.profile_dialogue_sessions import ProfileDialogueSession
from app.services.profile_dialogue_orchestrator import ProfileDialogueOrchestrator


class FakeLLM:
    def __init__(
        self,
        slot_updates=None,
        reply="了解。平时学习会提前做计划吗？",
        safe_reply=None,
        text_error=None,
    ):
        self.slot_updates = slot_updates or {}
        self.reply = reply
        self.safe_reply = safe_reply
        self.text_error = text_error
        self.extraction_calls = 0

    async def generate_json(self, prompt, **kwargs):
        if "相关性判断智能体" in prompt:
            return {"is_relevant": True, "relevance_score": 1.0}
        if "全局学习画像字段抽取智能体" in prompt:
            self.extraction_calls += 1
            return {
                "slot_updates": self.slot_updates,
                "current_slot_relevant": True,
                "has_any_useful_information": bool(self.slot_updates),
                "confidence": 1.0,
            }
        if "学习画像类型判断智能体" in prompt:
            return {
                "profile_type": "balanced_grower",
                "profile_type_name": "综合成长者",
                "summary": "画像摘要",
                "tags": ["稳定"],
                "reason": "信息完整",
                "confidence": 0.9,
            }
        if "安全审核智能体" in prompt:
            if self.safe_reply is not None:
                return {"passed": False, "safe_reply": self.safe_reply, "issues": ["test"]}
            return {"passed": True, "safe_reply": "", "issues": []}
        raise AssertionError(prompt)

    async def generate_text(self, **kwargs):
        if self.text_error is not None:
            raise self.text_error
        return self.reply


class FakeRequest:
    def __init__(self, disconnect_on_call=None):
        self.calls = 0
        self.disconnect_on_call = disconnect_on_call

    async def is_disconnected(self):
        self.calls += 1
        return self.disconnect_on_call == self.calls


class ProfileDialogueOrchestratorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        ProfileDialogueSession.__table__.create(self.engine)
        ProfileDialogueMessage.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def create_session(self):
        session = ProfileDialogueSession(
            student_id=7,
            scene="initial_profile",
            status="collecting",
            current_slot="learning_style",
            collected_slots_json=[],
            missing_slots_json=[
                "learning_style",
                "learning_habits",
                "motivation",
                "strengths_challenges",
                "pace_and_time",
            ],
            extracted_fields_json={},
            dialogue_state={},
            progress=0.0,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def test_profile_preview_filters_nested_llm_output(self):
        preview = ProfileDialogueOrchestrator._normalize_profile_preview(
            {
                "profile_type": "balanced",
                "profile_type_name": {"nested": "bad"},
                "summary": "稳定学习",
                "tags": ["自律", {"nested": "bad"}, ["bad"], "自律"],
                "reason": "信息完整",
                "confidence": 2.5,
                "unexpected": {"must": "not pass"},
            }
        )

        self.assertEqual(preview["profile_type"], "balanced")
        self.assertEqual(preview["profile_type_name"], "")
        self.assertEqual(preview["tags"], ["自律"])
        self.assertEqual(preview["confidence"], 1.0)
        self.assertNotIn("unexpected", preview)

    async def test_one_message_updates_multiple_slots_and_advances(self):
        session = self.create_session()
        llm = FakeLLM(
            slot_updates={
                "learning_style": {"preferred_content_formats": ["视频", "案例"]},
                "motivation": {"primary_learning_goal": "准备考试"},
                "pace_and_time": {
                    "preferred_learning_period": "晚上",
                    "session_duration": 60,
                },
            }
        )
        orchestrator = ProfileDialogueOrchestrator(self.db, llm)

        result = await orchestrator.handle_user_message(
            session.id,
            7,
            "我喜欢视频和案例，晚上学一小时，主要为了考试。",
            client_message_id="message-1",
        )

        self.assertEqual(result["current_slot"], "learning_habits")
        self.assertEqual(result["extracted_fields"]["motivation"]["primary_learning_goal"], "准备考试")
        self.assertEqual(result["extracted_fields"]["pace_and_time"]["session_duration"], 60)
        self.assertEqual(result["dialogue_action"]["question_field"], "planning_habit")
        self.assertEqual(result["display"]["current_slot"], "学习习惯")
        self.assertIn("学习习惯", result["display"]["missing_slots"])

    async def test_duplicate_client_message_id_replays_without_agents(self):
        session = self.create_session()
        llm = FakeLLM(
            slot_updates={
                "learning_style": {"preferred_content_formats": ["图解"]}
            }
        )
        orchestrator = ProfileDialogueOrchestrator(self.db, llm)

        first = await orchestrator.handle_user_message(
            session.id, 7, "我喜欢图解。", client_message_id="same-id"
        )
        second = await orchestrator.handle_user_message(
            session.id, 7, "我喜欢图解。", client_message_id="same-id"
        )

        self.assertFalse(first["idempotent_replay"])
        self.assertTrue(second["idempotent_replay"])
        self.assertEqual(llm.extraction_calls, 1)
        self.assertEqual(
            self.db.query(ProfileDialogueMessage).filter_by(role="user").count(), 1
        )
        self.assertEqual(
            self.db.query(ProfileDialogueMessage).filter_by(role="assistant").count(), 1
        )

    async def test_state_is_persisted_before_stream_disconnect(self):
        session = self.create_session()
        llm = FakeLLM(
            slot_updates={
                "learning_style": {"preferred_content_formats": ["图解"]}
            }
        )
        orchestrator = ProfileDialogueOrchestrator(self.db, llm)
        events = [
            event
            async for event in orchestrator.stream_user_message(
                request=FakeRequest(disconnect_on_call=2),
                session_id=session.id,
                student_id=7,
                user_message="我喜欢图解。",
                client_message_id="disconnect-id",
            )
        ]

        self.assertTrue(any("state_update" in event for event in events))
        self.db.refresh(session)
        self.assertEqual(session.current_slot, "learning_habits")
        self.assertEqual(
            session.extracted_fields_json["learning_style"]["preferred_content_formats"],
            ["图解"],
        )
        assistant = self.db.query(ProfileDialogueMessage).filter_by(role="assistant").one()
        self.assertEqual(assistant.stream_status, "interrupted")

    async def test_safety_reply_is_saved_and_sent_instead_of_raw_reply(self):
        session = self.create_session()
        llm = FakeLLM(
            slot_updates={
                "learning_style": {"preferred_content_formats": ["图解"]}
            },
            reply="不合适的原始回复",
            safe_reply="了解，已记录你的学习偏好。平时学习会提前做计划吗？",
        )
        orchestrator = ProfileDialogueOrchestrator(self.db, llm)
        events = [
            event
            async for event in orchestrator.stream_user_message(
                request=FakeRequest(),
                session_id=session.id,
                student_id=7,
                user_message="我喜欢图解。",
                client_message_id="safe-id",
            )
        ]
        delta_text = "".join(
            json.loads(event.split("data: ", 1)[1])["content"]
            for event in events
            if event.startswith("event: delta")
        )
        assistant = self.db.query(ProfileDialogueMessage).filter_by(role="assistant").one()

        self.assertEqual(
            delta_text,
            "了解，已记录你的学习偏好。平时学习会提前做计划吗？",
        )
        self.assertEqual(assistant.content, delta_text)
        self.assertNotIn("不合适的原始回复", delta_text)

        state_event = next(event for event in events if event.startswith("event: state_update"))
        done_event = next(event for event in events if event.startswith("event: done"))
        state_data = json.loads(state_event.split("data: ", 1)[1])
        done_data = json.loads(done_event.split("data: ", 1)[1])
        for data in (state_data, done_data):
            self.assertIn("display", data)
            self.assertEqual(data["display"]["current_slot"], "学习习惯")
            self.assertIn("fields", data["display"])

    async def test_empty_llm_reply_error_streams_fallback_and_completes(self):
        session = self.create_session()
        orchestrator = ProfileDialogueOrchestrator(
            self.db,
            FakeLLM(text_error=RuntimeError("LLM 返回内容为空")),
        )

        events = [
            event
            async for event in orchestrator.stream_user_message(
                request=FakeRequest(),
                session_id=session.id,
                student_id=7,
                user_message="继续",
                client_message_id="empty-reply-id",
            )
        ]

        delta_text = "".join(
            json.loads(event.split("data: ", 1)[1])["content"]
            for event in events
            if event.startswith("event: delta")
        )
        assistant = self.db.query(ProfileDialogueMessage).filter_by(role="assistant").one()

        self.assertTrue(delta_text)
        self.assertTrue(any(event.startswith("event: done") for event in events))
        self.assertFalse(any(event.startswith("event: error") for event in events))
        self.assertEqual(assistant.stream_status, "completed")
        self.assertEqual(assistant.content, delta_text)

    async def test_retry_repairs_existing_empty_failed_assistant_message(self):
        session = self.create_session()
        user_message = ProfileDialogueMessage(
            session_id=session.id,
            student_id=7,
            role="user",
            content="继续",
            client_message_id="failed-retry-id",
            slot="learning_style",
            stream_status="completed",
        )
        assistant = ProfileDialogueMessage(
            session_id=session.id,
            student_id=7,
            role="assistant",
            content="",
            partial_content="",
            slot="learning_habits",
            stream_status="failed",
            agent_result_json={
                "dialogue_action": {
                    "action": "recover_from_irrelevant",
                    "question_field": "planning_habit",
                    "question_text": "平时学习会提前做计划吗？",
                }
            },
        )
        self.db.add_all([user_message, assistant])
        self.db.commit()

        orchestrator = ProfileDialogueOrchestrator(self.db, FakeLLM())
        events = [
            event
            async for event in orchestrator.stream_user_message(
                request=FakeRequest(),
                session_id=session.id,
                student_id=7,
                user_message="继续",
                client_message_id="failed-retry-id",
            )
        ]

        delta_text = "".join(
            json.loads(event.split("data: ", 1)[1])["content"]
            for event in events
            if event.startswith("event: delta")
        )
        self.db.refresh(assistant)
        self.assertTrue(delta_text)
        self.assertEqual(assistant.stream_status, "completed")
        self.assertEqual(assistant.content, delta_text)
        self.assertTrue(any(event.startswith("event: done") for event in events))


if __name__ == "__main__":
    unittest.main()
