import uuid
from typing import Any

from fastapi import status
from sqlalchemy.orm import Session

from app.models.course_structure import CourseChapter
from app.models.exercise import SectionExerciseAnswer, SectionExerciseSubmission
from app.models.user import User
from app.utils.response import AppException, ErrorCode


def submit_section_exercise(
    db: Session,
    current_user: User,
    course_id: str,
    section_id: str,
    payload: Any,
) -> dict[str, Any]:
    _ensure_section_exists(db, course_id, section_id)

    answers = payload.answers
    total = len(answers)
    correct = sum(1 for item in answers if item.is_correct)
    incorrect = total - correct
    score = round(correct * 100 / total) if total else 0
    submit_id = "sub_" + uuid.uuid4().hex[:12]
    user_id = str(current_user.id)

    db.add(
        SectionExerciseSubmission(
            submit_id=submit_id,
            user_id=user_id,
            course_id=course_id,
            section_id=section_id,
            total_count=total,
            correct_count=correct,
            incorrect_count=incorrect,
            score=score,
        )
    )
    for item in answers:
        db.add(
            SectionExerciseAnswer(
                submit_id=submit_id,
                exercise_id=item.exercise_id,
                type=item.type,
                user_answer=item.user_answer,
                is_correct=1 if item.is_correct else 0,
            )
        )
    db.commit()

    return {
        "submit_id": submit_id,
        "total": total,
        "correct": correct,
        "incorrect": incorrect,
        "score": score,
    }


def get_latest_section_exercise(
    db: Session,
    current_user: User,
    course_id: str,
    section_id: str,
) -> dict[str, Any] | None:
    _ensure_section_exists(db, course_id, section_id)

    submission = (
        db.query(SectionExerciseSubmission)
        .filter(
            SectionExerciseSubmission.user_id == str(current_user.id),
            SectionExerciseSubmission.course_id == course_id,
            SectionExerciseSubmission.section_id == section_id,
        )
        .order_by(
            SectionExerciseSubmission.created_at.desc(),
            SectionExerciseSubmission.id.desc(),
        )
        .first()
    )
    if submission is None:
        return None

    answers = (
        db.query(SectionExerciseAnswer)
        .filter(SectionExerciseAnswer.submit_id == submission.submit_id)
        .order_by(SectionExerciseAnswer.id.asc())
        .all()
    )
    return {
        "submit_id": submission.submit_id,
        "total": submission.total_count,
        "correct": submission.correct_count,
        "incorrect": submission.incorrect_count,
        "score": submission.score,
        "answers": [
            {
                "exercise_id": item.exercise_id,
                "type": item.type,
                "user_answer": item.user_answer,
                "is_correct": bool(item.is_correct),
            }
            for item in answers
        ],
        "submitted_at": submission.created_at,
    }


def _ensure_section_exists(db: Session, course_id: str, section_id: str) -> None:
    exists = (
        db.query(CourseChapter.id)
        .filter(
            CourseChapter.course_id == course_id,
            CourseChapter.id == section_id,
        )
        .first()
    )
    if exists is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="小节不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )
