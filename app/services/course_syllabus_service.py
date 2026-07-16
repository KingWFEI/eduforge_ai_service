from collections import defaultdict

from fastapi import status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.course_structure import (
    CourseChapter,
    CourseDocument,
    KnowledgePoint,
    StudentSectionProgress,
)
from app.models.exercise import ExerciseSet
from app.models.resource_agent import LearningResource
from app.utils.response import AppException, ErrorCode


DEFAULT_SECTION_ESTIMATED_MINUTES = 30
SECTION_STATUSES = {"completed", "learning", "unlearned", "locked"}


def get_course_syllabus(
    db: Session,
    course_id: str,
    student_id: str,
) -> dict:
    course = db.query(Course).filter(Course.course_id == course_id).first()
    if course is None and course_id.isdigit():
        course = db.query(Course).filter(Course.id == int(course_id)).first()
    if course is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="课程不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    normalized_course_id = course.course_id
    chapter_rows = (
        db.query(CourseChapter)
        .filter(CourseChapter.course_id == normalized_course_id)
        .order_by(
            CourseChapter.sort_order.asc(),
            CourseChapter.created_at.asc(),
        )
        .all()
    )
    chapter_by_id = {item.id: item for item in chapter_rows}
    root_chapters = [
        item
        for item in chapter_rows
        if item.parent_id is None or item.parent_id not in chapter_by_id
    ]
    sections = [
        item
        for item in chapter_rows
        if item.parent_id is not None and item.parent_id in chapter_by_id
    ]
    sections_by_chapter: dict[str, list[CourseChapter]] = defaultdict(list)
    for section in sections:
        sections_by_chapter[section.parent_id].append(section)
    ordered_sections = [
        section
        for chapter in root_chapters
        for section in sections_by_chapter.get(chapter.id, [])
    ]

    section_ids = [item.id for item in sections]
    progress_by_section = _load_progress(
        db=db,
        student_id=student_id,
        course_id=normalized_course_id,
        section_ids=section_ids,
    )
    current_section_id = _select_current_section_id(
        sections=ordered_sections,
        progress_by_section=progress_by_section,
    )
    current_chapter_id = (
        chapter_by_id[current_section_id].parent_id
        if current_section_id in chapter_by_id
        else None
    )

    resource_section_ids = _load_resource_section_ids(
        db=db,
        course_id=normalized_course_id,
        section_ids=section_ids,
    )
    exercise_section_ids = _load_exercise_section_ids(
        db=db,
        course_id=normalized_course_id,
        section_ids=section_ids,
    )

    completed_sections = 0
    chapter_items = []
    for chapter in root_chapters:
        section_items = []
        for section in sections_by_chapter.get(chapter.id, []):
            progress_row = progress_by_section.get(section.id)
            progress = _normalize_progress(
                progress_row.progress if progress_row is not None else 0.0
            )
            section_status = _normalize_section_status(
                status_value=progress_row.status if progress_row is not None else None,
                progress=progress,
                is_current=section.id == current_section_id,
            )
            if section_status == "completed":
                completed_sections += 1
            section_items.append(
                {
                    "section_id": section.id,
                    "section_name": section.title,
                    "description": section.description,
                    "sort_order": section.sort_order or 0,
                    "status": section_status,
                    "progress": progress,
                    "estimated_time_minutes": DEFAULT_SECTION_ESTIMATED_MINUTES,
                    "has_exercise": section.id in exercise_section_ids,
                    "has_resource": section.id in resource_section_ids,
                    "last_study_time": (
                        progress_row.last_study_at
                        if progress_row is not None
                        else None
                    ),
                }
            )

        chapter_progress = _chapter_progress(section_items)
        is_current_chapter = chapter.id == current_chapter_id
        chapter_items.append(
            {
                "chapter_id": chapter.id,
                "chapter_name": chapter.title,
                "description": chapter.description,
                "sort_order": chapter.sort_order or 0,
                "status": _chapter_status(
                    section_items=section_items,
                    is_current=is_current_chapter,
                ),
                "progress": chapter_progress,
                "is_current_chapter": is_current_chapter,
                "current_section_id": (
                    current_section_id if is_current_chapter else None
                ),
                "sections": section_items,
            }
        )

    return {
        "course_id": normalized_course_id,
        "total_chapters": len(chapter_items),
        "total_sections": len(sections),
        "completed_sections": completed_sections,
        "current_chapter_id": current_chapter_id,
        "current_section_id": current_section_id,
        "chapters": chapter_items,
    }


