from datetime import datetime, timezone
from typing import Any

from fastapi import status
from sqlalchemy.orm import Session

from app.models.course_structure import CourseChapter, StudentSectionProgress
from app.models.user import User
from app.utils.response import AppException, ErrorCode


def complete_section_learning(
    db: Session,
    current_user: User,
    course_id: str,
    section_id: str,
) -> dict[str, Any]:
    _ensure_section_exists(db, course_id, section_id)

    student_id = str(current_user.id)
    progress = (
        db.query(StudentSectionProgress)
        .filter(
            StudentSectionProgress.student_id == student_id,
            StudentSectionProgress.section_id == section_id,
        )
        .first()
    )
    now = datetime.now(timezone.utc)
    if progress is None:
        db.add(
            StudentSectionProgress(
                student_id=student_id,
                course_id=course_id,
                section_id=section_id,
                progress=1.0,
                status="completed",
                last_study_at=now,
            )
        )
    else:
        progress.course_id = course_id
        progress.progress = 1.0
        progress.status = "completed"
        progress.last_study_at = now
    db.commit()

    return {"progress": 1.0}


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
