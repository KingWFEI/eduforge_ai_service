from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.evaluation import EvaluationReportResponse, MasteryResponse, WeakPointListResponse
from app.services.evaluation_service import get_learning_report, get_mastery, get_weak_points
from app.utils.response import ApiResponse, success

router = APIRouter(prefix="/evaluation", tags=["学习评估"])


@router.get("/report", response_model=ApiResponse[EvaluationReportResponse])
def report(
    range: str = Query("week", description="week / month / all"),
    course_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    data = get_learning_report(
        db=db,
        current_user=current_user,
        report_range=range,
        course_id=course_id,
    )
    return success(data)


@router.get("/weak-points", response_model=ApiResponse[WeakPointListResponse])
def weak_points(
    course_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    data = get_weak_points(db=db, current_user=current_user, course_id=course_id)
    return success(data)


@router.get("/mastery", response_model=ApiResponse[MasteryResponse])
def mastery(
    course_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    data = get_mastery(db=db, current_user=current_user, course_id=course_id)
    return success(data)