def _load_progress(
    db: Session,
    student_id: str,
    course_id: str,
    section_ids: list[str],
) -> dict[str, StudentSectionProgress]:
    if not section_ids:
        return {}
    rows = (
        db.query(StudentSectionProgress)
        .filter(
            StudentSectionProgress.student_id == student_id,
            StudentSectionProgress.course_id == course_id,
            StudentSectionProgress.section_id.in_(section_ids),
        )
        .all()
    )
    return {item.section_id: item for item in rows}


def _select_current_section_id(
    sections: list[CourseChapter],
    progress_by_section: dict[str, StudentSectionProgress],
) -> str | None:
    if not sections:
        return None

    studied_rows = [
        item
        for item in progress_by_section.values()
        if item.status == "learning" or 0 < _normalize_progress(item.progress) < 1
    ]
    if studied_rows:
        studied_rows.sort(
            key=lambda item: (
                item.last_study_at is not None,
                item.last_study_at,
                item.updated_at,
            ),
            reverse=True,
        )
        return studied_rows[0].section_id

    incomplete_rows = [
        item
        for item in progress_by_section.values()
        if _normalize_progress(item.progress) < 1
    ]
    if incomplete_rows:
        incomplete_ids = {item.section_id for item in incomplete_rows}
        for section in sections:
            if section.id in incomplete_ids:
                return section.id

    for section in sections:
        progress_row = progress_by_section.get(section.id)
        if progress_row is None or _normalize_progress(progress_row.progress) < 1:
            return section.id
    return None


def _load_resource_section_ids(
    db: Session,
    course_id: str,
    section_ids: list[str],
) -> set[str]:
    if not section_ids:
        return set()

    direct_ids = {
        row[0]
        for row in (
            db.query(CourseDocument.chapter_id)
            .filter(
                CourseDocument.course_id == course_id,
                CourseDocument.chapter_id.in_(section_ids),
                CourseDocument.status == "active",
            )
            .distinct()
            .all()
        )
        if row[0]
    }
    generated_ids = {
        row[0]
        for row in (
            db.query(KnowledgePoint.chapter_id)
            .join(
                LearningResource,
                LearningResource.knowledge_point_id == KnowledgePoint.id,
            )
            .filter(
                LearningResource.course_id == course_id,
                KnowledgePoint.chapter_id.in_(section_ids),
                or_(
                    LearningResource.review_status.is_(None),
                    LearningResource.review_status.in_(
                        ["pending", "approved", "auto_passed"]
                    ),
                ),
            )
            .distinct()
            .all()
        )
        if row[0]
    }
    return direct_ids | generated_ids


def _load_exercise_section_ids(
    db: Session,
    course_id: str,
    section_ids: list[str],
) -> set[str]:
    if not section_ids:
        return set()
    return {
        row[0]
        for row in (
            db.query(KnowledgePoint.chapter_id)
            .join(
                ExerciseSet,
                ExerciseSet.knowledge_point_id == KnowledgePoint.id,
            )
            .filter(
                ExerciseSet.course_id == course_id,
                KnowledgePoint.chapter_id.in_(section_ids),
            )
            .distinct()
            .all()
        )
        if row[0]
    }


def _normalize_progress(value: float | None) -> float:
    if value is None:
        return 0.0
    return round(max(0.0, min(1.0, float(value))), 4)


def _normalize_section_status(
    status_value: str | None,
    progress: float,
    is_current: bool,
) -> str:
    if progress >= 1:
        return "completed"
    if is_current or progress > 0:
        return "learning"
    if status_value in SECTION_STATUSES:
        return status_value
    return "unlearned"


def _chapter_progress(section_items: list[dict]) -> float:
    if not section_items:
        return 0.0
    return round(
        sum(item["progress"] for item in section_items) / len(section_items),
        4,
    )


def _chapter_status(section_items: list[dict], is_current: bool) -> str:
    if not section_items:
        return "locked"
    statuses = {item["status"] for item in section_items}
    if statuses == {"completed"}:
        return "completed"
    if is_current or "learning" in statuses:
        return "learning"
    if "completed" in statuses:
        return "review"
    return "locked"
