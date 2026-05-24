from __future__ import annotations

from typing import Any, Callable, TypeVar

from sqlalchemy import func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.evaluation import WeakPointRecord
from app.models.exercise import ExerciseSubmission
from app.models.learning_path import LearningPath, LearningPathTask
from app.models.other import StudyRecord
from app.models.resource_agent import LearningResource
from app.models.student_profile import StudentProfile
from app.models.user import User
from app.schemas.home import HomeSummaryResponse

T = TypeVar("T")


def _safe(db: Session, query_fn: Callable[[], T], default: T) -> T:
    """
    安全执行数据库查询。

    阶段 3.1 的首页要先跑通；如果后续阶段的某张表暂时没建好、字段还没数据，
    这里会回滚当前查询并返回默认值，避免整个首页接口 500。
    """
    try:
        value = query_fn()
        return default if value is None else value
    except SQLAlchemyError:
        db.rollback()
        return default


def _normalize_progress(value: Any) -> float:
    """把数据库里的进度统一转成 0~1。兼容 0.35 和 35 两种写法。"""
    if value is None:
        return 0.0
    try:
        progress = float(value)
    except (TypeError, ValueError):
        return 0.0
    if progress > 1:
        progress = progress / 100
    return round(max(0.0, min(progress, 1.0)), 2)


def _normalize_accuracy(value: Any) -> float:
    """把正确率统一转成 0~1。兼容 0.78 和 78 两种写法。"""
    if value is None:
        return 0.0
    try:
        accuracy = float(value)
    except (TypeError, ValueError):
        return 0.0
    if accuracy > 1:
        accuracy = accuracy / 100
    return round(max(0.0, min(accuracy, 1.0)), 2)


def _json_list(value: Any) -> list[str]:
    """把 JSON 字段安全转成字符串列表。"""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    if isinstance(value, tuple):
        return [str(item) for item in value if item not in (None, "")]
    if isinstance(value, str):
        return [value] if value else []
    return []


def _format_minutes(minutes: Any, fallback: str = "45 分钟") -> str:
    """把分钟数转成前端适合展示的文字。"""
    if minutes is None:
        return fallback
    try:
        minutes_int = int(minutes)
    except (TypeError, ValueError):
        return fallback
    if minutes_int <= 0:
        return fallback
    if minutes_int < 60:
        return f"{minutes_int} 分钟"
    hours = minutes_int // 60
    rest = minutes_int % 60
    if rest == 0:
        return f"{hours} 小时"
    return f"{hours} 小时 {rest} 分钟"


def _student_id(current_user: User) -> str:
    """
    当前 users.id 是 int，但很多业务表 student_id 是 varchar。
    查询业务表时统一转成字符串，兼容 student_id='1' 这种存法。
    """
    return str(current_user.id)


def get_home_summary(db: Session, current_user: User) -> HomeSummaryResponse:
    """阶段 3.1：生成 Flutter 学生首页摘要。"""
    student_id = _student_id(current_user)
    display_name = current_user.name or current_user.username or "同学"

    profile = _safe(
        db,
        lambda: db.query(StudentProfile)
        .filter(StudentProfile.student_id == student_id)
        .order_by(StudentProfile.last_updated.desc())
        .first(),
        None,
    )

    target_course_id = profile.target_course_id if profile else None
    target_course = profile.target_course if profile else None

    if not target_course and target_course_id:
        course = _safe(
            db,
            lambda: db.query(Course).filter(Course.course_id == target_course_id).first(),
            None,
        )
        target_course = course.name if course else None

    if not target_course:
        target_course = "人工智能基础"

    active_path = _safe(
        db,
        lambda: db.query(LearningPath)
        .filter(LearningPath.student_id == student_id)
        .filter(LearningPath.status == "active")
        .order_by(LearningPath.created_at.desc())
        .first(),
        None,
    )

    course_progress = _normalize_progress(active_path.progress if active_path else 0)

    today_task = None
    if active_path:
        today_task = _safe(
            db,
            lambda: db.query(LearningPathTask)
            .filter(LearningPathTask.path_id == active_path.id)
            .filter(LearningPathTask.status != "completed")
            .order_by(LearningPathTask.day_no.asc(), LearningPathTask.created_at.asc())
            .first(),
            None,
        )
        if today_task is None:
            today_task = _safe(
                db,
                lambda: db.query(LearningPathTask)
                .filter(LearningPathTask.path_id == active_path.id)
                .order_by(LearningPathTask.day_no.desc(), LearningPathTask.created_at.desc())
                .first(),
                None,
            )

    weak_points = _safe(
        db,
        lambda: [
            row.knowledge_point
            for row in db.query(WeakPointRecord)
            .filter(WeakPointRecord.student_id == student_id)
            .order_by(WeakPointRecord.wrong_count.desc(), WeakPointRecord.updated_at.desc())
            .limit(3)
            .all()
        ],
        [],
    )
    if not weak_points and profile:
        weak_points = _json_list(profile.weaknesses_json)[:3]

    if today_task:
        today_topic = today_task.topic or "今日学习任务"
        today_estimated_time = _format_minutes(today_task.estimated_minutes, profile.time_budget if profile else "45 分钟")
        today_progress = 1.0 if today_task.status == "completed" else 0.0
    else:
        first_weak = weak_points[0] if weak_points else "基础知识巩固"
        today_topic = f"复习：{first_weak}"
        today_estimated_time = profile.time_budget if profile and profile.time_budget else "45 分钟"
        today_progress = 0.0

    total_minutes = _safe(
        db,
        lambda: db.query(func.coalesce(func.sum(StudyRecord.study_minutes), 0))
        .filter(StudyRecord.student_id == student_id)
        .scalar(),
        0,
    )
    study_hours = round(float(total_minutes or 0) / 60, 1)

    completed_tasks = _safe(
        db,
        lambda: db.query(func.count(LearningPathTask.id))
        .join(LearningPath, LearningPathTask.path_id == LearningPath.id)
        .filter(LearningPath.student_id == student_id)
        .filter(LearningPathTask.status == "completed")
        .scalar(),
        0,
    )

    average_accuracy = _safe(
        db,
        lambda: db.query(func.avg(ExerciseSubmission.accuracy))
        .filter(ExerciseSubmission.student_id == student_id)
        .scalar(),
        0.0,
    )

    recommend_query_course_id = target_course_id or (active_path.course_id if active_path else None)

    def _count_recommend_resources() -> int:
        query = db.query(func.count(LearningResource.id)).filter(
            or_(LearningResource.student_id == student_id, LearningResource.student_id.is_(None))
        )
        if recommend_query_course_id:
            query = query.filter(LearningResource.course_id == recommend_query_course_id)
        query = query.filter(
            LearningResource.review_status.in_(["pending", "auto_passed", "approved"])
        )
        return int(query.scalar() or 0)

    recommend_count = _safe(db, _count_recommend_resources, 0)

    return HomeSummaryResponse(
        greeting=f"你好，{display_name}",
        target_course=target_course,
        course_progress=course_progress,
        today_topic=today_topic,
        today_estimated_time=today_estimated_time,
        today_progress=_normalize_progress(today_progress),
        study_hours=study_hours,
        completed_tasks=int(completed_tasks or 0),
        average_accuracy=_normalize_accuracy(average_accuracy),
        weak_points=weak_points,
        recommend_count=int(recommend_count or 0),
    )
