from fastapi import status
from sqlalchemy.orm import Session

from app.models.learning_profile import StudentLearningProfile
from app.models.user import User
from app.utils.response import AppException, ErrorCode


def get_my_profile(db: Session, current_user: User) -> dict:
    """获取当前学生的跨课程综合学习画像。"""
    student_id = str(current_user.id)
    profile = (
        db.query(StudentLearningProfile)
        .filter(StudentLearningProfile.student_id == student_id)
        .first()
    )

    if profile is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="当前学生还没有综合学习画像，请先完成引导问卷",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return {
        "profile_id": profile.id,
        "student_id": profile.student_id,
        "name": current_user.name,
        "learning_preferences": profile.learning_preferences_json or [],
        "cognitive_traits": profile.cognitive_traits_json or [],
        "learning_habits": profile.learning_habits_json or [],
        "motivation_factors": profile.motivation_factors_json or [],
        "general_strengths": profile.general_strengths_json or [],
        "general_challenges": profile.general_challenges_json or [],
        "preferred_pace": profile.preferred_pace,
        "available_time": profile.available_time_json or {},
        "summary": profile.summary,
        "profile_dimensions": profile.profile_dimensions_json or {},
        "evidence": profile.evidence_json or [],
        "confidence": profile.confidence_json or {},
        "version": profile.version or 1,
        "source": profile.source,
        "last_updated": profile.last_updated.isoformat() if profile.last_updated else None,
    }


def init_my_learning_data(db: Session, current_user: User) -> dict:
    """课程学习数据必须基于课程上下文，而不能仅根据综合画像生成。"""
    raise AppException(
        code=ErrorCode.CONFLICT,
        message="综合画像不包含目标课程，请先创建课程学习上下文后再初始化学习数据",
        status_code=status.HTTP_409_CONFLICT,
    )
