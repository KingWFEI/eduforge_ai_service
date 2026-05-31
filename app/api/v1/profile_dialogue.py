# app/api/profile_dialogue.py
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.constants.role import Role
from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.user import User
from app.models.profile_dialogue_sessions import ProfileDialogueSession
from app.models.profile_dialogue_messages import ProfileDialogueMessage
from app.utils.response import AppException, ErrorCode, success
from app.schemas.profile_dialogue import (
    CreateProfileDialogueSessionRequest,
    SendProfileDialogueMessageRequest, CloseDialogueReason, ProfileDialogueMessageData,
    ProfileDialogueSessionMessagesData, ProfileDialogueHistoryMessageData,
)
from app.constants.profile_dialogue import PROFILE_DIALOGUE_SLOT_ORDER

from app.services.llm_service import LLMService
from app.services.profile_dialogue_orchestrator import ProfileDialogueOrchestrator

from fastapi import Request

router = APIRouter(prefix="/profile/dialogue", tags=["Profile Dialogue"])


@router.post("/sessions")
def create_profile_dialogue_session(
    payload: CreateProfileDialogueSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
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

@router.post("/messages")
async def send_profile_dialogue_message(
    payload: SendProfileDialogueMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    """
    发送消息接口
    """
    llm_service = LLMService()

    orchestrator = ProfileDialogueOrchestrator(
        db=db,
        llm_service=llm_service,
    )

    result = await orchestrator.handle_user_message(
        session_id=payload.session_id,
        student_id=current_user.id,
        user_message=payload.message,
    )

    return success(result)

@router.post("/confirm")
def confirm_profile_dialogue(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    session = (
        db.query(ProfileDialogueSession)
        .filter(
            ProfileDialogueSession.id == session_id,
            ProfileDialogueSession.student_id == current_user.id,
        )
        .first()
    )

    if session is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="画像对话会话不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if session.status != "ready_to_confirm":
        raise AppException(
            code=ErrorCode.CONFLICT,
            message="当前画像还未生成，不能确认保存",
            status_code=status.HTTP_409_CONFLICT,
        )

    fields = session.extracted_fields_json or {}
    preview = session.profile_preview_json or {}

    # TODO:
    # 这里写入你的 student_profiles 表
    # 也可以创建 profile_versions
    #
    # profile = StudentProfile(...)
    # db.add(profile)
    # db.commit()

    session.status = "completed"
    db.add(session)
    db.commit()
    db.refresh(session)

    return success({
        "session_id": session.id,
        "status": session.status,
        "profile_preview": preview,
        "profile_fields": fields,
    })

@router.post("/messages/stream")
async def stream_profile_dialogue_message(
    request: Request,
    payload: SendProfileDialogueMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    llm_service = LLMService()

    orchestrator = ProfileDialogueOrchestrator(
        db=db,
        llm_service=llm_service,
    )

    generator = orchestrator.stream_user_message(
        request=request,
        session_id=payload.session_id,
        student_id=current_user.id,
        user_message=payload.message,
    )

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

REASON_TO_SESSION_STATUS = {
    "user_closed": "inactive",
    "app_background": "inactive",
    "app_terminated": "inactive",
    "route_changed": "inactive",

    "client_cancelled": "interrupted",
    "sse_disconnected": "interrupted",
    "network_error": "interrupted",

    "timeout": "inactive",
    "system_expired": "cancelled",
    "new_session_started": "cancelled",

    "completed": "completed",
    "cancelled": "cancelled",
}
@router.post("/sessions/{session_id}/close")
async def close_dialogue_session(
    session_id: int,
    payload: CloseDialogueReason,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    """
    关闭session
    """
    # 1. 查询当前学生自己的画像对话会话
    session = (
        db.query(ProfileDialogueSession)
        .filter(
            ProfileDialogueSession.id == session_id,
            ProfileDialogueSession.student_id == current_user.id,
        )
        .first()
    )

    # 2. 会话不存在
    if session is None:
        raise HTTPException(
            status_code=404,
            detail="画像对话会话不存在",
        )

    # 3. 如果会话已经完成，不允许被 user_closed / app_background 等覆盖
    if session.status == "completed":
        return success(
            {
                "session_id": session.id,
                "status": session.status,
                "end_reason": session.end_reason,
                "message": "画像对话会话已完成，无需重复关闭",
            }
        )

    # 4. 兼容 payload.reason 是 Enum 或 string 的情况
    reason = payload.reason.value if hasattr(payload.reason, "value") else payload.reason

    # 5. 根据 reason 映射新状态，默认 inactive
    new_status = REASON_TO_SESSION_STATUS.get(reason, "inactive")

    now = datetime.now(timezone.utc)

    # 6. 更新会话状态
    session.status = new_status
    session.end_reason = reason
    session.ended_at = now
    session.last_active_at = now

    db.add(session)
    db.commit()
    db.refresh(session)

    # 7. 返回结果
    return success(
        {
            "session_id": session.id,
            "status": session.status,
            "end_reason": session.end_reason,
            "ended_at": session.ended_at,
        }
    )

@router.get("/active-session")
async def get_active_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    """
    查询当前学生是否存在可恢复的画像对话会话。

    前端进入 ProfileDialoguePage 时先调用该接口。
    如果存在未完成会话，前端再调用：
    GET /api/profile/dialogue/sessions/{session_id}/messages
    加载历史消息并继续对话。

    如果不存在未完成会话，前端再调用：
    POST /api/profile/dialogue/sessions
    创建新会话。
    """
    # 允许恢复的会话状态
    resumable_statuses = [
        "collecting",
        "ready_to_confirm",
        "interrupted",
        "inactive",
    ]
    session = (
        db.query(ProfileDialogueSession)
        .filter(
            ProfileDialogueSession.student_id == current_user.id,
            ProfileDialogueSession.status.in_(resumable_statuses),
        )
        .order_by(ProfileDialogueSession.updated_at.desc())
        .first()
    )
    # 没有可恢复会话
    if session is None:
        return success(
            {
                "has_active_session": False,
                "session_id": None,
                "status": None,
                "current_slot": None,
                "progress": 0.0,
                "last_active_at": None,
            }
        )
    # 太久没有活跃直接将该会话关闭
    now = datetime.now(timezone.utc)
    last_active_at = session.last_active_at or session.updated_at or session.created_at
    if last_active_at is not None:
        # 如果数据库时间是 naive datetime，这里做兼容
        if last_active_at.tzinfo is None:
            last_active_at = last_active_at.replace(tzinfo=timezone.utc)

        if now - last_active_at > timedelta(hours=24):
            session.status = "cancelled"
            session.end_reason = "system_expired"
            session.ended_at = now
            db.add(session)
            db.commit()

            return success(
                {
                    "has_active_session": False,
                    "session_id": None,
                    "status": None,
                    "current_slot": None,
                    "progress": 0.0,
                    "last_active_at": None,
                }
            )
    return success(
        {
            "has_active_session": True,
            "session_id": session.id,
            "status": session.status,
            "current_slot": session.current_slot,
            "progress": session.progress or 0.0,
            "last_active_at": session.last_active_at,
        }
    )

@router.get("/sessions/{session_id}/messages")
async def get_dialogue_session_messages(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    """
    获取画像对话会话历史消息。

    用途：
    1. 前端检测到有未完成 active-session。
    2. 用户选择继续上次对话。
    3. 前端调用本接口恢复历史消息、画像进度、当前 slot、已识别字段、缺失字段。
    """
    # 1. 查询当前学生自己的会话
    session = (
        db.query(ProfileDialogueSession)
        .filter(
            ProfileDialogueSession.id == session_id,
            ProfileDialogueSession.student_id == current_user.id,
        )
        .first()
    )

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="画像对话会话不存在",
        )

    # 2. 如果会话是 inactive / interrupted，用户选择继续时可以恢复为 collecting
    # ready_to_confirm 不要改，completed 也不要改。
    if session.status in ["inactive", "interrupted"]:
        session.status = "collecting"
        session.end_reason = None
        session.ended_at = None
        session.last_active_at = datetime.now(timezone.utc)
        db.add(session)
        db.commit()
        db.refresh(session)

    # 3. 查询历史消息
    messages = (
        db.query(ProfileDialogueMessage)
        .filter(ProfileDialogueMessage.session_id == session.id)
        .order_by(ProfileDialogueMessage.created_at.asc())
        .all()
    )

    # 4. 组装消息列表
    message_items = []

    for message in messages:
        # 如果 SSE 中断时 content 为空，但 partial_content 有内容，则优先展示 partial_content
        content = message.content or ""

        if not content and hasattr(message, "partial_content"):
            content = message.partial_content or ""

        # 一般前端只需要 user / assistant
        if message.role not in ["user", "assistant"]:
            continue

        message_items.append(
            ProfileDialogueHistoryMessageData(
                message_id=message.id,
                role=message.role,
                content=content,
                created_at=message.created_at,
            )
        )

    # 5. 返回前端需要恢复的完整状态
    return success(
        ProfileDialogueSessionMessagesData(
            session_id=session.id,
            status=session.status,
            current_slot=session.current_slot or "basic_info",
            progress=session.progress or 0.0,
            messages=message_items,
            extracted_fields=session.extracted_fields_json or {},
            collected_slots=session.collected_slots_json or [],
            missing_slots=session.missing_slots_json or [],
            profile_preview=session.profile_preview_json,
        )
    )