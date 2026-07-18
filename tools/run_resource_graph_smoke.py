"""Run one real database-backed PPT task against existing local course data."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from sqlalchemy import func

from app.agents.resource_generation.graph import ResourceGenerationGraphService
from app.db.session import SessionLocal
from app.models.course import Course
from app.models.course_structure import CourseChapter, KnowledgeChunk, KnowledgePoint
from app.models.resource_agent import LearningResource, ResourceGenerationTask
from app.models.user import User


def main() -> None:
    db = SessionLocal()
    try:
        student = db.query(User).filter(User.role == "student").order_by(User.id).first()
        if student is None:
            raise RuntimeError("本地数据库没有学生用户")
        course = (
            db.query(Course)
            .join(
                KnowledgeChunk,
                (KnowledgeChunk.course_id == Course.course_id) & (KnowledgeChunk.deleted.is_(False)),
            )
            .group_by(Course.course_id)
            .order_by(func.count(KnowledgeChunk.id).desc())
            .first()
        )
        if course is None:
            raise RuntimeError("本地数据库没有已索引课程")
        chapter = (
            db.query(CourseChapter)
            .filter(CourseChapter.course_id == course.course_id, CourseChapter.level == 1)
            .order_by(CourseChapter.sort_order)
            .first()
        )
        if chapter is None:
            raise RuntimeError("课程没有一级章节")
        section = (
            db.query(CourseChapter)
            .filter(CourseChapter.course_id == course.course_id, CourseChapter.parent_id == chapter.id)
            .order_by(CourseChapter.sort_order)
            .first()
        )
        section_id = section.id if section else chapter.id
        points = (
            db.query(KnowledgePoint)
            .filter(KnowledgePoint.course_id == course.course_id, KnowledgePoint.chapter_id == section_id)
            .order_by(KnowledgePoint.sort_order)
            .limit(4)
            .all()
        )
        task_id = str(uuid.uuid4())
        task = ResourceGenerationTask(
            id=task_id,
            student_id=str(student.id),
            course_id=course.course_id,
            chapter_id=chapter.id,
            section_id=section_id,
            resource_type="ppt",
            generation_scope="section",
            knowledge_point_ids_json=[point.id for point in points],
            user_request="数据库与 LangGraph 端到端验证课件",
            knowledge_point=points[0].name if points else (section.title if section else chapter.title),
            goal="基于课程知识块生成结构清晰的互动课件",
            resource_types_json=["ppt"],
            difficulty="基础",
            status="queued",
            progress=0,
            current_step="端到端验证任务已进入队列",
        )
        db.add(task)
        db.commit()
        result = ResourceGenerationGraphService(db).run(task_id)
        db.refresh(task)
        resource = db.get(LearningResource, result["resource_ids"][0])
        artifacts = (task.artifacts_json or {}).get(resource.id, {})
        print(json.dumps({
            "task_id": task.id,
            "task_status": task.status,
            "task_progress": task.progress,
            "resource_id": resource.id,
            "course_id": course.course_id,
            "course_name": course.name,
            "chapter_id": chapter.id,
            "section_id": section_id,
            "generation_mode": resource.generation_mode,
            "renderer": (resource.content_json or {}).get("visualization", {}).get("renderer"),
            "slide_count": (resource.content_json or {}).get("visualization", {}).get("slide_count"),
            "html_exists": Path(artifacts.get("html_path", "missing")).is_file(),
            "cover_exists": Path(artifacts.get("cover_path", "missing")).is_file(),
            "review_score": resource.review_score,
        }, ensure_ascii=True, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
