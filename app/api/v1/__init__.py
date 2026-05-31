# app/api/profile_dialogue.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.models.profile_dialogue_sessions import ProfileDialogueSession
from app.models.profile_dialogue_messages import ProfileDialogueMessage
from app.utils.response import success
from app.schemas.profile_dialogue import (
    CreateProfileDialogueSessionRequest,
    SendProfileDialogueMessageRequest,
)
from app.constants.profile_dialogue import PROFILE_DIALOGUE_SLOT_ORDER

router = APIRouter(prefix="/api/profile/dialogue", tags=["Profile Dialogue"])


@router.post("/sessions")
def create_profile_dialogue_session(
    payload: CreateProfileDialogueSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(),
):
    opening_message = (
        "你好，我是你的 AI 学习画像助手。"
        "我会通过几个简单问题了解你的学习目标、基础水平、偏好和薄弱点，"
        "然后帮你生成专属学习画像。我们先从你的专业、年级和目标课程开始吧。"
    )

    session = ProfileDialogueSession(
        student_id=current_user.id,
        scene=payload.scene,
        status="collecting",
        current_slot="basic_info",
        collected_slots_json=[],
        missing_slots_json=PROFILE_DIALOGUE_SLOT_ORDER,
        extracted_fields_json={},
        progress=0.0,
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    assistant_msg = ProfileDialogueMessage(
        session_id=session.id,
        student_id=current_user.id,
        role="assistant",
        content=opening_message,
        slot="basic_info",
    )

    db.add(assistant_msg)
    db.commit()

    return success({
        "session_id": session.id,
        "status": session.status,
        "current_slot": session.current_slot,
        "progress": session.progress,
        "opening_message": opening_message,
        "missing_slots": session.missing_slots_json,
    })