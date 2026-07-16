import asyncio
import json
from typing import Any

from fastapi import status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agents.section_resource_recommendation_agent import SectionResourceRecommendationAgent
from app.models.course_structure import SectionRecommendation
from app.models.student_profile import StudentProfile
from app.models.user import User
from app.utils.response import AppException, ErrorCode


def get_section_recommendations(
    db: Session,
    current_user: User,
    course_id: str,
    section_id: str,
    chapter_id: str | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    user_id = str(current_user.id)
    cached = _load_cached_recommendation(
        db=db,
        user_id=user_id,
        course_id=course_id,
        section_id=section_id,
    )
    if cached is not None and cached.get("_personalized") and not refresh:
        return {"suggestion": cached["suggestion"], "resources": cached["resources"]}

    section = _load_section(db, course_id, section_id, chapter_id)
    learning_content = _load_section_learning_content(db, course_id, section_id)
    profile = _load_student_profile(db, user_id)
    progress = _load_course_progress(db, user_id, course_id, section_id)
    recommendation_input = {
        "section": section,
        "learning_content": learning_content,
        "profile": profile,
        "progress": progress,
    }
    try:
        recommendation = asyncio.run(
            SectionResourceRecommendationAgent().run(recommendation_input)
        )
    except Exception:
        recommendation = SectionResourceRecommendationAgent.fallback(recommendation_input)
    resources = recommendation["resources"]
    suggestion = recommendation["suggestion"]
    data = {
        "suggestion": suggestion,
        "resources": resources,
    }
    _save_recommendation(
        db=db,
        user_id=user_id,
        course_id=course_id,
        section_id=section_id,
        chapter_id=section.get("chapter_id") or chapter_id,
        suggestion=suggestion,
        resources=resources,
    )
    return data


def _load_cached_recommendation(
    db: Session,
    user_id: str,
    course_id: str,
    section_id: str,
) -> dict[str, Any] | None:
    row = (
        db.query(SectionRecommendation)
        .filter(
            SectionRecommendation.user_id == user_id,
            SectionRecommendation.course_id == course_id,
            SectionRecommendation.section_id == section_id,
        )
        .first()
    )
    if row is None:
        return None

    resources = row.resources_json or []
    if not isinstance(resources, list):
        resources = []
    return {
        "suggestion": row.suggestion,
        "resources": resources,
        "_personalized": bool(resources) and all(
            isinstance(item, dict) and bool(item.get("reason")) for item in resources
        ),
    }


def _save_recommendation(
    db: Session,
    user_id: str,
    course_id: str,
    section_id: str,
    chapter_id: str | None,
    suggestion: str,
    resources: list[dict[str, str]],
) -> None:
    existing = (
        db.query(SectionRecommendation)
        .filter(
            SectionRecommendation.user_id == user_id,
            SectionRecommendation.course_id == course_id,
            SectionRecommendation.section_id == section_id,
        )
        .first()
    )
    if existing is None:
        db.add(
            SectionRecommendation(
                user_id=user_id,
                course_id=course_id,
                section_id=section_id,
                chapter_id=chapter_id,
                suggestion=suggestion,
                resources_json=resources,
            )
        )
    else:
        existing.chapter_id = chapter_id
        existing.suggestion = suggestion
        existing.resources_json = resources
    db.commit()


def _load_section(
    db: Session,
    course_id: str,
    section_id: str,
    chapter_id: str | None,
) -> dict[str, Any]:
    row = db.execute(
        text(
            """
            SELECT
                s.id AS section_id,
                s.title AS section_title,
                s.description AS section_description,
                p.id AS chapter_id,
                p.title AS chapter_title,
                p.description AS chapter_description
            FROM course_chapters s
            LEFT JOIN course_chapters p ON p.id = s.parent_id
            WHERE s.course_id = :course_id
              AND s.id = :section_id
              AND (:chapter_id IS NULL OR s.parent_id = :chapter_id OR p.id = :chapter_id)
            LIMIT 1
            """
        ),
        {"course_id": course_id, "section_id": section_id, "chapter_id": chapter_id},
    ).mappings().first()
    if row is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="小节不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    point_rows = db.execute(
        text(
            """
            SELECT name, description, difficulty
            FROM knowledge_points
            WHERE course_id = :course_id
              AND chapter_id = :section_id
            ORDER BY sort_order ASC, created_at ASC
            LIMIT 5
            """
        ),
        {"course_id": course_id, "section_id": section_id},
    ).mappings().all()
    section = dict(row)
    section["knowledge_points"] = [dict(item) for item in point_rows]
    return section


def _load_student_profile(db: Session, student_id: str) -> dict[str, Any]:
    profile = db.query(StudentProfile).filter(StudentProfile.student_id == student_id).first()
    if profile is None:
        return {
            "learning_preferences": ["图解讲解"],
            "coding_level": "一般",
            "course_level": "入门",
            "weaknesses": [],
            "summary": "暂未生成学习画像，使用默认画像。",
        }
    return {
        "learning_goals": profile.learning_goals_json or [],
        "coding_level": profile.coding_level,
        "math_level": profile.math_level,
        "course_level": profile.course_level,
        "learning_preferences": profile.learning_preferences_json or [],
        "weaknesses": profile.weaknesses_json or [],
        "summary": profile.summary,
    }


def _load_section_learning_content(
    db: Session,
    course_id: str,
    section_id: str,
) -> dict[str, Any]:
    row = db.execute(
        text(
            """
            SELECT id, title, content_markdown, content_json, updated_at
            FROM course_section_learning_contents
            WHERE course_id = :course_id
              AND section_id = :section_id
              AND status IN ('generated', 'completed')
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"course_id": course_id, "section_id": section_id},
    ).mappings().first()
    if row is None:
        return {
            "content_id": None,
            "title": None,
            "content_markdown": None,
            "content_json": {},
        }
    content_json = row["content_json"]
    if isinstance(content_json, str):
        try:
            content_json = json.loads(content_json)
        except json.JSONDecodeError:
            content_json = {}
    return {
        "content_id": row["id"],
        "title": row["title"],
        "content_markdown": row["content_markdown"],
        "content_json": content_json if isinstance(content_json, dict) else {},
    }


def _load_course_progress(
    db: Session,
    student_id: str,
    course_id: str,
    section_id: str,
) -> dict[str, Any]:
    current = db.execute(
        text(
            """
            SELECT progress, status, last_study_at
            FROM student_section_progress
            WHERE student_id = :student_id
              AND course_id = :course_id
              AND section_id = :section_id
            LIMIT 1
            """
        ),
        {"student_id": student_id, "course_id": course_id, "section_id": section_id},
    ).mappings().first()
    aggregate = db.execute(
        text(
            """
            SELECT
                COUNT(*) AS total_sections,
                SUM(CASE WHEN status = 'completed' OR progress >= 1 THEN 1 ELSE 0 END) AS completed_sections,
                AVG(progress) AS average_progress
            FROM student_section_progress
            WHERE student_id = :student_id
              AND course_id = :course_id
            """
        ),
        {"student_id": student_id, "course_id": course_id},
    ).mappings().first()
    return {
        "current_section": {
            "progress": float(current["progress"] or 0) if current else 0,
            "status": current["status"] if current else "unlearned",
            "last_study_at": current["last_study_at"].isoformat() if current and current["last_study_at"] else None,
        },
        "course": {
            "total_sections": int(aggregate["total_sections"] or 0) if aggregate else 0,
            "completed_sections": int(aggregate["completed_sections"] or 0) if aggregate else 0,
            "average_progress": float(aggregate["average_progress"] or 0) if aggregate else 0,
        },
    }
