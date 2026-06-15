import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.resource_agent import AgentTask, AgentTaskStep, ResourceGenerationTask
from app.models.user import User
from app.schemas.resource import (
    DeleteResourceResponse,
    FavoriteResourcesResponse,
    GenerateResourceRequest,
    GenerateResourceTaskResponse,
    MyResourcesResponse,
    RecommendedResourcesResponse,
    ResourceDetailResponse,
    ResourceFavoriteRequest,
    ResourceFavoriteResponse,
    ResourceFeedbackCreate,
    ResourceFeedbackResponse,
    ResourceRegenerateRequest,
    ResourceRegenerateResponse,
    ResourceReviewRequest,
    ResourceReviewResponse,
    ReviewResourceListResponse,
    ResourceTaskDetailResponse,
    ResourceTaskStepItem,
    ResourceViewResponse,
)
from app.services.resource_generation_graph_service import run_resource_generation_graph
from app.services.resource_service import (
    clear_generated_resources,
    create_resource_regeneration_task,
    delete_resource,
    get_recommended_resources,
    get_resource_detail,
    list_favorite_resources,
    list_my_resources,
    list_review_resources,
    record_resource_view,
    review_resource,
    set_resource_favorite,
    submit_resource_feedback,
)
from app.utils.response import ApiResponse, AppException, ErrorCode, success

router = APIRouter(prefix="/resources", tags=["学习资源"])


@router.post("/generate", response_model=ApiResponse[GenerateResourceTaskResponse])
def generate_resource_task(
    payload: GenerateResourceRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    student_id = str(current_user.id)
    task_id = "task_res_" + uuid.uuid4().hex[:12]

    task = ResourceGenerationTask(
        id=task_id,
        student_id=student_id,
        course_id=payload.course_id,
        knowledge_point=payload.knowledge_point,
        goal=payload.goal,
        resource_types_json=payload.resource_types,
        difficulty=payload.difficulty,
        status="pending",
        progress=0,
        current_step="任务已进入队列",
    )
    db.add(task)
    db.commit()

    background_tasks.add_task(run_resource_generation_graph, task_id)

    return success(
        GenerateResourceTaskResponse(
            task_id=task_id,
            status="pending",
            progress=0,
            message="资源生成任务已创建，正在后台执行",
        ),
        message="资源生成任务已创建",
    )


@router.get("/task/{task_id}", response_model=ApiResponse[ResourceTaskDetailResponse])
def get_resource_generation_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT, Role.TEACHER, Role.ADMIN)),
):
    student_id = str(current_user.id)
    query = db.query(ResourceGenerationTask).filter(ResourceGenerationTask.id == task_id)
    if current_user.role == Role.STUDENT.value:
        query = query.filter(ResourceGenerationTask.student_id == student_id)
    task = query.first()
    if task is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="资源生成任务不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    agent_task = (
        db.query(AgentTask)
        .filter(AgentTask.related_task_id == task_id)
        .order_by(AgentTask.created_at.desc())
        .first()
    )

    steps = []
    agent_task_id = None
    if agent_task:
        agent_task_id = agent_task.id
        step_rows = (
            db.query(AgentTaskStep)
            .filter(AgentTaskStep.task_id == agent_task.id)
            .order_by(AgentTaskStep.step_order.asc())
            .all()
        )
        steps = [
            ResourceTaskStepItem(
                agent_name=item.agent_name,
                step_order=item.step_order,
                status=item.status,
                input_summary=item.input_summary,
                output_summary=item.output_summary,
                duration_ms=item.duration_ms,
            )
            for item in step_rows
        ]

    return success(
        ResourceTaskDetailResponse(
            task_id=task.id,
            status=task.status,
            progress=task.progress or 0,
            current_step=task.current_step,
            resource_ids=task.result_resource_ids_json or [],
            agent_task_id=agent_task_id,
            steps=steps,
            error_message=task.error_message,
        )
    )


