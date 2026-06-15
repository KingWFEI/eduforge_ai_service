from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.learning_path import (
    CompleteTaskResponse,
    GenerateLearningPathRequest,
    GenerateLearningPathResponse,
    LearningPathResponse,
    TodayLearningPathResponse,
)
from app.services.learning_path_service import (
    complete_learning_task,
    generate_learning_path,
    get_my_learning_path,
    get_today_learning_path,
)
from app.utils.response import ApiResponse, success

router = APIRouter(prefix="/learning-path", tags=["学习路径"])


@router.post("/generate", response_model=ApiResponse[GenerateLearningPathResponse])
def generate_path(
    payload: GenerateLearningPathRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    data = generate_learning_path(db=db, current_user=current_user, payload=payload)
    return success(data)


@router.get("/my", response_model=ApiResponse[LearningPathResponse | None])
def my_learning_path(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    data = get_my_learning_path(db=db, current_user=current_user)
    return success(data)


@router.get("/today", response_model=ApiResponse[TodayLearningPathResponse])
def get_today_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    data = get_today_learning_path(db=db, current_user=current_user)
    return success(data)


@router.put("/task/{task_id}/complete", response_model=ApiResponse[CompleteTaskResponse])
def complete_stage5_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    data = complete_learning_task(db=db, current_user=current_user, task_id=task_id)
    return success(data)


@router.put("/tasks/{task_id}/complete", response_model=ApiResponse[CompleteTaskResponse])
def complete_task_legacy(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    data = complete_learning_task(db=db, current_user=current_user, task_id=task_id)
    return success(data)
