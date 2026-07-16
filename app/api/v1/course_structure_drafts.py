import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.constants.role import Role
from app.core.dependencies import require_role
from app.db.session import SessionLocal
from app.db.session import get_db
from app.models.user import User
from app.schemas.course import CourseStructureConfirmResponse, CourseStructureDraftConfirmRequest
from app.schemas.course_content import (
    ContentGenerationTaskStatusResponse,
    GenerateSectionResourceRequest,
    SectionResourceGenerateResponse,
    SectionLearningContentListResponse,
    StartContentGenerationTaskResponse,
)
from app.services.course_content_generation_service import (
    create_content_generation_task,
    get_content_generation_task_status,
    list_section_learning_contents,
    run_content_generation_task,
)
from app.services.course_structure_service import (
    confirm_course_structure_draft,
    get_course_structure_draft_by_id,
)
from app.services.section_resource_generation_service import generate_section_resource
from app.utils.response import ApiResponse, success
from app.utils.sse import sse_event


router = APIRouter(prefix="/course-structure-drafts", tags=["课程结构草稿"])


@router.post(
    "/{draft_id}/confirm",
    response_model=ApiResponse[CourseStructureConfirmResponse],
)
def confirm_structure_draft(
    draft_id: str,
    payload: CourseStructureDraftConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """确认管理员编辑后的章节结构，并保存为正式章节/小节/知识点。"""
    draft_record = get_course_structure_draft_by_id(db=db, draft_id=draft_id)
    data = confirm_course_structure_draft(
        db=db,
        course_id=draft_record["course_id"],
        draft_id=draft_id,
        confirmed_by=str(current_user.id),
        draft=payload.draft,
        rebuild_index=payload.rebuild_index,
    )
    return success(data, message="章节保存成功")


@router.post(
    "/{draft_id}/generate-content",
    response_model=ApiResponse[StartContentGenerationTaskResponse],
)
def generate_content(
    draft_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """基于已确认并保存的章节结构，创建异步学习内容生成任务。"""
    data = create_content_generation_task(
        db=db,
        draft_id=draft_id,
        current_user=current_user,
    )
    background_tasks.add_task(run_content_generation_task, data["task_id"])
    return success(data)


@router.post(
    "/{draft_id}/confirm-and-generate-content",
    response_model=ApiResponse[StartContentGenerationTaskResponse],
    deprecated=True,
)
def confirm_and_generate_content(
    draft_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """兼容旧入口；现在只启动内容生成，不再确认或写入章节。"""
    return generate_content(
        draft_id=draft_id,
        background_tasks=background_tasks,
        db=db,
        current_user=current_user,
    )


@router.get(
    "/content-generation-tasks/{task_id}",
    response_model=ApiResponse[ContentGenerationTaskStatusResponse],
)
def get_content_generation_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """
    查询课程学习内容异步生成任务状态。
    """
    data = get_content_generation_task_status(db=db, task_id=task_id)
    return success(data)


@router.get("/content-generation-tasks/{task_id}/events")
async def stream_content_generation_task_events(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """
    SSE 订阅课程学习内容生成进度。
    """

    async def event_generator():
        last_payload = None
        event_index = 0
        while True:
            poll_db = SessionLocal()
            try:
                data = get_content_generation_task_status(db=poll_db, task_id=task_id)
            finally:
                poll_db.close()
            payload = {
                "task_id": data["task_id"],
                "draft_id": data["draft_id"],
                "course_id": data["course_id"],
                "status": data["status"],
                "progress": data["progress"],
                "current_step": data["current_step"],
                "total_sections": data["total_sections"],
                "current_section": data["current_section"],
                "contents_generated": data["contents_generated"],
                "contents_failed": data["contents_failed"],
                "content_ids": data["content_ids"],
                "failed_items": data["failed_items"],
                "error_message": data["error_message"],
            }
            if payload != last_payload:
                event_index += 1
                yield sse_event("progress", payload, event_id=str(event_index))
                last_payload = payload
            if data["status"] in {"completed", "failed", "cancelled"}:
                event_index += 1
                yield sse_event("done", payload, event_id=str(event_index))
                break
            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/contents",
    response_model=ApiResponse[SectionLearningContentListResponse],
)
def get_section_learning_contents(
    course_id: str = Query(..., description="课程ID"),
    chapter_id: str | None = Query(None, description="章节ID"),
    section_id: str | None = Query(None, description="小节ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT, Role.TEACHER, Role.ADMIN)),
):
    """
    查询已生成的小节学习内容，学生端点击小节后可调用。
    """
    data = list_section_learning_contents(
        db=db,
        course_id=course_id,
        chapter_id=chapter_id,
        section_id=section_id,
    )
    return success(data)


@router.post(
    "/contents/resources/generate",
    response_model=ApiResponse[SectionResourceGenerateResponse],
)
def generate_section_resource_detail(
    payload: GenerateSectionResourceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT, Role.TEACHER, Role.ADMIN)),
):
    """
    根据章节学习页资源壳子实时生成资源详情。

    前端从 content_json.resources[] 取 resource_id/type，点击“生成”时调用本接口。
    """
    data = generate_section_resource(
        db=db,
        current_user=current_user,
        course_id=payload.course_id,
        section_id=payload.section_id,
        resource_id=payload.resource_id,
        resource_type=payload.type,
        content_id=payload.content_id,
    )
    return success(
        data,
        message="资源生成成功" if data["generated"] else "智能体判断无需生成资源",
    )
