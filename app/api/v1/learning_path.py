from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.learning_path import TodayLearningPathResponse, CompleteTaskResponse
from app.services.learning_path_service import get_today_learning_path, complete_learning_task
from app.utils.response import ApiResponse, success

router = APIRouter(prefix="/learning-path", tags=["学习路径"])


@router.get("/today", response_model=ApiResponse[TodayLearningPathResponse])
def get_today_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    """
    阶段 3.2：获取当前学生今日学习任务。

    Flutter 首页点击“今日任务”区域时调用：
    GET /api/learning-path/today
    """
    data = get_today_learning_path(db=db, current_user=current_user)
    return success(data)

@router.put("/tasks/{task_id}/complete", response_model=ApiResponse[CompleteTaskResponse])
def complete_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    """
    完成学习任务。

    Flutter 点击“完成任务”按钮时调用：
    PUT /api/learning-path/tasks/{task_id}/complete
    """
    data = complete_learning_task(
        db=db,
        current_user=current_user,
        task_id=task_id,
    )
    return success(data)