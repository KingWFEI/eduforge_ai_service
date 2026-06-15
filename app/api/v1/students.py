from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.students import (
    StudentEvaluationResponse,
    StudentLearningPathResponse,
    StudentListResponse,
    StudentProfileResponse,
)
from app.services.student_management_service import (
    get_student_evaluation,
    get_student_learning_path,
    get_student_profile,
    list_students,
)
from app.utils.response import ApiResponse, success

router = APIRouter(prefix="/students", tags=["管理端学生管理"])


@router.get("", response_model=ApiResponse[StudentListResponse])
def student_list(
    keyword: str | None = None,
    course_id: str | None = None,
    weak_point: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    data = list_students(
        db=db,
        keyword=keyword,
        course_id=course_id,
        weak_point=weak_point,
        page=page,
        page_size=page_size,
    )
    return success(data)


@router.get("/{student_id}/profile", response_model=ApiResponse[StudentProfileResponse])
def student_profile(
    student_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    return success(get_student_profile(db=db, student_id=student_id))


@router.get("/{student_id}/learning-path", response_model=ApiResponse[StudentLearningPathResponse])
def student_learning_path(
    student_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    return success(get_student_learning_path(db=db, student_id=student_id))


@router.get("/{student_id}/evaluation", response_model=ApiResponse[StudentEvaluationResponse])
def student_evaluation(
    student_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    return success(get_student_evaluation(db=db, student_id=student_id))
