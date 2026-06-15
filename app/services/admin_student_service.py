from typing import Any

from fastapi import status
from sqlalchemy import false, or_
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.models.evaluation import EvaluationReport, MasteryRecord, WeakPointRecord
from app.models.exercise import ExerciseSubmission, WrongQuestion
from app.models.learning_profile import (
    StudentDomainCompetency,
    StudentLearningContext,
    StudentLearningProfile,
)
from app.models.learning_path import LearningPath, LearningPathTask
from app.models.other import StudyRecord
from app.models.resource_agent import LearningResource, ResourceGenerationTask
from app.models.user import User
from app.utils.response import AppException, ErrorCode


def list_student_learning_data(
    db: Session,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[dict[str, Any]], int]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 50)

    query = db.query(User).filter(User.role == Role.STUDENT.value)
    if keyword:
        like_keyword = f"%{keyword}%"
        query = query.filter(
            or_(
                User.username.like(like_keyword),
                User.name.like(like_keyword),
                User.phone.like(like_keyword),
                User.email.like(like_keyword),
            )
        )

    total = query.count()
    students = (
        query.order_by(User.created_at.desc(), User.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return [_build_student_learning_data(db, student) for student in students], total


def get_student_learning_data(db: Session, student_id: str) -> dict[str, Any]:
    student = _get_student(db, student_id)
    return _build_student_learning_data(db, student)


def _get_student(db: Session, student_id: str) -> User:
    id_filter = User.id == int(student_id) if student_id.isdigit() else false()
    student = db.query(User).filter(id_filter).first()
    if student is None or student.role != Role.STUDENT.value:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="学生不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return student


def _build_student_learning_data(db: Session, student: User) -> dict[str, Any]:
    student_id = str(student.id)
    profile = (
        db.query(StudentLearningProfile)
        .filter(StudentLearningProfile.student_id == student_id)
        .first()
    )

    return {
        "student": _serialize_student(student),
        "profile": _serialize_profile(profile) if profile else None,
        "domain_competencies": [
            _serialize_domain_competency(item)
            for item in (
                db.query(StudentDomainCompetency)
                .filter(StudentDomainCompetency.student_id == student_id)
                .order_by(StudentDomainCompetency.last_updated.desc())
                .all()
            )
        ],
        "learning_contexts": [
            _serialize_learning_context(item)
            for item in (
                db.query(StudentLearningContext)
                .filter(StudentLearningContext.student_id == student_id)
                .order_by(StudentLearningContext.updated_at.desc())
                .all()
            )
        ],
        "weak_points": [
            _serialize_weak_point(item)
            for item in (
                db.query(WeakPointRecord)
                .filter(WeakPointRecord.student_id == student_id)
                .order_by(WeakPointRecord.updated_at.desc())
                .all()
            )
        ],
        "mastery_records": [
            _serialize_mastery_record(item)
            for item in (
                db.query(MasteryRecord)
                .filter(MasteryRecord.student_id == student_id)
                .order_by(MasteryRecord.updated_at.desc())
                .all()
            )
        ],
        "evaluation_reports": [
            _serialize_evaluation_report(item)
            for item in (
                db.query(EvaluationReport)
                .filter(EvaluationReport.student_id == student_id)
                .order_by(EvaluationReport.created_at.desc())
                .all()
            )
        ],
        "learning_paths": [
            _serialize_learning_path(db, item)
            for item in (
                db.query(LearningPath)
                .filter(LearningPath.student_id == student_id)
                .order_by(LearningPath.updated_at.desc())
                .all()
            )
        ],
        "exercise_submissions": [
            _serialize_exercise_submission(item)
            for item in (
                db.query(ExerciseSubmission)
                .filter(ExerciseSubmission.student_id == student_id)
                .order_by(ExerciseSubmission.submitted_at.desc())
                .all()
            )
        ],
        "wrong_questions": [
            _serialize_wrong_question(item)
            for item in (
                db.query(WrongQuestion)
                .filter(WrongQuestion.student_id == student_id)
                .order_by(WrongQuestion.last_wrong_at.desc())
                .all()
            )
        ],
        "study_records": [
            _serialize_study_record(item)
            for item in (
                db.query(StudyRecord)
                .filter(StudyRecord.student_id == student_id)
                .order_by(StudyRecord.created_at.desc())
                .all()
            )
        ],
        "resources": [
            _serialize_resource(item)
            for item in (
                db.query(LearningResource)
                .filter(LearningResource.student_id == student_id)
                .order_by(LearningResource.created_at.desc())
                .all()
            )
        ],
        "resource_generation_tasks": [
            _serialize_resource_task(item)
            for item in (
                db.query(ResourceGenerationTask)
                .filter(ResourceGenerationTask.student_id == student_id)
                .order_by(ResourceGenerationTask.created_at.desc())
                .all()
            )
        ],
    }


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _serialize_student(student: User) -> dict[str, Any]:
    return {
        "student_id": str(student.id),
        "username": student.username,
        "name": student.name,
        "phone": student.phone,
        "email": student.email,
        "avatar_url": student.avatar_url,
        "status": student.status,
        "is_active": student.is_active,
        "created_at": _iso(student.created_at),
        "last_login_at": _iso(student.last_login_at),
    }


def _serialize_profile(profile: StudentLearningProfile) -> dict[str, Any]:
    return {
        "profile_id": profile.id,
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
        "version": profile.version,
        "source": profile.source,
        "last_updated": _iso(profile.last_updated),
    }


def _serialize_domain_competency(item: StudentDomainCompetency) -> dict[str, Any]:
    return {
        "id": item.id,
        "domain_type": item.domain_type,
        "domain_id": item.domain_id,
        "domain_name": item.domain_name,
        "competency_level": item.competency_level,
        "strengths": item.strengths_json or [],
        "weaknesses": item.weaknesses_json or [],
        "knowledge_state": item.knowledge_state_json or {},
        "evidence": item.evidence_json or [],
        "confidence": item.confidence,
        "last_updated": _iso(item.last_updated),
    }


def _serialize_learning_context(item: StudentLearningContext) -> dict[str, Any]:
    return {
        "id": item.id,
        "course_id": item.course_id,
        "course_name": item.course_name,
        "learning_goals": item.learning_goals_json or [],
        "time_budget": item.time_budget_json or {},
        "status": item.status,
        "started_at": _iso(item.started_at),
        "completed_at": _iso(item.completed_at),
        "updated_at": _iso(item.updated_at),
    }


def _serialize_weak_point(item: WeakPointRecord) -> dict[str, Any]:
    return {
        "id": item.id,
        "course_id": item.course_id,
        "knowledge_point": item.knowledge_point,
        "mastery_score": item.mastery_score,
        "wrong_count": item.wrong_count or 0,
        "reason": item.reason,
        "suggested_action": item.suggested_action,
        "source": item.source,
        "updated_at": _iso(item.updated_at),
    }


def _serialize_mastery_record(item: MasteryRecord) -> dict[str, Any]:
    return {
        "id": item.id,
        "course_id": item.course_id,
        "knowledge_point_id": item.knowledge_point_id,
        "knowledge_point": item.knowledge_point,
        "score": item.score,
        "source": item.source,
        "updated_at": _iso(item.updated_at),
    }


def _serialize_evaluation_report(item: EvaluationReport) -> dict[str, Any]:
    return {
        "id": item.id,
        "course_id": item.course_id,
        "report_range": item.report_range,
        "completion_rate": item.completion_rate,
        "accuracy_rate": item.accuracy_rate,
        "study_hours": item.study_hours,
        "mastery": item.mastery_json or [],
        "good_points": item.good_points_json or [],
        "weak_points": item.weak_points_json or [],
        "recommendations": item.recommendations_json or [],
        "next_suggestion": item.next_suggestion,
        "created_at": _iso(item.created_at),
    }


def _serialize_learning_path(db: Session, item: LearningPath) -> dict[str, Any]:
    tasks = (
        db.query(LearningPathTask)
        .filter(LearningPathTask.path_id == item.id)
        .order_by(LearningPathTask.day_no.asc(), LearningPathTask.created_at.asc())
        .all()
    )
    return {
        "path_id": item.id,
        "course_id": item.course_id,
        "title": item.title,
        "goal": item.goal,
        "duration_days": item.duration_days,
        "daily_minutes": item.daily_minutes,
        "progress": item.progress,
        "status": item.status,
        "plan": item.plan_json or {},
        "created_by_task_id": item.created_by_task_id,
        "created_at": _iso(item.created_at),
        "updated_at": _iso(item.updated_at),
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
                "created_at": _iso(task.created_at),
            }
            for task in tasks
        ],
    }


