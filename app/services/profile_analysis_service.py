import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.agents.onboarding_profile_agent import OnboardingProfileAgent
from app.db.session import SessionLocal
from app.models.onboarding import OnboardingSubmission
from app.models.profile_analysis import ProfileAnalysis
from app.models.learning_profile import StudentLearningProfile
from app.models.user import UserOnboardingStatus
from app.services.llm_service import DeepSeekService

logger = logging.getLogger("app.services.profile_analysis")


def _update_analysis(
    db: Session,
    analysis_id: str,
    **kwargs,
) -> None:
    """安全更新 analysis 记录（捕获异常避免打断流程）"""
    try:
        analysis = db.query(ProfileAnalysis).filter(ProfileAnalysis.id == analysis_id).first()
        if analysis:
            for key, value in kwargs.items():
                setattr(analysis, key, value)
            db.commit()
    except Exception:
        db.rollback()
        logger.exception("failed to update profile analysis | analysis_id=%s", analysis_id)


async def run_profile_analysis(
    analysis_id: str,
    submission_id: str,
    user_id: int,
    student_id: str,
    answers: dict,
) -> None:
    """
    后台运行画像分析任务。

    完整流程：
    1. 更新状态为 processing
    2. 调用 Agent 生成画像
    3. 保存 StudentLearningProfile
    4. 更新 ProfileAnalysis 结果
    5. 标记 completed / failed
    """
    result = None
    db = SessionLocal()
    try:
        _update_analysis(
            db, analysis_id,
            status="processing",
            progress=10,
            current_step="正在调用画像智能体分析学习偏好",
            started_at=datetime.now(timezone.utc),
        )

        # 调用 Agent（内部 DeepSeek 调用是同步的，放入线程池避免阻塞事件循环）
        agent = OnboardingProfileAgent(DeepSeekService())
        result = await asyncio.to_thread(
            agent.run, {
                "student_id": student_id,
                "answers": answers,
            }
        )

        _update_analysis(
            db, analysis_id,
            progress=60,
            current_step="正在保存画像数据",
        )

        profile_data = result["profile"]

        # 保存 / 更新综合学习画像
        profile = (
            db.query(StudentLearningProfile)
            .filter(StudentLearningProfile.student_id == student_id)
            .first()
        )

        if not profile:
            profile = StudentLearningProfile(
                id="learning_profile_" + uuid.uuid4().hex[:12],
                student_id=student_id,
            )
            db.add(profile)

        profile.learning_preferences_json = profile_data.get("learning_preferences")
        profile.cognitive_traits_json = profile_data.get("cognitive_traits")
        profile.learning_habits_json = profile_data.get("learning_habits")
        profile.motivation_factors_json = profile_data.get("motivation_factors")
        profile.general_strengths_json = profile_data.get("general_strengths")
        profile.general_challenges_json = profile_data.get("general_challenges")
        profile.preferred_pace = profile_data.get("preferred_pace")
        profile.available_time_json = profile_data.get("available_time")
        profile.summary = profile_data.get("summary")
        profile.profile_dimensions_json = profile_data.get("profile_dimensions")
        profile.evidence_json = profile_data.get("evidence")
        profile.confidence_json = profile_data.get("confidence")
        profile.version = (profile.version or 0) + 1
        profile.source = "onboarding"
        db.commit()
        db.refresh(profile)

        _update_analysis(
            db, analysis_id,
            progress=80,
            current_step="正在保存画像分析结果",
        )

        # 更新 analysis 结果
        analysis = db.query(ProfileAnalysis).filter(ProfileAnalysis.id == analysis_id).first()
        if analysis:
            analysis.profile_id = profile.id
            analysis.analysis_text = profile_data.get("analysis") or profile.summary
            analysis.learning_suggestion = profile_data.get("learning_suggestion")
            analysis.resource_strategy_json = None
            analysis.weakness_analysis_json = None
            analysis.confidence = (profile.confidence_json or {}).get("overall")
            analysis.agent_trace_json = {
                "agent_used": result.get("agent_used"),
                "skill_used": result.get("skill_used"),
                "skill_name": result.get("skill_name"),
                "llm_used": result.get("llm_used"),
                "llm_provider": result.get("llm_provider"),
                "llm_error": result.get("llm_error"),
            }
            analysis.status = "completed"
            analysis.progress = 100
            analysis.current_step = "画像分析完成"
            analysis.completed_at = datetime.now(timezone.utc)

            submission = (
                db.query(OnboardingSubmission)
                .filter(OnboardingSubmission.id == submission_id)
                .first()
            )
            if submission:
                submission.generated_profile_id = profile.id
                submission.status = "completed"

            onboarding_status = (
                db.query(UserOnboardingStatus)
                .filter(UserOnboardingStatus.user_id == user_id)
                .first()
            )
            if onboarding_status is None:
                onboarding_status = UserOnboardingStatus(
                    user_id=user_id,
                    submission_id=submission_id,
                )
                db.add(onboarding_status)

            if onboarding_status.submission_id in (None, submission_id):
                onboarding_status.status = "completed"
                onboarding_status.survey_id = submission.survey_id if submission else None
                onboarding_status.submission_id = submission_id
                onboarding_status.profile_id = profile.id
                onboarding_status.need_onboarding = False
                onboarding_status.completed_at = datetime.now(timezone.utc)
            db.commit()

    except Exception as e:
        db.rollback()
        logger.exception(
            "profile analysis failed | analysis_id=%s | submission_id=%s | student_id=%s",
            analysis_id,
            submission_id,
            student_id,
        )
        error_msg = str(e)

        submission = (
            db.query(OnboardingSubmission)
            .filter(OnboardingSubmission.id == submission_id)
            .first()
        )
        if submission:
            submission.status = "failed"

        onboarding_status = (
            db.query(UserOnboardingStatus)
            .filter(UserOnboardingStatus.user_id == user_id)
            .first()
        )
        if onboarding_status is None:
            onboarding_status = UserOnboardingStatus(
                user_id=user_id,
                submission_id=submission_id,
            )
            db.add(onboarding_status)

        if onboarding_status.submission_id in (None, submission_id):
            onboarding_status.status = "failed"
            onboarding_status.survey_id = submission.survey_id if submission else None
            onboarding_status.submission_id = submission_id
            onboarding_status.need_onboarding = True

        db.commit()

        _update_analysis(
            db, analysis_id,
            status="failed",
            progress=100,
            current_step="画像分析失败",
            completed_at=datetime.now(timezone.utc),
            error_json={
                "error_code": "ANALYSIS_FAILED",
                "error_message": error_msg,
            },
            agent_trace_json={
                "agent_used": "Onboarding Profile Agent",
                "skill_used": True,
                "skill_name": "ProfileGenerationSkill",
                "llm_used": False,
                "llm_provider": "DeepSeek",
                "llm_error": error_msg,
            },
        )
    finally:
        db.close()
