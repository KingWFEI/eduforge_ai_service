from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agents.student_learning_content_agent import StudentLearningContentAgent
from app.models.course import Course
from app.models.course_structure import CourseChapter, SectionRecommendation, StudentSectionProgress
from app.models.evaluation import WeakPointRecord
from app.models.exercise import SectionExerciseSubmission
from app.models.other import StudyRecord
from app.utils.response import AppException, ErrorCode


DEFAULT_SECTION_MINUTES = 30
RESOURCE_ESTIMATED_MINUTES = {
    "illustration": 15,
    "code_case": 30,
    "exercise": 10,
    "mind_map": 8,
}


def get_course_overview(db: Session, course_id: str, student_id: str) -> dict[str, Any]:
    course = _load_course(db, course_id)
    syllabus = _load_ordered_syllabus(db, course.course_id)
    progress_by_section = _load_progress(db, course.course_id, student_id, syllabus["section_ids"])
    current_section = _select_current_section(syllabus["sections"], progress_by_section)
    current_chapter = (
        syllabus["chapter_by_id"].get(current_section.parent_id)
        if current_section is not None
        else None
    )
    current_progress = (
        progress_by_section.get(current_section.id)
        if current_section is not None
        else None
    )
    chapter_section_ids = [
        item.id
        for item in syllabus["sections_by_chapter"].get(current_chapter.id if current_chapter else "", [])
    ]

    progress_summary = _build_progress_summary(
        db=db,
        course_id=course.course_id,
        student_id=student_id,
        chapters=syllabus["chapters"],
        sections_by_chapter=syllabus["sections_by_chapter"],
        progress_by_section=progress_by_section,
    )
    weak_points = _load_weak_points(db, course.course_id, student_id)
    recommended_resources = _build_recommended_resources(
        db=db,
        course_id=course.course_id,
        student_id=student_id,
        section=current_section,
    )

    section_progress = _normalize_progress(current_progress.progress if current_progress else 0.0)
    return {
        "continue_learning": {
            "chapter_id": current_chapter.id if current_chapter else None,
            "chapter_name": current_chapter.title if current_chapter else None,
            "section_id": current_section.id if current_section else None,
            "section_name": current_section.title if current_section else None,
            "progress": section_progress,
            "last_study_time": current_progress.last_study_at if current_progress else None,
            "estimated_remaining_minutes": _remaining_minutes(section_progress),
            "section_ids": chapter_section_ids,
        },
        "progress": progress_summary,
        "ai_suggestion": {
            "weak_points": weak_points,
            "suggestion": _build_suggestion(weak_points, recommended_resources),
            "next_task": _build_next_task(current_section),
        },
        "recent_learning": _build_recent_learning(db, course.course_id, student_id),
        "recommended_resources": recommended_resources,
    }


def _load_course(db: Session, course_id: str) -> Course:
    course = db.query(Course).filter(Course.course_id == course_id).first()
    if course is None and course_id.isdigit():
        course = db.query(Course).filter(Course.id == int(course_id)).first()
    if course is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="课程不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return course


def _load_ordered_syllabus(db: Session, course_id: str) -> dict[str, Any]:
    rows = (
        db.query(CourseChapter)
        .filter(CourseChapter.course_id == course_id)
        .order_by(CourseChapter.sort_order.asc(), CourseChapter.created_at.asc())
        .all()
    )
    chapter_by_id = {item.id: item for item in rows}
    chapters = [
        item
        for item in rows
        if item.parent_id is None or item.parent_id not in chapter_by_id
    ]
    sections_by_chapter: dict[str, list[CourseChapter]] = {chapter.id: [] for chapter in chapters}
    for item in rows:
        if item.parent_id in sections_by_chapter:
            sections_by_chapter[item.parent_id].append(item)
    sections = [
        section
        for chapter in chapters
        for section in sections_by_chapter.get(chapter.id, [])
    ]
    return {
        "chapters": chapters,
        "chapter_by_id": chapter_by_id,
        "sections": sections,
        "section_ids": [item.id for item in sections],
        "sections_by_chapter": sections_by_chapter,
    }