def _serialize_exercise_submission(item: ExerciseSubmission) -> dict[str, Any]:
    return {
        "submission_id": item.id,
        "exercise_set_id": item.exercise_set_id,
        "resource_id": item.resource_id,
        "score": item.score,
        "accuracy": item.accuracy,
        "correct_count": item.correct_count,
        "total_count": item.total_count,
        "duration_seconds": item.duration_seconds,
        "weak_points": item.weak_points_json or [],
        "analysis": item.analysis_json or {},
        "submitted_at": _iso(item.submitted_at),
    }


def _serialize_wrong_question(item: WrongQuestion) -> dict[str, Any]:
    return {
        "id": item.id,
        "question_id": item.question_id,
        "knowledge_point": item.knowledge_point,
        "wrong_count": item.wrong_count or 0,
        "last_wrong_at": _iso(item.last_wrong_at),
        "mastered": bool(item.mastered),
        "created_at": _iso(item.created_at),
    }


def _serialize_study_record(item: StudyRecord) -> dict[str, Any]:
    return {
        "id": item.id,
        "course_id": item.course_id,
        "resource_id": item.resource_id,
        "path_task_id": item.path_task_id,
        "action_type": item.action_type,
        "study_minutes": item.study_minutes or 0,
        "progress_delta": item.progress_delta,
        "created_at": _iso(item.created_at),
    }


def _serialize_resource(item: LearningResource) -> dict[str, Any]:
    return {
        "resource_id": item.id,
        "course_id": item.course_id,
        "knowledge_point_id": item.knowledge_point_id,
        "title": item.title,
        "type": item.type,
        "difficulty": item.difficulty,
        "description": item.description,
        "reason": item.reason,
        "content_text": item.content_text,
        "content_json": item.content_json or {},
        "source": item.source,
        "review_status": item.review_status,
        "safety_score": item.safety_score,
        "hallucination_risk": item.hallucination_risk,
        "generated_by_task_id": item.generated_by_task_id,
        "created_at": _iso(item.created_at),
        "updated_at": _iso(item.updated_at),
    }


def _serialize_resource_task(item: ResourceGenerationTask) -> dict[str, Any]:
    return {
        "task_id": item.id,
        "course_id": item.course_id,
        "knowledge_point": item.knowledge_point,
        "goal": item.goal,
        "resource_types": item.resource_types_json or [],
        "difficulty": item.difficulty,
        "status": item.status,
        "progress": item.progress or 0,
        "current_step": item.current_step,
        "result_resource_ids": item.result_resource_ids_json or [],
        "error_message": item.error_message,
        "created_at": _iso(item.created_at),
        "updated_at": _iso(item.updated_at),
    }
