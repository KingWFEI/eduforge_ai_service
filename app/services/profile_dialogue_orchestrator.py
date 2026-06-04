# app/services/profile_dialogue_orchestrator.py
from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy.orm import Session

from fastapi import Request, status
from app.agents.dialogue_agent import RelevanceJudgeAgent
from app.agents.dialogue_agent import ProfileExtractorAgent
from app.agents.dialogue_agent import DialogueGuideAgent
from app.agents.dialogue_agent import ProfileTypeAgent
from app.agents.dialogue_agent import SafetyAgent
from app.constants.profile_dialogue import PROFILE_SLOT_REQUIREMENTS
from app.models import ProfileDialogueSession
from app.models import ProfileDialogueMessage
from app.services.ProfileStateUpdater import ProfileStateUpdater
from app.utils.response import AppException, ErrorCode
from app.utils.sse import sse_event


class ProfileDialogueOrchestrator:
    """学习画像对话工作流编排器"""

    def __init__(self, db: Session, llm_service):
        self.db = db
        self.llm_service = llm_service
        self.state_updater = ProfileStateUpdater()

        self.relevance_agent = RelevanceJudgeAgent(llm_service)
        self.extractor_agent = ProfileExtractorAgent(llm_service)
        self.guide_agent = DialogueGuideAgent(llm_service)
        self.profile_type_agent = ProfileTypeAgent(llm_service)
        self.safety_agent = SafetyAgent(llm_service)

    async def handle_user_message(
        self,
        session_id: int,
        student_id: int,
        user_message: str,
    ) -> dict:
        """处理非流式画像对话消息并返回本轮完整状态。"""
        session = (
            self.db.query(ProfileDialogueSession)
            .filter(
                ProfileDialogueSession.id == session_id,
                ProfileDialogueSession.student_id == student_id,
            )
            .first()
        )
        if session is None:
            raise AppException(
                code=ErrorCode.NOT_FOUND,
                message="画像对话会话不存在",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        previous_slot = session.current_slot
        current_slot = session.current_slot
        existing_fields = session.extracted_fields_json or {}
        collected_slots = session.collected_slots_json or []
        session.last_active_at = datetime.utcnow()

        user_msg = ProfileDialogueMessage(
            session_id=session.id,
            student_id=student_id,
            role="user",
            content=user_message,
            slot=current_slot,
            stream_status="completed",
        )
        self.db.add(user_msg)
        self.db.commit()

        try:
            slot_requirements = PROFILE_SLOT_REQUIREMENTS.get(current_slot, [])
            relevance_result = await self.relevance_agent.run({
                "current_slot": current_slot,
                "slot_requirements": slot_requirements,
                "history_summary": self._load_history(session.id),
                "user_message": user_message,
            })
            extract_result = await self.extractor_agent.run({
                "current_slot": current_slot,
                "slot_requirements": slot_requirements,
                "existing_fields": existing_fields,
                "user_message": user_message,
            })

            is_relevant = bool(relevance_result.get("is_relevant", False))
            slot_completed = bool(extract_result.get("slot_completed", False))
            extracted_fields = extract_result.get("extracted_fields", {}) or {}
            merged_fields = self.state_updater.merge_fields(existing_fields, extracted_fields)
            should_advance = is_relevant and slot_completed

            if should_advance and current_slot not in collected_slots:
                collected_slots.append(current_slot)

            next_slot = current_slot
            if should_advance:
                next_slot = self.state_updater.get_next_slot(current_slot) or "confirm"

            missing_slots = self.state_updater.calculate_missing_slots(collected_slots)
            progress = self.state_updater.calculate_progress(collected_slots)
            profile_preview = None
            session_status = "collecting"

            if progress >= 1.0 or next_slot == "confirm":
                profile_type_result = await self.profile_type_agent.run({
                    "extracted_fields": merged_fields,
                })
                profile_preview = {
                    "profile_type": profile_type_result.get("profile_type"),
                    "profile_type_name": profile_type_result.get("profile_type_name"),
                    "summary": profile_type_result.get("summary"),
                    "tags": profile_type_result.get("tags", []),
                    "reason": profile_type_result.get("reason"),
                    "confidence": profile_type_result.get("confidence"),
                }
                session_status = "ready_to_confirm"
                next_slot = "confirm"

            guide_input = {
                "current_slot": current_slot,
                "next_slot": next_slot,
                "user_message": user_message,
                "relevance_result": relevance_result,
                "extract_result": extract_result,
                "extracted_fields": merged_fields,
                "missing_slots": missing_slots,
                "profile_preview": profile_preview,
            }
            guide_result = await self.guide_agent.run(guide_input)
            assistant_reply = guide_result.get("assistant_reply", "")
            if not assistant_reply:
                raise RuntimeError("画像对话引导智能体未返回 assistant_reply")

            safety_result = await self.safety_agent.run({
                "assistant_reply": assistant_reply,
            })
            if not safety_result.get("passed", True):
                assistant_reply = safety_result.get(
                    "safe_reply",
                    "我理解你的意思，我们继续完善学习画像信息。",
                )

            assistant_msg = ProfileDialogueMessage(
                session_id=session.id,
                student_id=student_id,
                role="assistant",
                content=assistant_reply,
                partial_content=assistant_reply,
                slot=next_slot,
                is_relevant=is_relevant,
                should_advance=should_advance,
                extracted_fields_json=extracted_fields,
                stream_status="completed",
                agent_result_json={
                    "relevance_result": relevance_result,
                    "extract_result": extract_result,
                    "profile_preview": profile_preview,
                    "guide_result": guide_result,
                    "safety_result": safety_result,
                },
            )

            session.current_slot = next_slot
            session.collected_slots_json = collected_slots
            session.missing_slots_json = missing_slots
            session.extracted_fields_json = merged_fields
            session.profile_preview_json = profile_preview
            session.progress = progress
            session.status = session_status
            session.last_active_at = datetime.utcnow()

            self.db.add(assistant_msg)
            self.db.add(session)
            self.db.commit()

            return {
                "session_id": session.id,
                "status": session.status,
                "current_slot": session.current_slot,
                "previous_slot": previous_slot,
                "assistant_reply": assistant_reply,
                "is_relevant": is_relevant,
                "should_advance": should_advance,
                "extracted_fields": merged_fields,
                "collected_slots": collected_slots,
                "missing_slots": missing_slots,
                "progress": progress,
                "profile_preview": profile_preview,
            }
        except Exception:
            self.db.rollback()
            raise

    async def stream_user_message(
        self,
        request: Request,
        session_id: int,
        student_id: int,
        user_message: str,
    ) -> AsyncGenerator[str, None]:

        assistant_msg = None
        assistant_content_parts: list[str] = []

        # 1. 读取会话状态
        try:
            session = (
                self.db.query(ProfileDialogueSession)
                .filter(
                    ProfileDialogueSession.id == session_id,
                    ProfileDialogueSession.student_id == student_id,
                )
                .first()
            )

            if session is None:
                yield sse_event("error", {"message": "画像对话会话不存在"})
                return

            previous_slot = session.current_slot
            current_slot = session.current_slot
            existing_fields = session.extracted_fields_json or {}
            collected_slots = session.collected_slots_json or []

            session.last_active_at = datetime.utcnow()
            self.db.add(session)

            # 2. 保存用户消息
            user_msg = ProfileDialogueMessage(
                session_id=session.id,
                student_id=student_id,
                role="user",
                content=user_message,
                slot=current_slot,
                stream_status="completed",
            )
            self.db.add(user_msg)
            self.db.commit()
            self.db.refresh(user_msg)


            yield sse_event(
                "start",
                {
                    "session_id": session.id,
                    "user_message_id": user_msg.id,
                    "current_slot": current_slot,
                },
            )

            # 3. 读取历史消息
            history = self._load_history(session.id)

            # 4. 当前 slot 的采集要求
            slot_requirements = PROFILE_SLOT_REQUIREMENTS.get(current_slot, [])

            yield sse_event(
                "thinking",
                {
                    "step": "relevance_judge",
                    "message": "正在理解你的回答...",
                },
            )

            # 5. 判断用户回答是否相关
            relevance_result = await self.relevance_agent.run({
                "current_slot": current_slot,
                "slot_requirements": slot_requirements,
                "history_summary": history,
                "user_message": user_message,
            })
            # 判断是否断开连接
            if await request.is_disconnected():
                self._mark_session_interrupted(session)
                return

            yield sse_event(
                "thinking",
                {
                    "step": "profile_extract",
                    "message": "正在提取学习画像信息...",
                },
            )

            # 6. 抽取画像字段
            extract_result = await self.extractor_agent.run({
                "current_slot": current_slot,
                "slot_requirements": slot_requirements,
                "existing_fields": existing_fields,
                "user_message": user_message,
            })

            is_relevant = bool(relevance_result.get("is_relevant", False))
            slot_completed = bool(extract_result.get("slot_completed", False))
            extracted_fields = extract_result.get("extracted_fields", {}) or {}

            # 7. 更新画像字段
            merged_fields = self.state_updater.merge_fields(
                existing_fields,
                extracted_fields,
            )

            should_advance = is_relevant and slot_completed

            # 8. 判断是否推进 slot
            if should_advance and current_slot not in collected_slots:
                collected_slots.append(current_slot)

            next_slot = current_slot

            if should_advance:
                maybe_next_slot = self.state_updater.get_next_slot(current_slot)
                next_slot = maybe_next_slot or "confirm"

            missing_slots = self.state_updater.calculate_missing_slots(collected_slots)
            progress = self.state_updater.calculate_progress(collected_slots)

            profile_preview = None
            status = "collecting"

            # 9. 如果已经完成全部 slot，生成画像类型
            if progress >= 1.0 or next_slot == "confirm":
                yield sse_event(
                    "thinking",
                    {
                        "step": "profile_type",
                        "message": "正在生成你的学习画像类型...",
                    },
                )

                profile_type_result = await self.profile_type_agent.run({
                    "extracted_fields": merged_fields,
                })

                profile_preview = {
                    "profile_type": profile_type_result.get("profile_type"),
                    "profile_type_name": profile_type_result.get("profile_type_name"),
                    "summary": profile_type_result.get("summary"),
                    "tags": profile_type_result.get("tags", []),
                    "reason": profile_type_result.get("reason"),
                    "confidence": profile_type_result.get("confidence"),
                }

                status = "ready_to_confirm"
                next_slot = "confirm"

            yield sse_event(
                "state_update",
                {
                    "session_id": session.id,
                    "status": status,
                    "current_slot": next_slot,
                    "previous_slot": previous_slot,
                    "is_relevant": is_relevant,
                    "should_advance": should_advance,
                    "extracted_fields": merged_fields,
                    "collected_slots": collected_slots,
                    "missing_slots": missing_slots,
                    "progress": progress,
                    "profile_preview": profile_preview,
                },
            )

            assistant_msg = ProfileDialogueMessage(
                session_id=session.id,
                student_id=student_id,
                role="assistant",
                content="",
                partial_content="",
                slot=next_slot,
                is_relevant=is_relevant,
                should_advance=should_advance,
                extracted_fields_json=extracted_fields,
                stream_status="streaming",
                agent_result_json={
                    "relevance_result": relevance_result,
                    "extract_result": extract_result,
                    "profile_preview": profile_preview,
                },
            )

            self.db.add(assistant_msg)
            self.db.commit()
            self.db.refresh(assistant_msg)

            yield sse_event(
                "thinking",
                {
                    "step": "dialogue_guide",
                    "message": "正在生成回复...",
                },
            )
            # 10. 生成 AI 回复
            guide_input = {
                "current_slot": current_slot,
                "next_slot": next_slot,
                "user_message": user_message,
                "relevance_result": relevance_result,
                "extract_result": extract_result,
                "extracted_fields": merged_fields,
                "missing_slots": missing_slots,
                "profile_preview": profile_preview,
            }

            async for delta in self.guide_agent.stream_reply(guide_input):
                if await request.is_disconnected():
                    partial = "".join(assistant_content_parts)
                    self._mark_message_interrupted(assistant_msg, partial)
                    self._mark_session_interrupted(session)
                    return
                assistant_content_parts.append(delta)

                yield sse_event(
                    "delta",
                    {
                        "content": delta,
                        "assistant_message_id": assistant_msg.id,
                    },
                )

            full_reply = "".join(assistant_content_parts)

        # 11. 安全检查
            safety_result = await self.safety_agent.run({
                "assistant_reply": full_reply,
            })

            if not safety_result.get("passed", True):
                assistant_reply = safety_result.get(
                    "safe_reply",
                    "我理解你的意思，我们继续完善学习画像信息。",
                )

            assistant_msg.content = full_reply
            assistant_msg.partial_content = full_reply
            assistant_msg.stream_status = "completed"
            assistant_msg.agent_result_json = {
                **(assistant_msg.agent_result_json or {}),
                "safety_result": safety_result,
            }
            # 12. 更新 session
            session.current_slot = next_slot
            session.collected_slots_json = collected_slots
            session.missing_slots_json = missing_slots
            session.extracted_fields_json = merged_fields
            session.profile_preview_json = profile_preview
            session.progress = progress
            session.status = status

            self.db.add(assistant_msg)
            self.db.add(session)
            self.db.commit()
            self.db.refresh(assistant_msg)
            self.db.refresh(session)

            yield sse_event(
                "done",
                {
                    "session_id": session.id,
                    "assistant_message_id": assistant_msg.id,
                    "status": session.status,
                    "current_slot": session.current_slot,
                    "progress": session.progress,
                },
            )
        except Exception as e:
            if assistant_msg is not None:
                partial = "".join(assistant_content_parts)
                self._mark_message_failed(assistant_msg, partial, str(e))

            yield sse_event(
                "error",
                {
                    "message": "AI 画像分析失败，请稍后重试",
                    "detail": str(e),
                },
            )

    def _load_history(self, session_id: int) -> str:
        messages = (
            self.db.query(ProfileDialogueMessage)
            .filter(ProfileDialogueMessage.session_id == session_id)
            .order_by(ProfileDialogueMessage.created_at.asc())
            .limit(20)
            .all()
        )

        lines = []
        for msg in messages:
            role = "学生" if msg.role == "user" else "AI"
            lines.append(f"{role}: {msg.content}")

        return "\n".join(lines)

    def _mark_message_interrupted(
            self,
            msg: ProfileDialogueMessage,
            partial_content: str,
    ) -> None:
        msg.content = partial_content
        msg.partial_content = partial_content
        msg.stream_status = "interrupted"
        self.db.add(msg)
        self.db.commit()

    def _mark_message_failed(
            self,
            msg: ProfileDialogueMessage,
            partial_content: str,
            error_message: str,
    ) -> None:
        msg.content = partial_content
        msg.partial_content = partial_content
        msg.stream_status = "failed"
        msg.agent_result_json = {
            **(msg.agent_result_json or {}),
            "error": error_message,
        }
        self.db.add(msg)
        self.db.commit()

    def _mark_session_interrupted(
            self,
            session: ProfileDialogueSession,
    ) -> None:
        session.status = "interrupted"
        session.end_reason = "sse_disconnected"
        session.last_active_at = datetime.utcnow()
        self.db.add(session)
        self.db.commit()
