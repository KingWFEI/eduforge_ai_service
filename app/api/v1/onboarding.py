import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.core.dependencies import require_role, get_current_user
from app.db.session import get_db
from app.models import UserOnboardingStatus
from app.models.onboarding import OnboardingSubmission
from app.models.profile_analysis import ProfileAnalysis
from app.models.user import User
from app.schemas.onboarding import (
    AgentTrace,
    AnalysisData,
    ErrorInfo,
    OnboardingSubmitRequest,
    OnboardingSubmitResponse,
    OnboardingSurveyResponse,
    ProfileData,
    ProfileQueryData,
    OnBoardingStatusData
)
from app.services.onboarding_service import (
    get_default_published_student_survey,
    get_published_survey_or_404,
    validate_answers_format,
    validate_answers_required,
)
from app.services.profile_analysis_service import run_profile_analysis
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


# ─── 2A.2 提交问卷答案并触发画像分析任务 ─────────────

@router.post("/submit", response_model=ApiResponse[OnboardingSubmitResponse])
async def submit_onboarding(
    req: OnboardingSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    """
    提交问卷并触发后台画像分析任务。

    异步任务模式：
    - 只保存问卷答案并触发后台分析
    - 不直接等待画像智能体分析完成
    - 前端应轮询 GET /onboarding/profile 获取结果
    """
    student_id = str(current_user.id)

    # 1. 校验问卷是否存在且已发布
    get_published_survey_or_404(db, req.survey_id)

    # 2. 校验答案格式
    format_errors = validate_answers_format(db, req.survey_id, req.answers)
    if format_errors:
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message="问卷答案格式错误",
            status_code=status.HTTP_400_BAD_REQUEST,
            data={"errors": format_errors},
        )

    # 3. 校验必填题
    missing = validate_answers_required(db, req.survey_id, req.answers)
    if missing:
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message="存在必填题未填写",
            status_code=status.HTTP_400_BAD_REQUEST,
            data={"missing_questions": missing},
        )

    # 4. 保存提交记录
    submission_id = "sub_" + uuid.uuid4().hex[:12]
    submission = OnboardingSubmission(
        id=submission_id,
        survey_id=req.survey_id,
        student_id=student_id,
        answers_json=req.answers,
    )
    db.add(submission)
    db.commit()

    # 5. 创建分析任务记录
    analysis_id = "analysis_" + uuid.uuid4().hex[:12]
    analysis = ProfileAnalysis(
        id=analysis_id,
        submission_id=submission_id,
        student_id=student_id,
        source="onboarding",
        analysis_type="initial",
        status="processing",
        progress=0,
        current_step="画像分析任务已创建，等待处理",
    )
    db.add(analysis)
    db.commit()

    # 6. 触发后台异步分析
    asyncio.create_task(
        run_profile_analysis(
            analysis_id=analysis_id,
            submission_id=submission_id,
            student_id=student_id,
            answers=req.answers,
        )
    )

    return success(
        OnboardingSubmitResponse(
            submission_id=submission_id,
            analysis_id=analysis_id,
            status="processing",
            next_action="poll_profile_result",
        ),
        message="问卷提交成功，画像分析任务已创建",
    )


# ─── 2A.3 查询问卷画像分析结果 ───────────────────────

