import uuid
import json

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.resource import (
    GenerateResourceRequest,
    GenerateResourceTaskResponse,
    RecommendedResourcesResponse,
    ResourceDetailResponse,
    ResourceFeedbackCreate,
    ResourceFeedbackResponse,
    ResourceTaskDetailResponse,
    ResourceTaskStepItem,
    ResourceViewResponse,
)
from app.models.resource_agent import AgentTask, AgentTaskStep, ResourceGenerationTask
from app.services.resource_generation_graph_service import run_resource_generation_graph
from app.services.resource_service import get_recommended_resources, get_resource_detail, submit_resource_feedback, record_resource_view
from app.utils.response import ApiResponse, success

router = APIRouter(prefix="/resources", tags=["学习资源"])


@router.post("/generate", response_model=ApiResponse[GenerateResourceTaskResponse])
def generate_resource_task(
    payload: GenerateResourceRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    """
    阶段 4.1：创建个性化资源生成任务。

    创建任务后，后台使用 LangGraph 执行多智能体流程：
    Profile → Knowledge → Designer → Doc/MindMap/Exercise/Code/Video → Safety → Save
    """
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
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    """
    阶段 4.2：查询资源生成任务进度。

    Flutter 资源生成页可以每 1 秒轮询一次该接口。
    """
    student_id = str(current_user.id)

    task = (
        db.query(ResourceGenerationTask)
        .filter(
            ResourceGenerationTask.id == task_id,
            ResourceGenerationTask.student_id == student_id,
        )
        .first()
    )

    if task is None:
        from app.utils.response import AppException, ErrorCode
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
    """
    阶段 3.3：获取当前学生推荐资源列表。

    Flutter 首页推荐资源区域调用：
    GET /api/resources/recommend
    """
    data = get_recommended_resources(db=db, current_user=current_user)
    return success(data)

@router.get("/{resource_id}", response_model=ApiResponse[ResourceDetailResponse])
def resource_detail(
    resource_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    """
    阶段 3.4：获取学习资源详情。

    Flutter 点击推荐资源卡片后调用：
    GET /api/resources/{resource_id}
    """
    data = get_resource_detail(
        db=db,
        current_user=current_user,
        resource_id=resource_id,
    )
    return success(data)

@router.post("/{resource_id}/feedback", response_model=ApiResponse[ResourceFeedbackResponse])
def create_resource_feedback(
    resource_id: str,
    payload: ResourceFeedbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    """
    阶段 3.5：提交学习资源反馈。

    Flutter 资源详情页点击喜欢、收藏、难度反馈时调用：
    POST /api/resources/{resource_id}/feedback
    """
    data = submit_resource_feedback(
        db=db,
        current_user=current_user,
        resource_id=resource_id,
        feedback_data=payload,
    )
    return success(data)

@router.post("/{resource_id}/view", response_model=ApiResponse[ResourceViewResponse])
def view_resource(
    resource_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    """
    记录学生查看学习资源行为。

    Flutter 进入资源详情页时调用：
    POST /api/resources/{resource_id}/view
    """
    data = record_resource_view(
        db=db,
        current_user=current_user,
        resource_id=resource_id,
    )
    return success(data)