@router.get("/recommend", response_model=ApiResponse[RecommendedResourcesResponse])
def recommend_resources(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    data = get_recommended_resources(db=db, current_user=current_user)
    return success(data)


@router.get("/my", response_model=ApiResponse[MyResourcesResponse])
def my_resources(
    type: str | None = None,
    difficulty: str | None = None,
    course_id: str | None = None,
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    data = list_my_resources(
        db=db,
        current_user=current_user,
        resource_type=type,
        difficulty=difficulty,
        course_id=course_id,
        page=page,
        page_size=page_size,
    )
    return success(data)


@router.get("/favorites", response_model=ApiResponse[FavoriteResourcesResponse])
def favorite_resources(
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    data = list_favorite_resources(
        db=db,
        current_user=current_user,
        page=page,
        page_size=page_size,
    )
    return success(data)


@router.get("/review-list", response_model=ApiResponse[ReviewResourceListResponse])
def review_resource_list(
    course_id: str | None = None,
    type: str | None = None,
    review_status: str | None = None,
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    data = list_review_resources(
        db=db,
        course_id=course_id,
        resource_type=type,
        review_status=review_status,
        page=page,
        page_size=page_size,
    )
    return success(data)


@router.delete("/generated/all", response_model=ApiResponse[DeleteResourceResponse])
def clear_my_generated_resources(
    course_id: str | None = None,
    all_students: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT, Role.ADMIN)),
):
    data = clear_generated_resources(
        db=db,
        current_user=current_user,
        course_id=course_id,
        all_students=all_students,
    )
    return success(data, message="生成资源已清理")


@router.delete("/{resource_id}", response_model=ApiResponse[DeleteResourceResponse])
def remove_resource(
    resource_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT, Role.ADMIN)),
):
    data = delete_resource(db=db, current_user=current_user, resource_id=resource_id)
    return success(data, message="资源已删除")


@router.post("/{resource_id}/review", response_model=ApiResponse[ResourceReviewResponse])
def review_generated_resource(
    resource_id: str,
    payload: ResourceReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    data = review_resource(
        db=db,
        current_user=current_user,
        resource_id=resource_id,
        action=payload.action,
        comment=payload.comment,
    )
    return success(data, message="审核完成")


@router.post("/{resource_id}/regenerate", response_model=ApiResponse[ResourceRegenerateResponse])
def regenerate_resource(
    resource_id: str,
    payload: ResourceRegenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    data = create_resource_regeneration_task(
        db=db,
        resource_id=resource_id,
        reason=payload.reason,
        keep_references=payload.keep_references,
    )
    background_tasks.add_task(run_resource_generation_graph, data["task_id"])
    return success(data, message="重新生成任务已创建")


@router.get("/{resource_id}", response_model=ApiResponse[ResourceDetailResponse])
def resource_detail(
    resource_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    data = get_resource_detail(db=db, current_user=current_user, resource_id=resource_id)
    return success(data)


@router.post("/{resource_id}/feedback", response_model=ApiResponse[ResourceFeedbackResponse])
def create_resource_feedback(
    resource_id: str,
    payload: ResourceFeedbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    data = submit_resource_feedback(
        db=db,
        current_user=current_user,
        resource_id=resource_id,
        feedback_data=payload,
    )
    return success(data, message="反馈已提交")


@router.post("/{resource_id}/favorite", response_model=ApiResponse[ResourceFavoriteResponse])
def favorite_resource(
    resource_id: str,
    payload: ResourceFavoriteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    data = set_resource_favorite(
        db=db,
        current_user=current_user,
        resource_id=resource_id,
        favorite=payload.favorite,
    )
    return success(data, message="收藏成功" if payload.favorite else "取消收藏成功")


@router.post("/{resource_id}/view", response_model=ApiResponse[ResourceViewResponse])
def view_resource(
    resource_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    data = record_resource_view(db=db, current_user=current_user, resource_id=resource_id)
    return success(data)
