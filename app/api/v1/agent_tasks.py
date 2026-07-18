from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.user import User
from app.models.resource_agent import ResourceGenerationTask
from app.schemas.agent_task import (
    AgentTaskListResponse,
    RetryAgentTaskRequest,
    RetryAgentTaskResponse,
)
from app.services.agent_task_service import (
    get_agent_task_detail,
    list_agent_tasks,
    retry_agent_task,
)
from app.services.course_content_generation_service import get_content_generation_task_status
from app.services.resource_generation_graph_service import run_resource_generation_graph
from app.utils.response import ApiResponse, success

router = APIRouter(prefix="/agent-tasks", tags=["智能体任务监控"])
task_alias_router = APIRouter(prefix="/tasks", tags=["智能体任务监控"])


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


@router.get("/{task_id}", response_model=ApiResponse[dict])
def agent_task_detail(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT, Role.TEACHER, Role.ADMIN)),
):
    resource_task = db.get(ResourceGenerationTask, task_id)
    if resource_task is not None:
        if current_user.role == Role.STUDENT.value and str(resource_task.student_id) != str(current_user.id):
            from app.utils.response import AppException, ErrorCode
            from fastapi import status
            raise AppException(code=ErrorCode.FORBIDDEN, message="无权访问该任务", status_code=status.HTTP_403_FORBIDDEN)
        resource_ids = resource_task.result_resource_ids_json or []
        return success({
            "task_id": resource_task.id,
            "task_type": "resource_generate",
            "status": resource_task.status,
            "progress": resource_task.progress or 0,
            "current_step": resource_task.current_step,
            "resource_id": resource_ids[0] if resource_ids else None,
            "resource_ids": resource_ids,
            "error": ({
                "error_code": resource_task.error_code,
                "error_message": resource_task.error_message,
                "failed_step": resource_task.failed_step,
                "retryable": bool(resource_task.retryable),
                "retry_count": resource_task.retry_count or 0,
            } if resource_task.error_message else None),
        })
    data = get_agent_task_detail(db=db, task_id=task_id)
    return success(data)


@task_alias_router.get("/{task_id}", response_model=ApiResponse[dict])
def task_detail_alias(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    task = db.execute(
        text(
            """
            SELECT task_type
            FROM agent_tasks
            WHERE id = :task_id
            LIMIT 1
            """
        ),
        {"task_id": task_id},
    ).mappings().first()
    if task and task["task_type"] == "course_content_generate":
        data = get_content_generation_task_status(db=db, task_id=task_id)
    else:
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
