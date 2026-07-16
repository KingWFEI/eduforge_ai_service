from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.tutor import (
    CloseSessionResponse,
    EnterSessionRequest,
    EnterSessionResponse,
    SessionListResponse,
    StreamChatRequest,
    TutorMessageResponse,
)
from app.services.tutor_service import TutorService, get_tutor_service
from app.utils.response import ApiResponse, success


router = APIRouter(prefix="/tutor", tags=["AI辅助问答"])


@router.post("/sessions/enter", response_model=ApiResponse[EnterSessionResponse])
async def enter_session(
    payload: EnterSessionRequest,
    current_user: User = Depends(get_current_user),
    service: TutorService = Depends(get_tutor_service),
):
    return success(
        await service.enter_session(
            student_id=current_user.id,
            course_id=payload.course_id,
            section_id=payload.section_id,
        )
    )


@router.get("/sessions", response_model=ApiResponse[SessionListResponse])
async def list_sessions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session_type: Literal["general", "tutoring"] | None = None,
    current_user: User = Depends(get_current_user),
    service: TutorService = Depends(get_tutor_service),
):
    return success(
        await service.list_sessions(
            student_id=current_user.id,
            page=page,
            page_size=page_size,
            session_type=session_type,
        )
    )


@router.get(
    "/sessions/{session_id}/messages",
    response_model=ApiResponse[list[TutorMessageResponse]],
)
async def get_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    service: TutorService = Depends(get_tutor_service),
):
    await service.verify_ownership(session_id, current_user.id)
    return success(await service.get_messages(session_id))


@router.post(
    "/sessions/{session_id}/close",
    response_model=ApiResponse[CloseSessionResponse],
)
async def close_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    service: TutorService = Depends(get_tutor_service),
):
    await service.verify_ownership(session_id, current_user.id)
    return success(await service.close_session(session_id))


@router.post(
    "/sessions/{session_id}/stream",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "SSE 流式响应；delta、done、error 事件均使用 code/message/data 结构",
            "content": {
                "text/event-stream": {
                    "example": (
                        'event: delta\n'
                        'data: {"code": 0, "message": "success", '
                        '"data": {"content": "你好"}}\n\n'
                    )
                }
            },
        }
    },
)
async def stream_chat(
    session_id: str,
    payload: StreamChatRequest,
    current_user: User = Depends(get_current_user),
    service: TutorService = Depends(get_tutor_service),
):
    await service.verify_ownership(session_id, current_user.id)
    return StreamingResponse(
        service.process_message(
            session_id=session_id,
            student_id=current_user.id,
            message=payload.message,
            course_id=payload.course_id,
            section_id=payload.section_id,
            context=payload.context,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
