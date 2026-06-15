from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.agent_task import (
    AgentTaskDetailResponse,
    AgentTaskListResponse,
    RetryAgentTaskRequest,
    RetryAgentTaskResponse,
)
from app.services.agent_task_service import (
    get_agent_task_detail,
    list_agent_tasks,
    retry_agent_task,
)
from app.services.resource_generation_graph_service import run_resource_generation_graph
from app.utils.response import ApiResponse, success

router = APIRouter(prefix="/agent-tasks", tags=["智能体任务监控"])


@router.get("", response_model=ApiResponse[AgentTaskListResponse])
def agent_task_list(
    task_type: str | None = None,
    status: str | None = Query(None),
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    data = list_agent_tasks(
        db=db,
        task_type=task_type,
        task_status=status,
        page=page,
        page_size=page_size,
    )
    return success(data)


@router.get("/{task_id}", response_model=ApiResponse[AgentTaskDetailResponse])
def agent_task_detail(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    data = get_agent_task_detail(db=db, task_id=task_id)
    return success(data)


@router.post("/{task_id}/retry", response_model=ApiResponse[RetryAgentTaskResponse])
def retry_task(
    task_id: str,
    payload: RetryAgentTaskRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    data = retry_agent_task(
        db=db,
        task_id=task_id,
        retry_from_step=payload.retry_from_step,
    )
    background_tasks.add_task(run_resource_generation_graph, data["new_task_id"])
    return success(data, message="任务已重新执行")
