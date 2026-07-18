from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agents.dialogue_agent import (
    DialogueGuideAgent,
    ProfileExtractorAgent,
    ProfileTypeAgent,
    RelevanceJudgeAgent,
    SafetyAgent,
)
from app.constants.profile_dialogue import (
    PROFILE_DIALOGUE_SLOT_ORDER,
    PROFILE_SLOT_CONFIG,
)
from app.models import ProfileDialogueMessage, ProfileDialogueSession
from app.services.profile_dialogue_state_service import (
    DialogueAction,
    ProfileDialogueStateService,
)
from app.services.profile_dialogue_presenter import (
    build_profile_dialogue_display,
    normalize_profile_dialogue_fields,
)
from app.utils.response import AppException, ErrorCode
from app.utils.sse import sse_event


logger = logging.getLogger("app.services.profile_dialogue_orchestrator")


class ProfileDialogueOrchestrator:
    """Deterministic learning-profile dialogue workflow orchestrator."""

    def __init__(self, db: Session, llm_service):
        self.db = db
        self.llm_service = llm_service
        self.state_service = ProfileDialogueStateService()
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
        client_message_id: str | None = None,
    ) -> dict:
        session = self._get_session(session_id, student_id)
        existing = self._find_user_message(session.id, client_message_id)
        if existing is not None:
            return self._build_replay_result(session, existing)
        self._ensure_accepts_message(session)
        user_msg, duplicate = self._save_user_message(
            session, student_id, user_message, client_message_id
        )
        if duplicate:
            return self._build_replay_result(session, user_msg)

        previous_slot = session.current_slot
        analysis = await self._analyze_turn(session, user_message)
        self._persist_state_before_reply(session, analysis, None)
        profile_preview = await self._build_profile_preview_if_needed(analysis)
        self._persist_profile_preview(session, profile_preview)

        assistant_msg = ProfileDialogueMessage(
            session_id=session.id,
            student_id=student_id,
            role="assistant",
            content="",
            partial_content="",
            slot=session.current_slot,
            is_relevant=analysis["is_relevant"],
            should_advance=analysis["action"].should_advance,
            extracted_fields_json=analysis["slot_updates"],
            stream_status="generating",
            agent_result_json=self._agent_result_payload(analysis, profile_preview),
        )
        self.db.add(assistant_msg)
        self.db.commit()
        self.db.refresh(assistant_msg)

        try:
            raw_reply = await self.guide_agent.generate_reply(
                {"dialogue_action": analysis["action"].to_dict()}
            )
            final_reply, safety_result = await self._review_reply(
                raw_reply, analysis["action"]
            )
            self._complete_assistant_message(assistant_msg, final_reply, safety_result)
            self._log_turn(session, previous_slot, user_msg, assistant_msg, analysis)
        except Exception as exc:
            self._mark_message_failed(assistant_msg, "", str(exc))
            raise

        return self._build_result(
            session=session,
            previous_slot=previous_slot,
            assistant_reply=final_reply,
            analysis=analysis,
            profile_preview=profile_preview,
        )

    async def stream_user_message(
        self,
        request: Request,
        session_id: int,
        student_id: int,
        user_message: str,
        client_message_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        assistant_msg: ProfileDialogueMessage | None = None
        sent_parts: list[str] = []
        try:
            session = self._get_session(session_id, student_id)
            previous_slot = session.current_slot
            existing = self._find_user_message(session.id, client_message_id)
            if existing is not None:
                async for event in self._stream_replay(session, existing):
                    yield event
                return
            self._ensure_accepts_message(session)
            user_msg, duplicate = self._save_user_message(
                session, student_id, user_message, client_message_id
            )
            if duplicate:
                async for event in self._stream_replay(session, user_msg):
                    yield event
                return

            yield sse_event(
                "start",
                {
                    "session_id": session.id,
                    "user_message_id": user_msg.id,
                    "current_slot": previous_slot,
                    "client_message_id": client_message_id,
                    "idempotent_replay": False,
                },
            )

            yield sse_event(
                "thinking",
                {"step": "relevance_judge", "message": "正在理解你的回答..."},
            )
            relevance_result = await self.relevance_agent.run(
                {
                    "current_slot": previous_slot,
                    "slot_requirements": PROFILE_SLOT_CONFIG[previous_slot],
                    "history_summary": self._load_history(session.id),
                    "user_message": user_message,
                }
            )
            if await request.is_disconnected():
                self._mark_session_interrupted(session)
                return

            yield sse_event(
                "thinking",
                {"step": "profile_extract", "message": "正在提取学习画像信息..."},
            )
            extraction_result = await self.extractor_agent.run(
                {
                    "current_slot": previous_slot,
                    "existing_fields": session.extracted_fields_json or {},
                    "user_message": user_message,
                }
            )
            analysis = self._build_analysis(
                session, user_message, relevance_result, extraction_result
            )

            # State is committed before profile typing and reply generation.
            self._persist_state_before_reply(session, analysis, None)

            profile_preview = None
            if analysis["action"].action == "confirm_profile":
                yield sse_event(
                    "thinking",
                    {"step": "profile_type", "message": "正在生成你的学习画像类型..."},
                )
                profile_preview = await self._build_profile_preview_if_needed(analysis)
                self._persist_profile_preview(session, profile_preview)

            yield sse_event("state_update", self._state_event(session, previous_slot, analysis))

            assistant_msg = ProfileDialogueMessage(
                session_id=session.id,
                student_id=student_id,
                role="assistant",
                content="",
                partial_content="",
                slot=session.current_slot,
                is_relevant=analysis["is_relevant"],
                should_advance=analysis["action"].should_advance,
                extracted_fields_json=analysis["slot_updates"],
                stream_status="generating",
                agent_result_json=self._agent_result_payload(analysis, profile_preview),
            )
            self.db.add(assistant_msg)
            self.db.commit()
            self.db.refresh(assistant_msg)

            yield sse_event(
                "thinking",
                {"step": "dialogue_guide", "message": "正在生成回复..."},
            )
            raw_reply = await self.guide_agent.generate_reply(
                {"dialogue_action": analysis["action"].to_dict()}
            )

            yield sse_event(
                "thinking",
                {"step": "safety_check", "message": "正在检查回复..."},
            )
            final_reply, safety_result = await self._review_reply(
                raw_reply, analysis["action"]
            )

            # The approved text is stored before any delta is exposed to the client.
            self._complete_assistant_message(assistant_msg, final_reply, safety_result)
            self._log_turn(session, previous_slot, user_msg, assistant_msg, analysis)

            for delta in self._split_reply(final_reply):
                if await request.is_disconnected():
                    partial = "".join(sent_parts)
                    self._mark_message_interrupted(assistant_msg, partial)
                    self._mark_session_interrupted(session)
                    return
                sent_parts.append(delta)
                yield sse_event(
                    "delta",
                    {"content": delta, "assistant_message_id": assistant_msg.id},
                )

            yield sse_event(
                "done",
                {
                    "session_id": session.id,
                    "assistant_message_id": assistant_msg.id,
                    "status": session.status,
                    "current_slot": session.current_slot,
                    "progress": session.progress,
                    "missing_slots": analysis["missing_slots"],
                    "extracted_fields": analysis["merged_profile"],
                    "display": build_profile_dialogue_display(
                        current_slot=session.current_slot,
                        missing_slots=analysis["missing_slots"],
                        extracted_fields=analysis["merged_profile"],
                    ),
                },
            )
        except AppException as exc:
            yield sse_event("error", {"message": exc.message, "code": exc.code})
        except Exception as exc:
            if assistant_msg is not None:
                self._mark_message_failed(assistant_msg, "".join(sent_parts), str(exc))
            yield sse_event(
                "error",
                {"message": "AI 画像分析失败，请稍后重试", "detail": str(exc)},
            )

    async def _analyze_turn(
        self,
        session: ProfileDialogueSession,
        user_message: str,
    ) -> dict:
        current_slot = session.current_slot
        relevance_result = await self.relevance_agent.run(
            {
                "current_slot": current_slot,
                "slot_requirements": PROFILE_SLOT_CONFIG[current_slot],
                "history_summary": self._load_history(session.id),
                "user_message": user_message,
            }
        )
        extraction_result = await self.extractor_agent.run(
            {
                "current_slot": current_slot,
                "existing_fields": session.extracted_fields_json or {},
                "user_message": user_message,
            }
        )
        return self._build_analysis(
            session, user_message, relevance_result, extraction_result
        )

    def _build_analysis(
        self,
        session: ProfileDialogueSession,
        user_message: str,
        relevance_result: dict,
        extraction_result: dict,
    ) -> dict:
        slot_updates = self.state_service.sanitize_slot_updates(
            extraction_result.get("slot_updates") or {}
        )
        merged_profile = self.state_service.merge_profile_fields(
            session.extracted_fields_json or {}, slot_updates
        )
        action, dialogue_state = self.state_service.build_dialogue_action(
            current_slot=session.current_slot,
            profile_data=merged_profile,
            dialogue_state=session.dialogue_state or {},
            relevance_result=relevance_result,
            slot_updates=slot_updates,
            user_message=user_message,
        )
        slot_states = self.state_service.calculate_all_slot_states(merged_profile)
        completed_slots = [
            slot for slot in PROFILE_DIALOGUE_SLOT_ORDER if slot_states[slot]["sufficient"]
        ]
        missing_slots = [
            slot for slot in PROFILE_DIALOGUE_SLOT_ORDER if slot not in completed_slots
        ]
        return {
            "relevance_result": relevance_result,
            "extraction_result": extraction_result,
            "is_relevant": bool(relevance_result.get("is_relevant", False)),
            "slot_updates": slot_updates,
            "merged_profile": merged_profile,
            "dialogue_state": dialogue_state,
            "action": action,
            "slot_states": slot_states,
            "completed_slots": completed_slots,
            "missing_slots": missing_slots,
            "progress": round(len(completed_slots) / len(PROFILE_DIALOGUE_SLOT_ORDER), 2),
        }

    async def _build_profile_preview_if_needed(self, analysis: dict) -> dict | None:
        if analysis["action"].action != "confirm_profile":
            return None
        try:
            result = await self.profile_type_agent.run(
                {"extracted_fields": analysis["merged_profile"]}
            )
        except Exception:
            logger.exception("profile type generation failed; using deterministic fallback")
            result = {
                "profile_type": "balanced_grower",
                "profile_type_name": "综合成长者",
                "summary": "已根据当前对话整理出基础学习画像。",
                "tags": [],
                "reason": "画像字段已达到可确认状态，类型分析暂时使用通用类型。",
                "confidence": 0.0,
            }
        return self._normalize_profile_preview(result)

    @staticmethod
    def _normalize_profile_preview(result: dict | None) -> dict:
        source = result if isinstance(result, dict) else {}

        def safe_text(key: str, max_length: int) -> str:
            value = source.get(key)
            return value.strip()[:max_length] if isinstance(value, str) else ""

        raw_tags = source.get("tags")
        tags = []
        if isinstance(raw_tags, list):
            for tag in raw_tags[:10]:
                if isinstance(tag, str) and tag.strip() and tag.strip() not in tags:
                    tags.append(tag.strip()[:50])

        confidence = source.get("confidence", 0.0)
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            confidence = 0.0
        confidence = max(0.0, min(1.0, float(confidence)))

        return {
            "profile_type": safe_text("profile_type", 64),
            "profile_type_name": safe_text("profile_type_name", 100),
            "summary": safe_text("summary", 1000),
            "tags": tags,
            "reason": safe_text("reason", 1000),
            "confidence": confidence,
        }

    def _persist_state_before_reply(
        self,
        session: ProfileDialogueSession,
        analysis: dict,
        profile_preview: dict | None,
    ) -> None:
        action: DialogueAction = analysis["action"]
        session.current_slot = action.next_slot
        session.collected_slots_json = analysis["completed_slots"]
        session.missing_slots_json = analysis["missing_slots"]
        session.extracted_fields_json = analysis["merged_profile"]
        session.dialogue_state = analysis["dialogue_state"]
        session.profile_preview_json = profile_preview
        session.progress = analysis["progress"]
        session.status = "ready_to_confirm" if action.profile_completed else "collecting"
        session.last_active_at = datetime.now(timezone.utc)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

    def _persist_profile_preview(
        self,
        session: ProfileDialogueSession,
        profile_preview: dict | None,
    ) -> None:
        if profile_preview is None:
            return
        session.profile_preview_json = profile_preview
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

    async def _review_reply(
        self,
        raw_reply: str,
        action: DialogueAction,
    ) -> tuple[str, dict]:
        safety_result = await self.safety_agent.run({"assistant_reply": raw_reply})
        if safety_result.get("passed", True):
            return raw_reply, safety_result
        safe_reply = (safety_result.get("safe_reply") or "").strip()
        if not safe_reply:
            safe_reply = "我们换个更合适的方式继续。你愿意回答当前问题吗？"
        return self.guide_agent._normalize_or_fallback(safe_reply, action.to_dict()), safety_result

    def _save_user_message(
        self,
        session: ProfileDialogueSession,
        student_id: int,
        user_message: str,
        client_message_id: str | None,
    ) -> tuple[ProfileDialogueMessage, bool]:
        existing = self._find_user_message(session.id, client_message_id)
        if existing is not None:
            return existing, True

        user_msg = ProfileDialogueMessage(
            session_id=session.id,
            student_id=student_id,
            role="user",
            content=user_message,
            client_message_id=client_message_id,
            slot=session.current_slot,
            stream_status="completed",
        )
        session.last_active_at = datetime.now(timezone.utc)
        self.db.add(user_msg)
        self.db.add(session)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing = self._find_user_message(session.id, client_message_id)
            if existing is not None:
                return existing, True
            raise
        self.db.refresh(user_msg)
        return user_msg, False

    def _find_user_message(
        self, session_id: int, client_message_id: str | None
    ) -> ProfileDialogueMessage | None:
        if not client_message_id:
            return None
        return (
            self.db.query(ProfileDialogueMessage)
            .filter(
                ProfileDialogueMessage.session_id == session_id,
                ProfileDialogueMessage.role == "user",
                ProfileDialogueMessage.client_message_id == client_message_id,
            )
            .first()
        )

    def _find_assistant_after(
        self, user_msg: ProfileDialogueMessage
    ) -> ProfileDialogueMessage | None:
        return (
            self.db.query(ProfileDialogueMessage)
            .filter(
                ProfileDialogueMessage.session_id == user_msg.session_id,
                ProfileDialogueMessage.role == "assistant",
                ProfileDialogueMessage.id > user_msg.id,
            )
            .order_by(ProfileDialogueMessage.id.asc())
            .first()
        )

    async def _stream_replay(
        self,
        session: ProfileDialogueSession,
        user_msg: ProfileDialogueMessage,
    ) -> AsyncGenerator[str, None]:
        assistant = self._find_assistant_after(user_msg)
        self._repair_empty_failed_assistant(assistant)
        extracted_fields = normalize_profile_dialogue_fields(
            session.extracted_fields_json
        )
        yield sse_event(
            "start",
            {
                "session_id": session.id,
                "user_message_id": user_msg.id,
                "current_slot": session.current_slot,
                "client_message_id": user_msg.client_message_id,
                "idempotent_replay": True,
            },
        )
        if assistant and (assistant.content or assistant.partial_content):
            content = assistant.content or assistant.partial_content or ""
            yield sse_event(
                "delta",
                {"content": content, "assistant_message_id": assistant.id},
            )
        yield sse_event(
            "done",
            {
                "session_id": session.id,
                "assistant_message_id": assistant.id if assistant else None,
                "message_status": assistant.stream_status if assistant else "processing",
                "status": session.status,
                "current_slot": session.current_slot,
                "progress": session.progress,
                "missing_slots": session.missing_slots_json or [],
                "extracted_fields": extracted_fields,
                "display": build_profile_dialogue_display(
                    current_slot=session.current_slot,
                    missing_slots=session.missing_slots_json or [],
                    extracted_fields=extracted_fields,
                ),
                "idempotent_replay": True,
            },
        )

    def _build_replay_result(
        self,
        session: ProfileDialogueSession,
        user_msg: ProfileDialogueMessage,
    ) -> dict:
        assistant = self._find_assistant_after(user_msg)
        self._repair_empty_failed_assistant(assistant)
        extracted_fields = normalize_profile_dialogue_fields(
            session.extracted_fields_json
        )
        return {
            "session_id": session.id,
            "status": session.status,
            "current_slot": session.current_slot,
            "previous_slot": user_msg.slot,
            "assistant_reply": (
                (assistant.content or assistant.partial_content or "") if assistant else ""
            ),
            "is_relevant": bool(assistant.is_relevant) if assistant else False,
            "should_advance": bool(assistant.should_advance) if assistant else False,
            "extracted_fields": extracted_fields,
            "collected_slots": session.collected_slots_json or [],
            "missing_slots": session.missing_slots_json or [],
            "progress": session.progress or 0.0,
            "profile_preview": session.profile_preview_json,
            "display": build_profile_dialogue_display(
                current_slot=session.current_slot,
                missing_slots=session.missing_slots_json or [],
                extracted_fields=extracted_fields,
            ),
            "idempotent_replay": True,
        }

    def _repair_empty_failed_assistant(
        self,
        assistant: ProfileDialogueMessage | None,
    ) -> None:
        if assistant is None or assistant.content or assistant.partial_content:
            return
        if assistant.stream_status != "failed":
            return
        action = (assistant.agent_result_json or {}).get("dialogue_action") or {}
        if not action:
            return
        fallback_reply = self.guide_agent._fallback_reply(action)
        self._complete_assistant_message(
            assistant,
            fallback_reply,
            {
                "passed": True,
                "used_deterministic_fallback": True,
                "reason": "recovered_failed_idempotent_replay",
            },
        )

    @staticmethod
    def _agent_result_payload(analysis: dict, profile_preview: dict | None) -> dict:
        return {
            "relevance_result": analysis["relevance_result"],
            "extraction_result": analysis["extraction_result"],
            "slot_updates": analysis["slot_updates"],
            "slot_states": analysis["slot_states"],
            "dialogue_action": analysis["action"].to_dict(),
            "profile_preview": profile_preview,
        }

    def _complete_assistant_message(
        self,
        assistant_msg: ProfileDialogueMessage,
        final_reply: str,
        safety_result: dict,
    ) -> None:
        assistant_msg.content = final_reply
        assistant_msg.partial_content = final_reply
        assistant_msg.stream_status = "completed"
        assistant_msg.completed_at = datetime.now(timezone.utc)
        assistant_msg.agent_result_json = {
            **(assistant_msg.agent_result_json or {}),
            "safety_result": safety_result,
        }
        self.db.add(assistant_msg)
        self.db.commit()
        self.db.refresh(assistant_msg)

    def _build_result(
        self,
        session: ProfileDialogueSession,
        previous_slot: str,
        assistant_reply: str,
        analysis: dict,
        profile_preview: dict | None,
    ) -> dict:
        return {
            "session_id": session.id,
            "status": session.status,
            "current_slot": session.current_slot,
            "previous_slot": previous_slot,
            "assistant_reply": assistant_reply,
            "is_relevant": analysis["is_relevant"],
            "should_advance": analysis["action"].should_advance,
            "extracted_fields": analysis["merged_profile"],
            "collected_slots": analysis["completed_slots"],
            "missing_slots": analysis["missing_slots"],
            "progress": analysis["progress"],
            "profile_preview": profile_preview,
            "display": build_profile_dialogue_display(
                current_slot=session.current_slot,
                missing_slots=analysis["missing_slots"],
                extracted_fields=analysis["merged_profile"],
            ),
            "dialogue_action": analysis["action"].to_dict(),
            "idempotent_replay": False,
        }

    @staticmethod
    def _state_event(
        session: ProfileDialogueSession,
        previous_slot: str,
        analysis: dict,
    ) -> dict:
        return {
            "session_id": session.id,
            "status": session.status,
            "current_slot": session.current_slot,
            "previous_slot": previous_slot,
            "is_relevant": analysis["is_relevant"],
            "should_advance": analysis["action"].should_advance,
            "extracted_fields": analysis["merged_profile"],
            "collected_slots": analysis["completed_slots"],
            "missing_slots": analysis["missing_slots"],
            "progress": analysis["progress"],
            "profile_preview": session.profile_preview_json,
            "display": build_profile_dialogue_display(
                current_slot=session.current_slot,
                missing_slots=analysis["missing_slots"],
                extracted_fields=analysis["merged_profile"],
            ),
            "dialogue_action": analysis["action"].to_dict(),
        }

    def _get_session(self, session_id: int, student_id: int) -> ProfileDialogueSession:
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
        return session

    @staticmethod
    def _ensure_accepts_message(session: ProfileDialogueSession) -> None:
        if session.current_slot == "confirm" or session.status in {
            "ready_to_confirm",
            "completed",
            "cancelled",
        }:
            raise AppException(
                code=ErrorCode.CONFLICT,
                message="画像已生成，请先确认或重新开始",
                status_code=status.HTTP_409_CONFLICT,
            )

    def _load_history(self, session_id: int) -> str:
        messages = (
            self.db.query(ProfileDialogueMessage)
            .filter(ProfileDialogueMessage.session_id == session_id)
            .order_by(ProfileDialogueMessage.created_at.desc(), ProfileDialogueMessage.id.desc())
            .limit(20)
            .all()
        )
        messages.reverse()
        return "\n".join(
            f"{'学生' if msg.role == 'user' else 'AI'}: {msg.content}" for msg in messages
        )

    @staticmethod
    def _split_reply(reply: str, chunk_size: int = 4) -> list[str]:
        return [reply[index:index + chunk_size] for index in range(0, len(reply), chunk_size)]

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

    def _mark_session_interrupted(self, session: ProfileDialogueSession) -> None:
        session.status = "interrupted"
        session.end_reason = "sse_disconnected"
        session.last_active_at = datetime.now(timezone.utc)
        self.db.add(session)
        self.db.commit()

    def _log_turn(
        self,
        session: ProfileDialogueSession,
        previous_slot: str,
        user_msg: ProfileDialogueMessage,
        assistant_msg: ProfileDialogueMessage,
        analysis: dict,
    ) -> None:
        action: DialogueAction = analysis["action"]
        logger.info(
            "profile dialogue turn | session_id=%s current_slot_before=%s "
            "current_slot_after=%s user_message_id=%s is_relevant=%s "
            "updated_fields=%s completed_slots=%s slot_coverage=%s "
            "dialogue_action=%s question_field=%s question_attempt_count=%s "
            "assistant_reply_length=%s",
            session.id,
            previous_slot,
            session.current_slot,
            user_msg.id,
            analysis["is_relevant"],
            {
                slot: sorted(fields.keys())
                for slot, fields in analysis["slot_updates"].items()
            },
            analysis["completed_slots"],
            {
                slot: state["coverage"]
                for slot, state in analysis["slot_states"].items()
            },
            action.action,
            action.question_field,
            action.question_attempt_count,
            len(assistant_msg.content or ""),
        )
