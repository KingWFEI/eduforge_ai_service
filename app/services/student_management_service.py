from __future__ import annotations

from typing import Any

from fastapi import status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.models.evaluation import EvaluationReport, MasteryRecord, WeakPointRecord
from app.models.exercise import ExerciseSubmission
from app.models.learning_profile import StudentLearningContext, StudentLearningProfile
from app.models.learning_path import LearningPath, LearningPathTask
from app.models.other import StudyRecord
from app.models.user import User
from app.utils.response import AppException, ErrorCode


def _iso(value: Any) -> str | None:
    return value.isoformat() if value else None


def _round_rate(value: Any) -> float:
    return round(float(value or 0), 4)


def _student_key(student: User | str) -> str:
    return str(student.id) if isinstance(student, User) else str(student)


def _get_student(db: Session, student_id: str) -> User:
    query = db.query(User).filter(User.role == Role.STUDENT.value)
    if student_id.isdigit():
        query = query.filter(User.id == int(student_id))
    else:
        query = query.filter(User.username == student_id)
    student = query.first()
    if student is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="学生不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return student


def _profile_dimensions(profile: StudentLearningProfile | None) -> dict[str, Any]:
    return profile.profile_dimensions_json or {} if profile else {}


def _major_and_grade(profile: StudentLearningProfile | None) -> tuple[str | None, str | None]:
    dimensions = _profile_dimensions(profile)
    basic = dimensions.get("basic_info") if isinstance(dimensions, dict) else {}
    if not isinstance(basic, dict):
        basic = {}
    return basic.get("major"), basic.get("grade")


def _target_course(db: Session, student_id: str) -> str | None:
    context = (
        db.query(StudentLearningContext)
        .filter(StudentLearningContext.student_id == student_id)
        .order_by(StudentLearningContext.updated_at.desc())
        .first()
    )
    return context.course_name if context else None


def _weak_point_names(db: Session, student_id: str, limit: int = 3) -> list[str]:
    rows = (
        db.query(WeakPointRecord.knowledge_point)
        .filter(WeakPointRecord.student_id == student_id)
        .order_by(WeakPointRecord.wrong_count.desc(), WeakPointRecord.updated_at.desc())
        .limit(limit)
        .all()
    )
    return [row[0] for row in rows if row[0]]