@router.get("/profile", response_model=ApiResponse[ProfileQueryData])
def get_profile_result(
    submission_id: Optional[str] = Query(None, description="问卷提交记录 ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    """
    查询问卷画像分析结果。

    支持两种方式：
    1. submission_id 指定查询某次提交
    2. 不传则查询当前学生最新画像
    """
    student_id = str(current_user.id)

    # 查找 analysis 记录
    query = db.query(ProfileAnalysis).filter(
        ProfileAnalysis.student_id == student_id,
    )

    if submission_id:
        analysis = query.filter(
            ProfileAnalysis.submission_id == submission_id,
        ).first()
        if analysis is None:
            raise AppException(
                code=ErrorCode.NOT_FOUND,
                message="问卷提交记录不存在",
                status_code=status.HTTP_404_NOT_FOUND,
            )
    else:
        analysis = (
            query.order_by(ProfileAnalysis.created_at.desc())
            .first()
        )
        if analysis is None:
            raise AppException(
                code=ErrorCode.NOT_FOUND,
                message="暂未找到画像分析记录",
                status_code=status.HTTP_404_NOT_FOUND,
            )

    # 构建 agent_trace
    agent_trace = None
    if analysis.agent_trace_json:
        trace = analysis.agent_trace_json
        agent_trace = AgentTrace(
            agent_used=trace.get("agent_used"),
            skill_used=trace.get("skill_used"),
            skill_name=trace.get("skill_name"),
            llm_used=trace.get("llm_used"),
            llm_provider=trace.get("llm_provider"),
            llm_error=trace.get("llm_error"),
        )

    # 构建 error
    error_info = None
    if analysis.error_json:
        error_info = ErrorInfo(
            error_code=analysis.error_json.get("error_code", "UNKNOWN"),
            error_message=analysis.error_json.get("error_message", "未知错误"),
        )

    # 构建 profile (仅 completed 时才有)
    profile_data = None
    analysis_data = None

    if analysis.status == "completed" and analysis.profile_id:
        from app.models.student_profile import StudentProfile
        profile = (
            db.query(StudentProfile)
            .filter(StudentProfile.id == analysis.profile_id)
            .first()
        )
        if profile:
            profile_data = ProfileData(
                profile_id=profile.id,
                student_id=profile.student_id,
                name="",
                major=profile.major or "",
                grade=profile.grade or "",
                target_course=profile.target_course or "",
                learning_goals=profile.learning_goals_json or [],
                coding_level=profile.coding_level or "",
                math_level=profile.math_level or "",
                course_level=profile.course_level or "",
                learning_preferences=profile.learning_preferences_json or [],
                weaknesses=profile.weaknesses_json or [],
                cognitive_style=profile.cognitive_style_json or [],
                time_budget=profile.time_budget or "",
                summary=profile.summary or "",
                confidence=profile.confidence or 0.0,
                last_updated=profile.last_updated,
            )

            analysis_data = AnalysisData(
                analysis_text=analysis.analysis_text,
                learning_suggestion=analysis.learning_suggestion,
                resource_strategy=analysis.resource_strategy_json,
                weakness_analysis=analysis.weakness_analysis_json,
            )

    # 确定 message
    status_msg_map = {
        "pending": "画像分析任务等待处理中",
        "processing": "画像分析中",
        "completed": "学习画像生成成功",
        "failed": "画像分析失败",
    }

    return success(
        ProfileQueryData(
            submission_id=analysis.submission_id,
            analysis_id=analysis.id,
            status=analysis.status,
            progress=analysis.progress or 0,
            current_step=analysis.current_step,
            agent_trace=agent_trace,
            profile=profile_data,
            analysis=analysis_data,
            error=error_info,
        ),
        message=status_msg_map.get(analysis.status, "未知状态"),
    )

# 查询当前用户是否需要填写问卷
@router.get("/status")
def get_onboarding_status(
        db:Session = Depends(get_db),
        current_user: User = Depends(require_role(Role.STUDENT)),
):
    # 查询当前用户填写引导问卷的状态
    onboarding_status = (
        db.query(UserOnboardingStatus)
        .filter(UserOnboardingStatus.user_id == current_user.id)
        .first()
    )
    # 如果没有记录，说明是老数据用户或刚注册但未初始化状态
    # 这里自动创建一条 not_started 记录，避免前端拿不到状态
    if onboarding_status is None:
        onboarding_status=UserOnboardingStatus(
            user_id=current_user.id,
            status="not_started",
            need_onboarding=True,
        )
        db.add(onboarding_status)
        db.commit()
        db.refresh(onboarding_status)

    # 根据 status 重新计算 need_onboarding，避免数据库字段不一致
    need_onboarding = onboarding_status.status in [
        "not_started",
        "reset_required"
    ]
    # 如果数据库里的 need_onboarding 和计算结果不一致，顺手修正
    if onboarding_status.need_onboarding != need_onboarding:
        onboarding_status.need_onboarding = need_onboarding
        db.commit()
        db.refresh(onboarding_status)

    return success(
        OnBoardingStatusData(
            need_onboarding=need_onboarding,
            onboarding_status=onboarding_status.status,
            survey_id=onboarding_status.survey_id,
            submission_id=onboarding_status.submission_id,
            profile_id=onboarding_status.profile_id,
            completed_at=onboarding_status.completed_at,
            skipped_at=onboarding_status.skipped_at,
            reset_at=onboarding_status.reset_at,
        )
    )

# 用户跳过引导问卷填写
@router.post("/skip", response_model=ApiResponse[OnBoardingStatusData])
def skip_onboarding(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    """用户跳过引导问卷，设置状态为 skipped"""
    onboarding_status = (
        db.query(UserOnboardingStatus)
        .filter(UserOnboardingStatus.user_id == current_user.id)
        .first()
    )

    if onboarding_status is None:
        onboarding_status = UserOnboardingStatus(
            user_id=current_user.id,
            status="skipped",
            need_onboarding=False,
            skipped_at=datetime.now(timezone.utc),
        )
        db.add(onboarding_status)
    else:
        onboarding_status.status = "skipped"
        onboarding_status.need_onboarding = False
        onboarding_status.skipped_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(onboarding_status)

    return success(
        OnBoardingStatusData(
            need_onboarding=False,
            onboarding_status=onboarding_status.status,
            survey_id=onboarding_status.survey_id,
            submission_id=onboarding_status.submission_id,
            profile_id=onboarding_status.profile_id,
            completed_at=onboarding_status.completed_at,
            skipped_at=onboarding_status.skipped_at,
            reset_at=onboarding_status.reset_at,
        ),
        message="已跳过引导问卷",
    )