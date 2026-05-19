import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.agents.onboarding_profile_agent import OnboardingProfileAgent
from app.db.session import SessionLocal
from app.models.profile_analysis import ProfileAnalysis
from app.models.student_profile import StudentProfile


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


async def run_profile_analysis(
    analysis_id: str,
    submission_id: str,
    student_id: str,
    answers: dict,
) -> None:
    """
    后台运行画像分析任务。

    完整流程：
    1. 更新状态为 processing
    2. 调用 Agent 生成画像
    3. 保存 StudentProfile
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
        agent = OnboardingProfileAgent()
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

        # 保存 / 更新 StudentProfile
        profile = (
            db.query(StudentProfile)
            .filter(StudentProfile.student_id == student_id)
            .first()
        )

        if not profile:
            profile = StudentProfile(
                id="profile_" + uuid.uuid4().hex[:12],
                student_id=student_id,
            )
            db.add(profile)

        profile.major = profile_data.get("major")
        profile.grade = profile_data.get("grade")
        profile.target_course = profile_data.get("target_course")
        profile.learning_goals_json = profile_data.get("learning_goals")
        profile.coding_level = profile_data.get("coding_level")
        profile.math_level = profile_data.get("math_level")
        profile.course_level = profile_data.get("course_level")
        profile.learning_preferences_json = profile_data.get("learning_preferences")
        profile.weaknesses_json = profile_data.get("weaknesses")
        profile.cognitive_style_json = profile_data.get("cognitive_style")
        profile.time_budget = profile_data.get("time_budget")
        profile.summary = profile_data.get("summary")
        profile.confidence = profile_data.get("confidence")
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
            analysis.resource_strategy_json = profile_data.get("resource_strategy")
            analysis.weakness_analysis_json = profile_data.get("weakness_analysis")
            analysis.confidence = profile.confidence
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
            db.commit()

    except Exception as e:
        db.rollback()
        error_msg = str(e)
        agent_trace = None
        if result:
            agent_trace = {
                "agent_used": result.get("agent_used"),
                "skill_used": result.get("skill_used"),
                "skill_name": result.get("skill_name"),
                "llm_used": result.get("llm_used"),
                "llm_provider": result.get("llm_provider"),
                "llm_error": result.get("llm_error"),
            }
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
            agent_trace_json=agent_trace,
        )
    finally:
        db.close()