def list_students(
    db: Session,
    keyword: str | None = None,
    course_id: str | None = None,
    weak_point: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> dict[str, Any]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    query = db.query(User).filter(User.role == Role.STUDENT.value)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(User.username.like(like), User.name.like(like), User.phone.like(like), User.email.like(like)))
    if course_id:
        query = query.filter(
            User.id.in_(
                db.query(StudentLearningContext.student_id)
                .filter(StudentLearningContext.course_id == course_id)
            )
        )
    if weak_point:
        query = query.filter(
            User.id.in_(
                db.query(WeakPointRecord.student_id)
                .filter(WeakPointRecord.knowledge_point.like(f"%{weak_point}%"))
            )
        )

    total = query.count()
    students = (
        query.order_by(User.created_at.desc(), User.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = []
    for student in students:
        sid = _student_key(student)
        profile = db.query(StudentLearningProfile).filter(StudentLearningProfile.student_id == sid).first()
        major, grade = _major_and_grade(profile)
        items.append(
            {
                "student_id": sid,
                "name": student.name or student.username,
                "major": major,
                "grade": grade,
                "target_course": _target_course(db, sid),
                "completion_rate": _round_rate(db.query(func.avg(LearningPath.progress)).filter(LearningPath.student_id == sid).scalar()),
                "accuracy_rate": _round_rate(db.query(func.avg(ExerciseSubmission.accuracy)).filter(ExerciseSubmission.student_id == sid).scalar()),
                "weak_points": _weak_point_names(db, sid),
            }
        )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def get_student_profile(db: Session, student_id: str) -> dict[str, Any]:
    student = _get_student(db, student_id)
    sid = _student_key(student)
    profile = db.query(StudentLearningProfile).filter(StudentLearningProfile.student_id == sid).first()
    major, grade = _major_and_grade(profile)
    mastery_rows = (
        db.query(MasteryRecord)
        .filter(MasteryRecord.student_id == sid)
        .order_by(MasteryRecord.updated_at.desc())
        .all()
    )
    return {
        "student_id": sid,
        "name": student.name or student.username,
        "major": major,
        "grade": grade,
        "learning_preferences": profile.learning_preferences_json if profile else [],
        "weaknesses": profile.general_challenges_json if profile else [],
        "mastery": [
            {
                "course_id": item.course_id,
                "knowledge_point": item.knowledge_point,
                "score": item.score,
                "source": item.source,
                "updated_at": _iso(item.updated_at),
            }
            for item in mastery_rows
        ],
        "profile": {
            "summary": profile.summary if profile else None,
            "preferred_pace": profile.preferred_pace if profile else None,
            "learning_habits": profile.learning_habits_json if profile else [],
            "motivation_factors": profile.motivation_factors_json if profile else [],
            "general_strengths": profile.general_strengths_json if profile else [],
            "confidence": profile.confidence_json if profile else {},
            "last_updated": _iso(profile.last_updated) if profile else None,
        },
    }


def get_student_learning_path(db: Session, student_id: str) -> dict[str, Any]:
    student = _get_student(db, student_id)
    sid = _student_key(student)
    paths = (
        db.query(LearningPath)
        .filter(LearningPath.student_id == sid)
        .order_by(LearningPath.updated_at.desc())
        .all()
    )
    return {
        "student_id": sid,
        "paths": [_serialize_path(db, path) for path in paths],
    }


def get_student_evaluation(db: Session, student_id: str) -> dict[str, Any]:
    student = _get_student(db, student_id)
    sid = _student_key(student)
    return {
        "student_id": sid,
        "completion_rate": _round_rate(db.query(func.avg(LearningPath.progress)).filter(LearningPath.student_id == sid).scalar()),
        "accuracy_rate": _round_rate(db.query(func.avg(ExerciseSubmission.accuracy)).filter(ExerciseSubmission.student_id == sid).scalar()),
        "study_hours": _round_rate((db.query(func.coalesce(func.sum(StudyRecord.study_minutes), 0)).filter(StudyRecord.student_id == sid).scalar() or 0) / 60),
        "weak_points": [
            {
                "course_id": item.course_id,
                "knowledge_point": item.knowledge_point,
                "mastery_score": item.mastery_score,
                "wrong_count": item.wrong_count or 0,
                "reason": item.reason,
                "suggested_action": item.suggested_action,
                "updated_at": _iso(item.updated_at),
            }
            for item in (
                db.query(WeakPointRecord)
                .filter(WeakPointRecord.student_id == sid)
                .order_by(WeakPointRecord.updated_at.desc())
                .all()
            )
        ],
        "mastery": [
            {
                "course_id": item.course_id,
                "knowledge_point": item.knowledge_point,
                "score": item.score,
                "updated_at": _iso(item.updated_at),
            }
            for item in (
                db.query(MasteryRecord)
                .filter(MasteryRecord.student_id == sid)
                .order_by(MasteryRecord.updated_at.desc())
                .all()
            )
        ],
        "reports": [
            {
                "report_id": item.id,
                "course_id": item.course_id,
                "range": item.report_range,
                "completion_rate": item.completion_rate,
                "accuracy_rate": item.accuracy_rate,
                "study_hours": item.study_hours,
                "recommendations": item.recommendations_json or [],
                "next_suggestion": item.next_suggestion,
                "created_at": _iso(item.created_at),
            }
            for item in (
                db.query(EvaluationReport)
                .filter(EvaluationReport.student_id == sid)
                .order_by(EvaluationReport.created_at.desc())
                .limit(10)
                .all()
            )
        ],
    }


def _serialize_path(db: Session, path: LearningPath) -> dict[str, Any]:
    tasks = (
        db.query(LearningPathTask)
        .filter(LearningPathTask.path_id == path.id)
        .order_by(LearningPathTask.day_no.asc(), LearningPathTask.created_at.asc())
        .all()
    )
    return {
        "path_id": path.id,
        "course_id": path.course_id,
        "title": path.title,
        "goal": path.goal,
        "duration_days": path.duration_days,
        "daily_minutes": path.daily_minutes,
        "progress": path.progress,
        "status": path.status,
        "created_at": _iso(path.created_at),
        "updated_at": _iso(path.updated_at),
        "tasks": [
            {
                "task_id": task.id,
                "day_no": task.day_no,
                "topic": task.topic,
                "description": task.description,
                "estimated_minutes": task.estimated_minutes,
                "resource_ids": task.resource_ids_json or [],
                "status": task.status,
                "completed_at": _iso(task.completed_at),
            }
            for task in tasks
        ],
    }
