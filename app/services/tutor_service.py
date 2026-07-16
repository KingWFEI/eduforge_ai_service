import asyncio
import re
import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.course import Course
from app.models.tutor import TutorMessage, TutorSession
from app.services.llm_service import DeepSeekService
from app.services.tutor_retrieval_service import TutorRetrievalService
from app.utils.response import AppException, ErrorCode, success
from app.utils.sse import sse_event


class TutorService:
    def __init__(
        self,
        db: Session,
        llm: DeepSeekService | None = None,
        retrieval: TutorRetrievalService | None = None,
    ):
        self.db = db
        # LLM initialization is lazy so session-management APIs do not require an API key.
        self._llm = llm
        self.retrieval = retrieval or TutorRetrievalService(db)

    @property
    def llm(self) -> DeepSeekService:
        if self._llm is None:
            self._llm = DeepSeekService()
        return self._llm

    async def enter_session(
        self,
        student_id: int,
        course_id: str | None,
        section_id: str | None,
    ) -> dict:
        self._validate_tutoring_context(course_id, section_id)
        session = self._find_active_session(student_id, course_id, section_id)
        is_new = session is None
        if session is None:
            session = self._create_session(student_id, course_id, section_id)

        return {
            "session_id": session.id,
            "session_type": session.session_type,
            "course_id": session.course_id,
            "is_new": is_new,
        }

    def _find_active_session(
        self,
        student_id: int,
        course_id: str | None,
        section_id: str | None,
    ) -> TutorSession | None:
        query = (
            self.db.query(TutorSession)
            .filter(
                TutorSession.student_id == student_id,
                TutorSession.status == "active",
            )
        )
        if course_id and section_id:
            query = query.filter(
                TutorSession.session_type == "tutoring",
                TutorSession.course_id == course_id,
                TutorSession.section_id == section_id,
            )
        else:
            query = query.filter(
                TutorSession.session_type == "general",
                TutorSession.course_id.is_(None),
                TutorSession.section_id.is_(None),
            )
        return (
            query.order_by(TutorSession.updated_at.desc(), TutorSession.created_at.desc())
            .first()
        )

    def _validate_tutoring_context(
        self,
        course_id: str | None,
        section_id: str | None,
    ) -> None:
        if bool(course_id) != bool(section_id):
            raise AppException(
                code=ErrorCode.PARAM_ERROR,
                message="course_id and section_id must be provided together",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if not course_id:
            return

        from app.models.course_structure import CourseChapter

        section = (
            self.db.query(CourseChapter.id)
            .filter(
                CourseChapter.id == section_id,
                CourseChapter.course_id == course_id,
            )
            .first()
        )
        if section is None:
            raise AppException(
                code=ErrorCode.NOT_FOUND,
                message="Course or section does not exist, or the section is not in the course",
                status_code=status.HTTP_404_NOT_FOUND,
            )

    def _create_session(
        self,
        student_id: int,
        course_id: str | None,
        section_id: str | None,
    ) -> TutorSession:
        is_tutoring = bool(course_id and section_id)
        session = TutorSession(
            id=str(uuid.uuid4()),
            student_id=student_id,
            session_type="tutoring" if is_tutoring else "general",
            course_id=course_id if is_tutoring else None,
            section_id=section_id if is_tutoring else None,
            title="",
            status="active",
        )
        self.db.add(session)
        self._commit()
        self.db.refresh(session)
        return session

    async def list_sessions(
        self,
        student_id: int,
        page: int,
        page_size: int,
        session_type: str | None,
    ) -> dict:
        query = (
            self.db.query(TutorSession, Course.name.label("course_name"))
            .outerjoin(Course, Course.course_id == TutorSession.course_id)
            .filter(TutorSession.student_id == student_id)
        )
        if session_type:
            query = query.filter(TutorSession.session_type == session_type)

        total = query.count()
        rows = (
            query.order_by(TutorSession.updated_at.desc(), TutorSession.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {
            "total": total,
            "items": [self._session_dict(session, course_name) for session, course_name in rows],
        }

    async def get_messages(self, session_id: str) -> list[TutorMessage]:
        return (
            self.db.query(TutorMessage)
            .filter(TutorMessage.session_id == session_id)
            .order_by(TutorMessage.created_at.asc(), TutorMessage.id.asc())
            .all()
        )

    async def close_session(self, session_id: str) -> dict:
        session = self._get_session(session_id)
        session.status = "closed"
        self._commit()
        return {"session_id": session.id, "status": "closed"}

    async def verify_ownership(self, session_id: str, student_id: int) -> TutorSession:
        session = self._get_session(session_id)
        if session.student_id != student_id:
            raise AppException(
                code=ErrorCode.FORBIDDEN,
                message="You do not have access to this tutor session",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return session

    def _get_session(self, session_id: str) -> TutorSession:
        session = self.db.query(TutorSession).filter(TutorSession.id == session_id).first()
        if session is None:
            raise AppException(
                code=ErrorCode.NOT_FOUND,
                message="Tutor session not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return session

    def _save_message(self, session: TutorSession, role: str, content: str) -> TutorMessage:
        message = TutorMessage(
            id=str(uuid.uuid4()),
            session_id=session.id,
            role=role,
            content=content,
        )
        session.last_message = content[:500]
        self.db.add(message)
        self.db.add(session)
        self._commit()
        self.db.refresh(message)
        return message

    def _update_session_title(self, session: TutorSession, first_message: str) -> None:
        session.title = first_message[:30] + ("..." if len(first_message) > 30 else "")

    async def process_message(
        self,
        session_id: str,
        student_id: int,
        message: str,
        course_id: str | None = None,
        section_id: str | None = None,
        context: str | None = None,
    ) -> AsyncGenerator[str, None]:
        session = await self.verify_ownership(session_id, student_id)
        if session.status != "active":
            yield sse_event(
                "error",
                {
                    "code": ErrorCode.CONFLICT,
                    "message": "Tutor session is closed",
                    "data": None,
                },
            )
            return

        full_answer = ""
        try:
            effective_course_id, effective_section_id = self._resolve_context(
                session, course_id, section_id
            )
            history = await self.get_messages(session_id)
            if not history:
                self._update_session_title(session, message)
            self._save_message(session, "user", message)

            greeting_answer = self._simple_greeting_answer(
                message=message,
                is_tutoring=session.session_type == "tutoring",
            )
            if greeting_answer:
                self._save_message(session, "assistant", greeting_answer)
                yield sse_event("delta", success({"content": greeting_answer}))
                yield sse_event(
                    "done",
                    success({"answer": greeting_answer, "session_id": session_id}),
                )
                return

            retrieved_context = ""
            if session.session_type == "tutoring":
                chunks = await self.retrieval.search(
                    course_id=effective_course_id,
                    section_id=effective_section_id,
                    query=message,
                    top_k=5,
                )
                retrieved_context = self.retrieval.format_context(chunks)

            system_prompt = self._build_system_prompt(
                is_tutoring=session.session_type == "tutoring",
                retrieved_context=retrieved_context,
                user_context=context,
            )
            llm_messages = [{"role": "system", "content": system_prompt}]
            llm_messages.extend(
                {"role": item.role, "content": item.content} for item in history[-20:]
            )
            llm_messages.append({"role": "user", "content": message})

            async for chunk in self.llm.chat_stream(llm_messages):
                full_answer += chunk
                yield sse_event("delta", success({"content": chunk}))

            if not full_answer:
                raise RuntimeError("LLM returned an empty response")
            self._save_message(session, "assistant", full_answer)
            yield sse_event(
                "done",
                success({"answer": full_answer, "session_id": session_id}),
            )
        except asyncio.CancelledError:
            if full_answer:
                self._save_message(session, "assistant", full_answer + "\n\n（回复中断）")
            raise
        except AppException as exc:
            if full_answer:
                self._save_message(session, "assistant", full_answer + "\n\n（回复中断）")
            yield sse_event(
                "error",
                {
                    "code": exc.code,
                    "message": exc.message,
                    "data": exc.data,
                },
            )
        except Exception as exc:
            if full_answer:
                self._save_message(session, "assistant", full_answer + "\n\n（回复中断）")
            yield sse_event(
                "error",
                {
                    "code": ErrorCode.LLM_ERROR,
                    "message": str(exc),
                    "data": {"partial_answer": full_answer or None},
                },
            )

    def _resolve_context(
        self,
        session: TutorSession,
        course_id: str | None,
        section_id: str | None,
    ) -> tuple[str | None, str | None]:
        if course_id and course_id != session.course_id:
            raise AppException(
                code=ErrorCode.PARAM_ERROR,
                message="course_id does not match the tutor session",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if section_id and section_id != session.section_id:
            raise AppException(
                code=ErrorCode.PARAM_ERROR,
                message="section_id does not match the tutor session",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return session.course_id, session.section_id

    @staticmethod
    def _build_system_prompt(
        is_tutoring: bool,
        retrieved_context: str,
        user_context: str | None,
    ) -> str:
        if not is_tutoring:
            return (
                "你是 EduForge 智学工坊的 AI 学习助手。解答学生在学习中的问题，"
                "用通俗准确的中文解释复杂概念，并在需要时提供学习方法建议。"
                "回答应自然、简洁、克制，不使用夸张玩笑，不堆砌表情符号，也不要主动罗列大量能力。"
                "只有复杂学习问题确实需要时才分点或分层说明，不要机械使用“核心答案”“展开解释”等固定标题。"
                "面对问候或闲聊时，用一到两句话自然回应；只关注用户当前这句话，"
                "不要因为历史里出现过相同问候就说用户在循环或重复。"
            )

        prompt = (
            "你是 EduForge 的 AI 辅导老师，正在帮助学生学习课程内容。"
            "请基于课程内容解答疑问，善用类比和分步讲解，引导学生思考，"
            "保持鼓励、耐心和专业。若资料不足，请明确说明，不要编造课程事实。"
        )
        if retrieved_context:
            prompt += f"\n\n【课程知识库检索结果】\n{retrieved_context}\n\n请优先基于以上课程内容回答。"
        if user_context:
            prompt += f"\n\n【学生选中的学习内容】\n{user_context}\n\n请针对这段内容解答。"
        return prompt

    @staticmethod
    def _simple_greeting_answer(message: str, is_tutoring: bool) -> str | None:
        normalized = re.sub(r"[\s!！。,.，？?～~]+", "", message).lower()
        if normalized not in {"你好", "您好", "嗨", "哈喽", "hello", "hi", "hey"}:
            return None
        if is_tutoring:
            return "你好！我可以结合当前课程内容帮助你理解知识点。你想先从哪里开始？"
        return "你好！我是 EduForge AI 学习助手。有什么学习问题需要我帮你吗？"

    @staticmethod
    def _session_dict(session: TutorSession, course_name: str | None) -> dict:
        return {
            "id": session.id,
            "title": session.title,
            "session_type": session.session_type,
            "course_id": session.course_id,
            "course_name": course_name,
            "status": session.status,
            "last_message": session.last_message,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
        }

    def _commit(self) -> None:
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise


def get_tutor_service(db: Session = Depends(get_db)) -> TutorService:
    return TutorService(db)
