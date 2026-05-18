from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import PageResponse
from app.schemas.onboarding import (
    OnboardingOptionCreateRequest,
    OnboardingOptionCreateResponse,
    OnboardingOptionUpdateRequest,
    OnboardingQuestionCreateRequest,
    OnboardingQuestionCreateResponse,
    OnboardingQuestionUpdateRequest,
    OnboardingSurveyCreateRequest,
    OnboardingSurveyCreateResponse,
    OnboardingSurveyDetailResponse,
    OnboardingSurveyListItem,
    OnboardingSurveyPublishResponse,
    OnboardingSurveyUpdateRequest,
    QuestionReorderRequest,
)
from app.services.onboarding_service import (
    archive_survey,
    create_option,
    create_question,
    create_survey,
    delete_option,
    delete_question,
    duplicate_survey,
    get_survey_detail,
    list_surveys,
    publish_survey,
    reorder_questions,
    update_option,
    update_question,
    update_survey,
)
from app.utils.response import ApiResponse, success

router = APIRouter(prefix="/admin/onboarding", tags=["管理端问卷配置"])


@router.get("/surveys", response_model=ApiResponse[PageResponse[OnboardingSurveyListItem]])
def get_surveys(
    status: Optional[Literal["draft", "published", "archived"]] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """分页查询问卷列表（教师/管理员权限）"""
    items, total = list_surveys(
        db=db,
        status_value=status,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )

    return success(
        PageResponse[OnboardingSurveyListItem](
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post("/surveys", response_model=ApiResponse[OnboardingSurveyCreateResponse])
def create_onboarding_survey(
    payload: OnboardingSurveyCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """创建新问卷"""
    survey = create_survey(db=db, payload=payload, created_by=current_user.username)
    return success(survey, message="问卷创建成功")


@router.get("/surveys/{survey_id}", response_model=ApiResponse[OnboardingSurveyDetailResponse])
def get_onboarding_survey_detail(
    survey_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """获取问卷详情（含题目和选项）"""
    return success(get_survey_detail(db, survey_id))


@router.put("/surveys/{survey_id}", response_model=ApiResponse[bool])
def update_onboarding_survey(
    survey_id: str,
    payload: OnboardingSurveyUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """更新问卷基本信息"""
    update_survey(db, survey_id, payload)
    return success(True, message="问卷更新成功")


@router.delete("/surveys/{survey_id}", response_model=ApiResponse[bool])
def archive_onboarding_survey(
    survey_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """归档问卷"""
    archive_survey(
        db=db,
        survey_id=survey_id,
        current_username=current_user.username,
        current_role=current_user.role,
    )
    return success(True, message="问卷已归档")


@router.post(
    "/surveys/{survey_id}/publish",
    response_model=ApiResponse[OnboardingSurveyPublishResponse],
)
def publish_onboarding_survey(
    survey_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    print("点击发布问卷")
    """发布问卷"""
    result = publish_survey(db=db, survey_id=survey_id)
    return success(result, message="问卷发布成功")


@router.post(
    "/surveys/{survey_id}/duplicate",
    response_model=ApiResponse[OnboardingSurveyCreateResponse],
)
def duplicate_onboarding_survey(
    survey_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """复制问卷"""
    result = duplicate_survey(db=db, survey_id=survey_id, created_by=current_user.username)
    return success(result, message="问卷复制成功")


@router.post(
    "/surveys/{survey_id}/questions",
    response_model=ApiResponse[OnboardingQuestionCreateResponse],
)
def create_onboarding_question(
    survey_id: str,
    payload: OnboardingQuestionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """在问卷中创建新题目"""
    result = create_question(db=db, survey_id=survey_id, payload=payload)
    return success(result, message="问题创建成功")


@router.put("/questions/{question_id}", response_model=ApiResponse[bool])
def update_onboarding_question(
    question_id: str,
    payload: OnboardingQuestionUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """更新题目信息"""
    update_question(db=db, question_id=question_id, payload=payload)
    return success(True, message="问题更新成功")


@router.delete("/questions/{question_id}", response_model=ApiResponse[bool])
def delete_onboarding_question(
    question_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """删除题目"""
    delete_question(db=db, question_id=question_id)
    return success(True, message="问题已删除")


@router.put("/surveys/{survey_id}/questions/reorder", response_model=ApiResponse[bool])
def reorder_onboarding_questions(
    survey_id: str,
    payload: QuestionReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """调整题目顺序"""
    reorder_questions(db=db, survey_id=survey_id, payload=payload)
    return success(True, message="问题顺序已更新")


@router.post(
    "/questions/{question_id}/options",
    response_model=ApiResponse[OnboardingOptionCreateResponse],
)
def create_onboarding_option(
    question_id: str,
    payload: OnboardingOptionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """为题目创建新选项"""
    result = create_option(db=db, question_id=question_id, payload=payload)
    return success(result, message="选项创建成功")


@router.put("/options/{option_id}", response_model=ApiResponse[bool])
def update_onboarding_option(
    option_id: str,
    payload: OnboardingOptionUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """更新选项信息"""
    update_option(db=db, option_id=option_id, payload=payload)
    return success(True, message="选项更新成功")


@router.delete("/options/{option_id}", response_model=ApiResponse[bool])
def delete_onboarding_option(
    option_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """删除选项"""
    delete_option(db=db, option_id=option_id)
    return success(True, message="选项已删除")
