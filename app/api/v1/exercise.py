from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.exercise import (
    ExerciseListResponse,
    ExerciseSubmitRequest,
    ExerciseSubmitResponse,
    WrongQuestionListResponse,
)
from app.services.exercise_service import (
    get_exercises_by_resource,
    list_wrong_questions,
    submit_exercise,
)
from app.utils.response import ApiResponse, success

router = APIRouter(tags=["练习"])


@router.get("/exercises/{resource_id}", response_model=ApiResponse[ExerciseListResponse])
def get_exercises(
    resource_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    data = get_exercises_by_resource(db=db, current_user=current_user, resource_id=resource_id)
    return success(data)


@router.post("/exercise/submit", response_model=ApiResponse[ExerciseSubmitResponse])
def submit_answers(
    payload: ExerciseSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    data = submit_exercise(db=db, current_user=current_user, payload=payload)
    return success(data)


@router.get("/exercise/wrong-list", response_model=ApiResponse[WrongQuestionListResponse])
def wrong_list(
    course_id: str | None = None,
    knowledge_point: str | None = None,
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    data = list_wrong_questions(
        db=db,
        current_user=current_user,
        course_id=course_id,
        knowledge_point=knowledge_point,
        page=page,
        page_size=page_size,
    )
    return success(data)
