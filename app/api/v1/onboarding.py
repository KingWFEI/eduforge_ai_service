from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.onboarding import OnboardingSubmitRequest, OnboardingSubmitResponse, OnboardingSurveyResponse
from app.services.onboarding_service import get_default_published_student_survey, submit_survey
from app.utils.response import ApiResponse, AppException, ErrorCode, success

router = APIRouter(prefix="/onboarding", tags=["学生画像与问卷"])


@router.get("/questions", response_model=ApiResponse[OnboardingSurveyResponse])
def get_questions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT, Role.TEACHER, Role.ADMIN)),
):
    """获取面向学生的默认已发布引导问卷"""
    survey = get_default_published_student_survey(db)

    if survey is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="当前没有已发布的学生引导问卷",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return success(survey)


@router.post("/submit", response_model=ApiResponse[OnboardingSubmitResponse])
def submit_onboarding(
    payload: OnboardingSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    """提交问卷答案并生成学习画像"""
    submission, profile, profile_data = submit_survey(
        db=db,
        survey_id=payload.survey_id,
        answers=payload.answers,
        student=current_user,
    )

    return success(
        OnboardingSubmitResponse(
            submission_id=submission.submission_id,
            profile=profile_data,
        ),
        message="学习画像生成成功",
    )
