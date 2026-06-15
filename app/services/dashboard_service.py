from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.models.course import Course
from app.models.course_structure import CourseDocument, KnowledgeChunk
from app.models.evaluation import WeakPointRecord
from app.models.exercise import ExerciseSubmission
from app.models.learning_path import LearningPath
from app.models.resource_agent import AgentTask, AgentTaskStep, LearningResource, ResourceGenerationTask
from app.models.user import User


RESOURCE_TYPE_LABELS = {
    "document": "讲解文档",
    "mind_map": "思维导图",
    "exercise": "练习题",
    "code_case": "代码案例",
    "video_script": "视频脚本",
}


def _round_rate(value: Any) -> float:
    return round(float(value or 0), 4)


def get_dashboard_summary(db: Session) -> dict[str, Any]:
    total_agent_tasks = db.query(AgentTask).count()
    completed_agent_tasks = db.query(AgentTask).filter(AgentTask.status == "completed").count()
    today_start = date.today()

    return {
        "student_count": db.query(User).filter(User.role == Role.STUDENT.value).count(),
        "course_count": db.query(Course).count(),
        "document_count": db.query(CourseDocument).count(),
        "knowledge_chunk_count": db.query(KnowledgeChunk).filter(KnowledgeChunk.deleted == False).count(),  # noqa: E712
        "generated_resource_count": db.query(LearningResource).filter(LearningResource.generated_by_task_id.isnot(None)).count(),
        "today_generation_count": db.query(ResourceGenerationTask)
        .filter(ResourceGenerationTask.created_at >= today_start)
        .count(),
        "average_accuracy": _round_rate(db.query(func.avg(ExerciseSubmission.accuracy)).scalar()),
        "learning_path_completion_rate": _round_rate(db.query(func.avg(LearningPath.progress)).scalar()),
        "agent_task_success_rate": _round_rate(completed_agent_tasks / total_agent_tasks if total_agent_tasks else 0),
    }


def get_resource_stats(db: Session) -> dict[str, Any]:
    type_rows = (
        db.query(LearningResource.type, func.count(LearningResource.id))
        .group_by(LearningResource.type)
        .order_by(func.count(LearningResource.id).desc())
        .all()
    )

    start_date = date.today() - timedelta(days=13)
    daily_rows = (
        db.query(func.date(LearningResource.created_at), func.count(LearningResource.id))
        .filter(LearningResource.created_at >= start_date)
        .group_by(func.date(LearningResource.created_at))
        .order_by(func.date(LearningResource.created_at).asc())
        .all()
    )

    return {
        "type_distribution": [
            {
                "type": row[0] or "unknown",
                "label": RESOURCE_TYPE_LABELS.get(row[0] or "", row[0] or "未知类型"),
                "count": int(row[1] or 0),
            }
            for row in type_rows
        ],
        "daily_trend": [
            {
                "date": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]),
                "count": int(row[1] or 0),
            }
            for row in daily_rows
        ],
    }


def get_learning_stats(db: Session) -> dict[str, Any]:
    weak_rows = (
        db.query(
            WeakPointRecord.knowledge_point,
            func.count(WeakPointRecord.id),
            func.coalesce(func.sum(WeakPointRecord.wrong_count), 0),
        )
        .group_by(WeakPointRecord.knowledge_point)
        .order_by(func.coalesce(func.sum(WeakPointRecord.wrong_count), 0).desc(), func.count(WeakPointRecord.id).desc())
        .limit(10)
        .all()
    )
    progress_rows = (
        db.query(Course.course_id, Course.name, func.avg(LearningPath.progress))
        .outerjoin(LearningPath, LearningPath.course_id == Course.course_id)
        .group_by(Course.course_id, Course.name)
        .order_by(Course.created_at.desc())
        .all()
    )

    return {
        "completion_rate": _round_rate(db.query(func.avg(LearningPath.progress)).scalar()),
        "average_accuracy": _round_rate(db.query(func.avg(ExerciseSubmission.accuracy)).scalar()),
        "weak_point_rank": [
            {
                "knowledge_point": row[0],
                "student_count": int(row[1] or 0),
                "wrong_count": int(row[2] or 0),
            }
            for row in weak_rows
        ],
        "course_progress": [
            {
                "course_id": row[0],
                "course_name": row[1],
                "completion_rate": _round_rate(row[2]),
            }
            for row in progress_rows
        ],
    }


def get_agent_stats(db: Session) -> dict[str, Any]:
    total_tasks = db.query(AgentTask).count()
    completed_tasks = db.query(AgentTask).filter(AgentTask.status == "completed").count()
    status_rows = (
        db.query(AgentTask.status, func.count(AgentTask.id))
        .group_by(AgentTask.status)
        .order_by(func.count(AgentTask.id).desc())
        .all()
    )
    duration_rows = (
        db.query(AgentTaskStep.agent_name, func.avg(AgentTaskStep.duration_ms))
        .filter(and_(AgentTaskStep.duration_ms.isnot(None), AgentTaskStep.duration_ms > 0))
        .group_by(AgentTaskStep.agent_name)
        .order_by(func.avg(AgentTaskStep.duration_ms).desc())
        .limit(10)
        .all()
    )

    return {
        "total_tasks": total_tasks,
        "success_rate": _round_rate(completed_tasks / total_tasks if total_tasks else 0),
        "average_duration_seconds": _round_rate((db.query(func.avg(AgentTaskStep.duration_ms)).scalar() or 0) / 1000),
        "status_distribution": [
            {"status": row[0] or "unknown", "count": int(row[1] or 0)}
            for row in status_rows
        ],
        "agent_duration_rank": [
            {
                "agent_name": row[0],
                "average_duration_seconds": _round_rate((row[1] or 0) / 1000),
            }
            for row in duration_rows
        ],
    }