def _load_progress(
    db: Session,
    course_id: str,
    student_id: str,
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


def _select_current_section(
    sections: list[CourseChapter],
    progress_by_section: dict[str, StudentSectionProgress],
) -> CourseChapter | None:
    for section in sections:
        progress = progress_by_section.get(section.id)
        if progress is None or _normalize_progress(progress.progress) < 1:
            return section
    return None


def _build_progress_summary(
    db: Session,
    course_id: str,
    student_id: str,
    chapters: list[CourseChapter],
    sections_by_chapter: dict[str, list[CourseChapter]],
    progress_by_section: dict[str, StudentSectionProgress],
) -> dict[str, Any]:
    section_ids = [
        section.id
        for sections in sections_by_chapter.values()
        for section in sections
    ]
    section_progress_values = [
        _normalize_progress(progress_by_section.get(section_id).progress if progress_by_section.get(section_id) else 0)
        for section_id in section_ids
    ]
    completed_sections = sum(
        1
        for value in section_progress_values
        if value >= 1
    )
    completed_chapters = 0
    for chapter in chapters:
        chapter_sections = sections_by_chapter.get(chapter.id, [])
        if chapter_sections and all(
            _normalize_progress(
                progress_by_section.get(section.id).progress if progress_by_section.get(section.id) else 0
            ) >= 1
            for section in chapter_sections
        ):
            completed_chapters += 1

    total_minutes = (
        db.query(func.coalesce(func.sum(StudyRecord.study_minutes), 0))
        .filter(
            StudyRecord.student_id == student_id,
            StudyRecord.course_id == course_id,
        )
        .scalar()
        or 0
    )
    return {
        "total_progress": round(sum(section_progress_values) / len(section_progress_values), 4) if section_progress_values else 0.0,
        "completed_chapters": completed_chapters,
        "total_chapters": len(chapters),
        "total_study_hours": round(float(total_minutes or 0) / 60, 2),
        "streak_days": _streak_days(db, course_id, student_id),
    }


def _streak_days(db: Session, course_id: str, student_id: str) -> int:
    rows = (
        db.query(func.date(StudyRecord.created_at))
        .filter(
            StudyRecord.student_id == student_id,
            StudyRecord.course_id == course_id,
        )
        .distinct()
        .all()
    )
    studied_dates = {
        item[0] if isinstance(item[0], date) else date.fromisoformat(str(item[0]))
        for item in rows
        if item[0]
    }
    if not studied_dates:
        return 0

    current = date.today()
    if current not in studied_dates:
        current = max(studied_dates)
    streak = 0
    while current in studied_dates:
        streak += 1
        current = date.fromordinal(current.toordinal() - 1)
    return streak


def _load_weak_points(db: Session, course_id: str, student_id: str) -> list[str]:
    rows = (
        db.query(WeakPointRecord.knowledge_point)
        .filter(
            WeakPointRecord.student_id == student_id,
            WeakPointRecord.course_id == course_id,
        )
        .order_by(WeakPointRecord.wrong_count.desc(), WeakPointRecord.updated_at.desc())
        .limit(3)
        .all()
    )
    return [item[0] for item in rows if item[0]]


def _build_recommended_resources(
    db: Session,
    course_id: str,
    student_id: str,
    section: CourseChapter | None,
) -> list[dict[str, Any]]:
    if section is None:
        return []
    cached = (
        db.query(SectionRecommendation)
        .filter(
            SectionRecommendation.user_id == student_id,
            SectionRecommendation.course_id == course_id,
            SectionRecommendation.section_id == section.id,
        )
        .first()
    )
    shells = cached.resources_json if cached and isinstance(cached.resources_json, list) else None
    resources = StudentLearningContentAgent.normalize_resource_shells(
        shells,
        section_id=section.id,
        title=section.title,
    )
    return [
        {
            "title": item.get("title") or f"{section.title}学习资源",
            "type": item.get("type") or "illustration",
            "reason": "根据当前学习进度推荐",
            "estimated_time_minutes": RESOURCE_ESTIMATED_MINUTES.get(item.get("type"), 15),
        }
        for item in resources[:2]
    ]


def _build_suggestion(weak_points: list[str], resources: list[dict[str, Any]]) -> str:
    if weak_points:
        return f"建议先复习{weak_points[0]}，再结合练习检查掌握情况。"
    if resources:
        return "建议先完成当前小节学习，再结合推荐资源巩固核心概念。"
    return "建议按课程目录继续学习，并及时完成随堂练习。"


def _build_next_task(section: CourseChapter | None) -> str:
    if section is None:
        return "本课程已完成，可以回顾错题和薄弱知识点。"
    return f"完成「{section.title}」小节的学习与练习"


def _build_recent_learning(db: Session, course_id: str, student_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    progress_rows = (
        db.query(StudentSectionProgress, CourseChapter)
        .join(CourseChapter, CourseChapter.id == StudentSectionProgress.section_id)
        .filter(
            StudentSectionProgress.student_id == student_id,
            StudentSectionProgress.course_id == course_id,
            StudentSectionProgress.last_study_at.isnot(None),
        )
        .order_by(StudentSectionProgress.last_study_at.desc())
        .limit(3)
        .all()
    )
    for progress, section in progress_rows:
        items.append(
            {
                "type": "section",
                "title": section.title,
                "action": "继续学习" if _normalize_progress(progress.progress) < 1 else "已完成",
                "time_ago": _time_ago(progress.last_study_at),
                "is_incomplete": _normalize_progress(progress.progress) < 1,
                "_sort_time": progress.last_study_at or datetime.min,
            }
        )

    exercise_rows = (
        db.query(SectionExerciseSubmission, CourseChapter)
        .join(CourseChapter, CourseChapter.id == SectionExerciseSubmission.section_id)
        .filter(
            SectionExerciseSubmission.user_id == student_id,
            SectionExerciseSubmission.course_id == course_id,
        )
        .order_by(SectionExerciseSubmission.created_at.desc())
        .limit(2)
        .all()
    )
    for submission, section in exercise_rows:
        items.append(
            {
                "type": "exercise",
                "title": f"{section.title}随堂练习",
                "action": "继续练习" if submission.score < 100 else "已完成练习",
                "time_ago": _time_ago(submission.created_at),
                "is_incomplete": submission.score < 100,
                "_sort_time": submission.created_at or datetime.min,
            }
        )

    items.sort(key=lambda item: _sort_timestamp(item.get("_sort_time")), reverse=True)
    for item in items:
        item.pop("_sort_time", None)
    return items[:5]


def _remaining_minutes(progress: float) -> int:
    return max(0, round(DEFAULT_SECTION_MINUTES * (1 - progress)))


def _normalize_progress(value: float | None) -> float:
    if value is None:
        return 0.0
    return round(max(0.0, min(1.0, float(value))), 4)


def _time_ago(value: datetime | None) -> str:
    if value is None:
        return "未知时间"
    now = datetime.now(value.tzinfo) if value.tzinfo else datetime.now()
    delta = now - value
    minutes = max(0, int(delta.total_seconds() // 60))
    if minutes < 1:
        return "刚刚"
    if minutes < 60:
        return f"{minutes}分钟前"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}小时前"
    days = hours // 24
    if days == 1:
        return "昨天"
    return f"{days}天前"


def _sort_timestamp(value: Any) -> float:
    if not isinstance(value, datetime):
        return 0.0
    return value.timestamp()
