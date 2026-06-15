from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.dashboard import (
    AgentStatsResponse,
    DashboardSummaryResponse,
    LearningStatsResponse,
    ResourceStatsResponse,
)
from app.services.dashboard_service import (
    get_agent_stats,
    get_dashboard_summary,
    get_learning_stats,
    get_resource_stats,
)
from app.utils.response import ApiResponse, success

router = APIRouter(prefix="/dashboard", tags=["管理端数据看板"])


@router.get("/summary", response_model=ApiResponse[DashboardSummaryResponse])
def dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    return success(get_dashboard_summary(db))


@router.get("/resource-stats", response_model=ApiResponse[ResourceStatsResponse])
def resource_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    return success(get_resource_stats(db))


@router.get("/learning-stats", response_model=ApiResponse[LearningStatsResponse])
def learning_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    return success(get_learning_stats(db))


@router.get("/agent-stats", response_model=ApiResponse[AgentStatsResponse])
def agent_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    return success(get_agent_stats(db))
