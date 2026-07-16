import json
import logging
import uuid
from types import SimpleNamespace
from typing import Any

from fastapi import status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agents.student_learning_content_agent import StudentLearningContentAgent
from app.db.session import SessionLocal
from app.models.resource_agent import AgentTask
from app.models.user import User
from app.services.document_asset_service import append_source_images
from app.services.rag_service import rebuild_course_document_index_with_structure, search_knowledge_chunks
from app.utils.response import AppException, ErrorCode


CONFIRMABLE_DRAFT_STATUSES = {"draft", "draft_generated", "pending_review", "modified"}
CONTENT_GENERATABLE_DRAFT_STATUSES = {
    "confirmed",
    "content_generated",
    "content_partially_generated",
    "failed",
}
TERMINAL_TASK_STATUSES = {"completed", "failed", "cancelled"}
logger = logging.getLogger("app.services.course_content_generation_service")


def _json_loads(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _normalize_draft(draft: dict[str, Any]) -> dict[str, Any]:
    chapters = draft.get("chapters")
    if not isinstance(chapters, list):
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message="课程结构草稿格式错误：缺少 chapters 数组",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    normalized_chapters = []
    for chapter in chapters:
        if not isinstance(chapter, dict) or not str(chapter.get("title", "")).strip():
            continue

        sections = []
        raw_sections = chapter.get("sections") or [
            {
                "title": chapter.get("title"),
                "description": chapter.get("description"),
                "knowledge_points": chapter.get("knowledge_points") or [],
            }
        ]
        for section in raw_sections:
            if not isinstance(section, dict) or not str(section.get("title", "")).strip():
                continue
            points = []
            for point in section.get("knowledge_points") or []:
                if not isinstance(point, dict) or not str(point.get("name", "")).strip():
                    continue
                points.append(
                    {
                        "name": str(point["name"]).strip()[:100],
                        "description": str(point.get("description") or "").strip()[:1000] or None,
                        "difficulty": str(point.get("difficulty") or "基础")[:30],
                    }
                )
            sections.append(
                {
                    "title": str(section["title"]).strip()[:200],
                    "description": str(section.get("description") or "").strip()[:1000] or None,
                    "knowledge_points": points,
                }
            )

        normalized_chapters.append(
            {
                "title": str(chapter["title"]).strip()[:200],
                "description": str(chapter.get("description") or "").strip()[:1000] or None,
                "sections": sections,
            }
        )

    if not normalized_chapters:
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message="课程结构草稿中没有有效章节",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return {"chapters": normalized_chapters}


def _load_draft(db: Session, draft_id: str) -> dict[str, Any]:
    row = db.execute(
        text(
            """
            SELECT id, course_id, source_document_ids_json, draft_json, status
            FROM course_structure_drafts
            WHERE id = :draft_id
            LIMIT 1
            """
        ),
        {"draft_id": draft_id},
    ).mappings().first()
    if row is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="课程结构草稿不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return {
        "draft_id": row["id"],
        "course_id": row["course_id"],
        "source_document_ids": _json_loads(row["source_document_ids_json"], []),
        "draft": _normalize_draft(_json_loads(row["draft_json"], {})),
        "status": row["status"],
    }


def _ensure_draft_confirmable(draft: dict[str, Any]) -> None:
    if draft["status"] not in CONFIRMABLE_DRAFT_STATUSES:
        raise AppException(
            code=ErrorCode.CONFLICT,
            message=f"当前草稿状态为 {draft['status']}，不能重复确认并生成学习内容",
            status_code=status.HTTP_409_CONFLICT,
        )


def _ensure_draft_content_generatable(draft: dict[str, Any]) -> None:
    if draft["status"] in {"content_generating"}:
        raise AppException(
            code=ErrorCode.CONFLICT,
            message="章节学习内容正在生成中，请勿重复提交",
            status_code=status.HTTP_409_CONFLICT,
        )
    if draft["status"] not in CONTENT_GENERATABLE_DRAFT_STATUSES:
        raise AppException(
            code=ErrorCode.CONFLICT,
            message="请先确认并保存章节结构，再生成章节学习内容",
            status_code=status.HTTP_409_CONFLICT,
        )


def _task_output(
    draft_id: str,
    course_id: str,
    total_sections: int = 0,
    current_section: str | None = None,
    contents_generated: int = 0,
    contents_failed: int = 0,
    content_ids: list[str] | None = None,
    failed_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "draft_id": draft_id,
        "course_id": course_id,
        "total_sections": total_sections,
        "current_section": current_section,
        "contents_generated": contents_generated,
        "contents_failed": contents_failed,
        "content_ids": content_ids or [],
        "failed_items": failed_items or [],
    }


def _update_agent_task(
    db: Session,
    task_id: str,
    status_value: str | None = None,
    progress: int | None = None,
    current_step: str | None = None,
    output_json: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    assignments = ["updated_at = NOW()"]
    params: dict[str, Any] = {"task_id": task_id}
    if status_value is not None:
        assignments.append("status = :status")
        params["status"] = status_value
    if progress is not None:
        assignments.append("progress = :progress")
        params["progress"] = max(0, min(100, progress))
    if current_step is not None:
        assignments.append("current_step = :current_step")
        params["current_step"] = current_step
    if output_json is not None:
        assignments.append("output_json = :output_json")
        params["output_json"] = json.dumps(output_json, ensure_ascii=False)
    if error_message is not None:
        assignments.append("error_message = :error_message")
        params["error_message"] = error_message

    db.execute(
        text(
            f"""
            UPDATE agent_tasks
            SET {', '.join(assignments)}
            WHERE id = :task_id
            """
        ),
        params,
    )
    db.commit()


def _format_generation_task(row: Any) -> dict[str, Any]:
    output = _json_loads(row["output_json"], {}) or {}
    input_data = _json_loads(row["input_json"], {}) or {}
    return {
        "task_id": row["id"],
        "draft_id": input_data.get("draft_id") or row["related_task_id"],
        "course_id": row["course_id"],
        "status": row["status"],
        "progress": row["progress"] or 0,
        "current_step": row["current_step"],
        "total_sections": int(output.get("total_sections") or 0),
        "current_section": output.get("current_section"),
        "contents_generated": int(output.get("contents_generated") or 0),
        "contents_failed": int(output.get("contents_failed") or 0),
        "content_ids": output.get("content_ids") or [],
        "failed_items": output.get("failed_items") or [],
        "error_message": row["error_message"],
    }


def get_content_generation_task_status(db: Session, task_id: str) -> dict:
    row = db.execute(
        text(
            """
            SELECT *
            FROM agent_tasks
            WHERE id = :task_id
              AND task_type = 'course_content_generate'
            LIMIT 1
            """
        ),
        {"task_id": task_id},
    ).mappings().first()
    if row is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="课程内容生成任务不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return _format_generation_task(row)


def create_content_generation_task(
    db: Session,
    draft_id: str,
    current_user: User,
) -> dict:
    draft_record = _load_draft(db, draft_id)
    existing = db.execute(
        text(
            """
            SELECT *
            FROM agent_tasks
            WHERE task_type = 'course_content_generate'
              AND related_task_id = :draft_id
              AND status IN ('pending', 'running')
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"draft_id": draft_id},
    ).mappings().first()
    if existing is not None:
        task = _format_generation_task(existing)
        return {
            "task_id": task["task_id"],
            "draft_id": task["draft_id"],
            "course_id": task["course_id"],
            "status": task["status"],
            "progress": task["progress"],
            "total_sections": task["total_sections"],
        }

    _ensure_draft_content_generatable(draft_record)
    sections = _load_confirmed_sections(db, draft_record["course_id"])
    if not sections:
        raise AppException(
            code=ErrorCode.CONFLICT,
            message="未找到已保存的章节小节，请先确认章节结构",
            status_code=status.HTTP_409_CONFLICT,
        )

    total_sections = len(sections)
    task_id = "agent_" + uuid.uuid4().hex[:12]
    output = _task_output(
        draft_id=draft_id,
        course_id=draft_record["course_id"],
        total_sections=total_sections,
    )
    task = AgentTask(
        id=task_id,
        task_type="course_content_generate",
        related_task_id=draft_id,
        student_id=None,
        course_id=draft_record["course_id"],
        status="pending",
        progress=0,
        current_step="任务已进入队列",
        input_json={
            "draft_id": draft_id,
            "created_by": str(current_user.id),
            "username": current_user.username,
        },
        output_json=output,
        error_message=None,
    )
    db.add(task)
    db.commit()

    return {
        "task_id": task_id,
        "draft_id": draft_id,
        "course_id": draft_record["course_id"],
        "status": "pending",
        "progress": 0,
        "total_sections": total_sections,
    }


def _insert_chapter(
    db: Session,
    course_id: str,
    title: str,
    description: str | None,
    sort_order: int,
    parent_id: str | None,
    level: int,
) -> tuple[str, bool]:
    existing = db.execute(
        text(
            """
            SELECT id
            FROM course_chapters
            WHERE course_id = :course_id
              AND title = :title
              AND ((parent_id IS NULL AND :parent_id IS NULL) OR parent_id = :parent_id)
            LIMIT 1
            """
        ),
        {"course_id": course_id, "title": title, "parent_id": parent_id},
    ).mappings().first()
    if existing:
        return existing["id"], False

    chapter_id = ("sec_" if level > 1 else "ch_") + uuid.uuid4().hex[:12]
    db.execute(
        text(
            """
            INSERT INTO course_chapters (
                id, course_id, parent_id, level, title, description,
                sort_order, created_at, updated_at
            )
            VALUES (
                :id, :course_id, :parent_id, :level, :title, :description,
                :sort_order, NOW(), NOW()
            )
            """
        ),
        {
            "id": chapter_id,
            "course_id": course_id,
            "parent_id": parent_id,
            "level": level,
            "title": title,
            "description": description,
            "sort_order": sort_order,
        },
    )
    return chapter_id, True


def _insert_knowledge_point(
    db: Session,
    course_id: str,
    section_id: str,
    point: dict[str, Any],
    sort_order: int,
) -> tuple[str, bool]:
    existing = db.execute(
        text(
            """
            SELECT id
            FROM knowledge_points
            WHERE course_id = :course_id
              AND chapter_id = :section_id
              AND name = :name
            LIMIT 1
            """
        ),
        {"course_id": course_id, "section_id": section_id, "name": point["name"]},
    ).mappings().first()
    if existing:
        return existing["id"], False

    point_id = "kp_" + uuid.uuid4().hex[:12]
    db.execute(
        text(
            """
            INSERT INTO knowledge_points (
                id, course_id, chapter_id, name, description,
                difficulty, sort_order, created_at, updated_at
            )
            VALUES (
                :id, :course_id, :chapter_id, :name, :description,
                :difficulty, :sort_order, NOW(), NOW()
            )
            """
        ),
        {
            "id": point_id,
            "course_id": course_id,
            "chapter_id": section_id,
            "name": point["name"],
            "description": point.get("description"),
            "difficulty": point.get("difficulty") or "基础",
            "sort_order": sort_order,
        },
    )
    return point_id, True


def _persist_confirmed_course_structure(
    db: Session,
    course_id: str,
    draft: dict[str, Any],
) -> dict[str, Any]:
    chapters_created = 0
    sections_created = 0
    knowledge_points_created = 0
    sections: list[dict[str, Any]] = []

    for chapter_index, chapter in enumerate(draft["chapters"], start=1):
        chapter_id, chapter_created = _insert_chapter(
            db=db,
            course_id=course_id,
            title=chapter["title"],
            description=chapter.get("description"),
            sort_order=chapter_index,
            parent_id=None,
            level=1,
        )
        if chapter_created:
            chapters_created += 1

        for section_index, section in enumerate(chapter.get("sections") or [], start=1):
            section_id, section_created = _insert_chapter(
                db=db,
                course_id=course_id,
                title=section["title"],
                description=section.get("description"),
                sort_order=section_index,
                parent_id=chapter_id,
                level=2,
            )
            if section_created:
                sections_created += 1

            knowledge_points = []
            for point_index, point in enumerate(section.get("knowledge_points") or [], start=1):
                point_id, point_created = _insert_knowledge_point(
                    db=db,
                    course_id=course_id,
                    section_id=section_id,
                    point=point,
                    sort_order=point_index,
                )
                if point_created:
                    knowledge_points_created += 1
                knowledge_points.append(
                    {
                        "knowledge_point_id": point_id,
                        "name": point["name"],
                        "description": point.get("description"),
                        "difficulty": point.get("difficulty"),
                    }
                )

            sections.append(
                {
                    "chapter_id": chapter_id,
                    "chapter_title": chapter["title"],
                    "section_id": section_id,
                    "section_title": section["title"],
                    "section_description": section.get("description"),
                    "knowledge_points": knowledge_points,
                }
            )

    return {
        "chapters_created": chapters_created,
        "sections_created": sections_created,
        "knowledge_points_created": knowledge_points_created,
        "sections": sections,
    }


def _load_confirmed_sections(db: Session, course_id: str) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT
                sec.id AS section_id,
                sec.title AS section_title,
                sec.description AS section_description,
                sec.sort_order AS section_sort_order,
                ch.id AS chapter_id,
                ch.title AS chapter_title,
                ch.sort_order AS chapter_sort_order
            FROM course_chapters sec
            LEFT JOIN course_chapters ch ON ch.id = sec.parent_id
            WHERE sec.course_id = :course_id
              AND sec.parent_id IS NOT NULL
            ORDER BY ch.sort_order ASC, sec.sort_order ASC, sec.created_at ASC
            """
        ),
        {"course_id": course_id},
    ).mappings().all()

    sections: list[dict[str, Any]] = []
    for row in rows:
        point_rows = db.execute(
            text(
                """
                SELECT id, name, description, difficulty
                FROM knowledge_points
                WHERE course_id = :course_id
                  AND chapter_id = :section_id
                ORDER BY sort_order ASC, created_at ASC
                """
            ),
            {"course_id": course_id, "section_id": row["section_id"]},
        ).mappings().all()
        sections.append(
            {
                "chapter_id": row["chapter_id"],
                "chapter_title": row["chapter_title"],
                "section_id": row["section_id"],
                "section_title": row["section_title"],
                "section_description": row["section_description"],
                "knowledge_points": [
                    {
                        "knowledge_point_id": point["id"],
                        "name": point["name"],
                        "description": point["description"],
                        "difficulty": point["difficulty"],
                    }
                    for point in point_rows
                ],
            }
        )
    return sections


def _set_draft_status(db: Session, draft_id: str, status_value: str, confirmed_by: str | None = None) -> None:
    db.execute(
        text(
            """
            UPDATE course_structure_drafts
            SET status = :status,
                confirmed_by = COALESCE(:confirmed_by, confirmed_by),
                confirmed_at = CASE
                    WHEN :confirmed_by IS NULL THEN confirmed_at
                    ELSE COALESCE(confirmed_at, NOW())
                END,
                updated_at = NOW()
            WHERE id = :draft_id
            """
        ),
        {"draft_id": draft_id, "status": status_value, "confirmed_by": confirmed_by},
    )


def _rebuild_source_documents(
    db: Session,
    course_id: str,
    document_ids: list[str],
    created_by: str | None,
) -> None:
    if not document_ids:
        rows = db.execute(
            text(
                """
                SELECT id
                FROM course_documents
                WHERE course_id = :course_id
                  AND COALESCE(status, 'active') <> 'deleted'
                  AND parse_status IN ('parsed', 'processing')
                ORDER BY uploaded_at ASC
                """
            ),
            {"course_id": course_id},
        ).mappings().all()
        document_ids = [row["id"] for row in rows]

    for document_id in document_ids:
        rebuild_course_document_index_with_structure(
            db=db,
            course_id=course_id,
            document_id=document_id,
            created_by=created_by,
        )
    db.commit()


def _retrieve_rag_context_for_section(
    db: Session,
    course_id: str,
    section: dict[str, Any],
) -> list[dict[str, Any]]:
    exact_rows = db.execute(
        text(
            """
            SELECT
                kc.id AS chunk_id,
                kc.document_id,
                kc.course_id,
                kc.chapter_id,
                kc.knowledge_point_id,
                kc.section,
                kc.content,
                kc.chunk_index
            FROM knowledge_chunks kc
            JOIN course_documents cd ON cd.id = kc.document_id
            WHERE kc.course_id = :course_id
              AND kc.chapter_id = :section_id
              AND COALESCE(kc.deleted, 0) = 0
              AND COALESCE(cd.status, 'active') <> 'deleted'
            ORDER BY kc.document_id ASC, kc.chunk_index ASC
            LIMIT 12
            """
        ),
        {
            "course_id": course_id,
            "section_id": section["section_id"],
        },
    ).mappings().all()
    items = [
        {
            **dict(row),
            "score": 1.0,
            "retrieval_type": "section",
        }
        for row in exact_rows
    ]
    known_chunk_ids = {item["chunk_id"] for item in items}

    point_names = [point["name"] for point in section.get("knowledge_points") or []]
    query = " ".join(
        value
        for value in [
            section.get("chapter_title"),
            section.get("section_title"),
            section.get("section_description"),
            " ".join(point_names),
        ]
        if value
    )
    if not query.strip():
        return items

    try:
        result = search_knowledge_chunks(
            db=db,
            course_id=course_id,
            query=query,
            top_k=8,
            chapter_id=section["section_id"],
        )
        for item in result.get("items") or []:
            if item.get("chunk_id") not in known_chunk_ids:
                item["retrieval_type"] = "section_vector"
                items.append(item)
                known_chunk_ids.add(item.get("chunk_id"))
    except Exception:
        pass

    if len(items) >= 12:
        return items[:12]

    try:
        result = search_knowledge_chunks(
            db=db,
            course_id=course_id,
            query=query,
            top_k=8,
        )
        for item in result.get("items") or []:
            if item.get("chunk_id") not in known_chunk_ids:
                item["retrieval_type"] = "course_vector"
                items.append(item)
                known_chunk_ids.add(item.get("chunk_id"))
            if len(items) >= 12:
                break
    except Exception:
        pass
    return items[:12]


def _save_section_learning_content(
    db: Session,
    course_id: str,
    section: dict[str, Any],
    agent_result: dict[str, Any],
    source_chunk_ids: list[str],
    created_by: str,
    status_value: str,
    error_message: str | None = None,
) -> str:
    content_id = "slc_" + uuid.uuid4().hex[:12]
    primary_point = (section.get("knowledge_points") or [None])[0]
    db.execute(
        text(
            """
            INSERT INTO course_section_learning_contents (
                id, course_id, chapter_id, section_id, knowledge_point_id,
                title, content_type, content_markdown, content_json,
                source_chunk_ids, generation_prompt, generation_model,
                status, error_message, created_by, created_at, updated_at
            )
            VALUES (
                :id, :course_id, :chapter_id, :section_id, :knowledge_point_id,
                :title, 'student_learning_content', :content_markdown, :content_json,
                :source_chunk_ids, :generation_prompt, :generation_model,
                :status, :error_message, :created_by, NOW(), NOW()
            )
            """
        ),
        {
            "id": content_id,
            "course_id": course_id,
            "chapter_id": section["chapter_id"],
            "section_id": section["section_id"],
            "knowledge_point_id": primary_point["knowledge_point_id"] if primary_point else None,
            "title": section["section_title"],
            "content_markdown": agent_result.get("content_markdown"),
            "content_json": json.dumps(agent_result.get("content_json"), ensure_ascii=False)
            if agent_result.get("content_json") is not None
            else None,
            "source_chunk_ids": json.dumps(source_chunk_ids, ensure_ascii=False),
            "generation_prompt": agent_result.get("generation_prompt"),
            "generation_model": agent_result.get("generation_model"),
            "status": status_value,
            "error_message": error_message,
            "created_by": created_by,
        },
    )
    db.commit()
    return content_id


def _load_course(db: Session, course_id: str) -> dict[str, Any]:
    row = db.execute(
        text(
            """
            SELECT course_id, name, description
            FROM courses
            WHERE course_id = :course_id
            LIMIT 1
            """
        ),
        {"course_id": course_id},
    ).mappings().first()
    return dict(row) if row else {"course_id": course_id}


def confirm_draft_and_generate_learning_contents(
    db: Session,
    draft_id: str,
    current_user: User,
    task_id: str | None = None,
) -> dict:
    draft_record = _load_draft(db, draft_id)
    _ensure_draft_confirmable(draft_record)

    course_id = draft_record["course_id"]
    created_by = str(current_user.id)

    try:
        if task_id:
            _update_agent_task(
                db=db,
                task_id=task_id,
                status_value="running",
                progress=1,
                current_step="确认课程结构",
                output_json=_task_output(
                    draft_id=draft_id,
                    course_id=course_id,
                ),
            )
        _set_draft_status(db, draft_id, "content_generating", confirmed_by=created_by)
        structure_result = _persist_confirmed_course_structure(
            db=db,
            course_id=course_id,
            draft=draft_record["draft"],
        )
        db.commit()
        if task_id:
            _update_agent_task(
                db=db,
                task_id=task_id,
                progress=10,
                current_step="正式课程结构已写入",
                output_json=_task_output(
                    draft_id=draft_id,
                    course_id=course_id,
                    total_sections=len(structure_result["sections"]),
                ),
            )
    except Exception:
        db.rollback()
        _set_draft_status(db, draft_id, "failed")
        db.commit()
        raise

    try:
        if task_id:
            _update_agent_task(
                db=db,
                task_id=task_id,
                progress=15,
                current_step="重建课程知识索引",
            )
        _rebuild_source_documents(
            db=db,
            course_id=course_id,
            document_ids=draft_record["source_document_ids"],
            created_by=created_by,
        )
    except Exception:
        # Content generation can still fall back to the confirmed structure if
        # vector rebuilding is unavailable in the current environment.
        db.rollback()

    course = _load_course(db, course_id)
    content_ids: list[str] = []
    failed_items: list[dict[str, Any]] = []
    total_sections = len(structure_result["sections"])

    for index, section in enumerate(structure_result["sections"], start=1):
        if task_id:
            _update_agent_task(
                db=db,
                task_id=task_id,
                progress=15 + int((index - 1) / max(total_sections, 1) * 80),
                current_step=f"正在生成小节内容：{section['section_title']}",
                output_json=_task_output(
                    draft_id=draft_id,
                    course_id=course_id,
                    total_sections=total_sections,
                    current_section=section["section_title"],
                    contents_generated=len(content_ids),
                    contents_failed=len(failed_items),
                    content_ids=content_ids,
                    failed_items=failed_items,
                ),
            )
        try:
            agent = StudentLearningContentAgent()
            rag_chunks = _retrieve_rag_context_for_section(
                db=db,
                course_id=course_id,
                section=section,
            )
            agent_result = agent.run_sync(
                {
                    "course": course,
                    "chapter": {
                        "chapter_id": section["chapter_id"],
                        "title": section["chapter_title"],
                    },
                    "section": {
                        "section_id": section["section_id"],
                        "title": section["section_title"],
                        "description": section.get("section_description"),
                    },
                    "knowledge_points": section.get("knowledge_points") or [],
                    "course_structure": draft_record["draft"],
                    "rag_chunks": rag_chunks,
                }
            )
            agent_result["content_markdown"] = append_source_images(
                agent_result.get("content_markdown"),
                rag_chunks,
            )
            source_chunk_ids = [
                item["chunk_id"]
                for item in rag_chunks
                if item.get("chunk_id")
            ]
            content_id = _save_section_learning_content(
                db=db,
                course_id=course_id,
                section=section,
                agent_result=agent_result,
                source_chunk_ids=source_chunk_ids,
                created_by=created_by,
                status_value=agent_result.get("status") or "generated",
                error_message=agent_result.get("json_error"),
            )
            content_ids.append(content_id)
        except Exception as exc:
            failed_items.append(
                {
                    "section_id": section["section_id"],
                    "section_title": section["section_title"],
                    "error_message": str(exc),
                }
            )
            _save_section_learning_content(
                db=db,
                course_id=course_id,
                section=section,
                agent_result={
                    "content_markdown": None,
                    "content_json": None,
                    "generation_prompt": None,
                    "generation_model": None,
                },
                source_chunk_ids=[],
                created_by=created_by,
                status_value="failed",
                error_message=str(exc),
            )
        finally:
            if task_id:
                _update_agent_task(
                    db=db,
                    task_id=task_id,
                    progress=15 + int(index / max(total_sections, 1) * 80),
                    current_step=f"已处理小节：{section['section_title']}",
                    output_json=_task_output(
                        draft_id=draft_id,
                        course_id=course_id,
                        total_sections=total_sections,
                        current_section=section["section_title"],
                        contents_generated=len(content_ids),
                        contents_failed=len(failed_items),
                        content_ids=content_ids,
                        failed_items=failed_items,
                    ),
                )

    contents_generated = len(content_ids)
    contents_failed = len(failed_items)
    if contents_generated and contents_failed:
        final_status = "content_partially_generated"
    elif contents_generated:
        final_status = "content_generated"
    else:
        final_status = "failed"

    _set_draft_status(db, draft_id, final_status, confirmed_by=created_by)
    db.commit()
    if task_id:
        _update_agent_task(
            db=db,
            task_id=task_id,
            status_value="completed" if contents_generated else "failed",
            progress=100,
            current_step="学习内容生成完成",
            output_json=_task_output(
                draft_id=draft_id,
                course_id=course_id,
                total_sections=total_sections,
                contents_generated=contents_generated,
                contents_failed=contents_failed,
                content_ids=content_ids,
                failed_items=failed_items,
            ),
            error_message=None if contents_generated else "所有小节内容生成失败",
        )

    return {
        "draft_id": draft_id,
        "course_id": course_id,
        "status": final_status,
        "chapters_created": structure_result["chapters_created"],
        "sections_created": structure_result["sections_created"],
        "knowledge_points_created": structure_result["knowledge_points_created"],
        "contents_generated": contents_generated,
        "contents_failed": contents_failed,
        "content_ids": content_ids,
        "failed_items": failed_items,
    }


def generate_learning_contents_for_confirmed_draft(
    db: Session,
    draft_id: str,
    current_user: User,
    task_id: str | None = None,
) -> dict:
    draft_record = _load_draft(db, draft_id)
    _ensure_draft_content_generatable(draft_record)

    course_id = draft_record["course_id"]
    created_by = str(current_user.id)
    sections = _load_confirmed_sections(db, course_id)
    if not sections:
        raise AppException(
            code=ErrorCode.CONFLICT,
            message="未找到已保存的章节小节，请先确认章节结构",
            status_code=status.HTTP_409_CONFLICT,
        )

    total_sections = len(sections)
    if task_id:
        _update_agent_task(
            db=db,
            task_id=task_id,
            status_value="running",
            progress=1,
            current_step="开始生成章节学习内容",
            output_json=_task_output(
                draft_id=draft_id,
                course_id=course_id,
                total_sections=total_sections,
            ),
        )

    _set_draft_status(db, draft_id, "content_generating")
    db.commit()

    course = _load_course(db, course_id)
    content_ids: list[str] = []
    failed_items: list[dict[str, Any]] = []

    for index, section in enumerate(sections, start=1):
        if task_id:
            _update_agent_task(
                db=db,
                task_id=task_id,
                progress=5 + int((index - 1) / max(total_sections, 1) * 90),
                current_step=f"正在生成小节内容：{section['section_title']}",
                output_json=_task_output(
                    draft_id=draft_id,
                    course_id=course_id,
                    total_sections=total_sections,
                    current_section=section["section_title"],
                    contents_generated=len(content_ids),
                    contents_failed=len(failed_items),
                    content_ids=content_ids,
                    failed_items=failed_items,
                ),
            )
        try:
            agent = StudentLearningContentAgent()
            rag_chunks = _retrieve_rag_context_for_section(
                db=db,
                course_id=course_id,
                section=section,
            )
            agent_result = agent.run_sync(
                {
                    "course": course,
                    "chapter": {
                        "chapter_id": section["chapter_id"],
                        "title": section["chapter_title"],
                    },
                    "section": {
                        "section_id": section["section_id"],
                        "title": section["section_title"],
                        "description": section.get("section_description"),
                    },
                    "knowledge_points": section.get("knowledge_points") or [],
                    "course_structure": draft_record["draft"],
                    "rag_chunks": rag_chunks,
                }
            )
            agent_result["content_markdown"] = append_source_images(
                agent_result.get("content_markdown"),
                rag_chunks,
            )
            source_chunk_ids = [
                item["chunk_id"]
                for item in rag_chunks
                if item.get("chunk_id")
            ]
            content_id = _save_section_learning_content(
                db=db,
                course_id=course_id,
                section=section,
                agent_result=agent_result,
                source_chunk_ids=source_chunk_ids,
                created_by=created_by,
                status_value=agent_result.get("status") or "generated",
                error_message=agent_result.get("json_error"),
            )
            content_ids.append(content_id)
        except Exception as exc:
            failed_items.append(
                {
                    "section_id": section["section_id"],
                    "section_title": section["section_title"],
                    "error_message": str(exc),
                }
            )
            _save_section_learning_content(
                db=db,
                course_id=course_id,
                section=section,
                agent_result={
                    "content_markdown": None,
                    "content_json": None,
                    "generation_prompt": None,
                    "generation_model": None,
                },
                source_chunk_ids=[],
                created_by=created_by,
                status_value="failed",
                error_message=str(exc),
            )
        finally:
            if task_id:
                _update_agent_task(
                    db=db,
                    task_id=task_id,
                    progress=5 + int(index / max(total_sections, 1) * 90),
                    current_step=f"已处理小节：{section['section_title']}",
                    output_json=_task_output(
                        draft_id=draft_id,
                        course_id=course_id,
                        total_sections=total_sections,
                        current_section=section["section_title"],
                        contents_generated=len(content_ids),
                        contents_failed=len(failed_items),
                        content_ids=content_ids,
                        failed_items=failed_items,
                    ),
                )

    contents_generated = len(content_ids)
    contents_failed = len(failed_items)
    if contents_generated and contents_failed:
        final_status = "content_partially_generated"
    elif contents_generated:
        final_status = "content_generated"
    else:
        final_status = "failed"

    _set_draft_status(db, draft_id, final_status)
    db.commit()
    if task_id:
        _update_agent_task(
            db=db,
            task_id=task_id,
            status_value="completed" if contents_generated else "failed",
            progress=100,
            current_step="学习内容生成完成",
            output_json=_task_output(
                draft_id=draft_id,
                course_id=course_id,
                total_sections=total_sections,
                contents_generated=contents_generated,
                contents_failed=contents_failed,
                content_ids=content_ids,
                failed_items=failed_items,
            ),
            error_message=None if contents_generated else "所有小节内容生成失败",
        )

    return {
        "draft_id": draft_id,
        "course_id": course_id,
        "status": final_status,
        "chapters_created": 0,
        "sections_created": 0,
        "knowledge_points_created": 0,
        "contents_generated": contents_generated,
        "contents_failed": contents_failed,
        "content_ids": content_ids,
        "failed_items": failed_items,
    }


def run_content_generation_task(task_id: str) -> None:
    db = SessionLocal()
    try:
        row = db.execute(
            text(
                """
                SELECT *
                FROM agent_tasks
                WHERE id = :task_id
                  AND task_type = 'course_content_generate'
                LIMIT 1
                """
            ),
            {"task_id": task_id},
        ).mappings().first()
        if row is None:
            return

        input_data = _json_loads(row["input_json"], {}) or {}
        draft_id = input_data.get("draft_id") or row["related_task_id"]
        created_by = input_data.get("created_by")
        if not draft_id or not created_by:
            _update_agent_task(
                db=db,
                task_id=task_id,
                status_value="failed",
                progress=100,
                current_step="任务参数错误",
                error_message="缺少 draft_id 或 created_by",
            )
            return

        current_user = SimpleNamespace(
            id=created_by,
            username=input_data.get("username") or "",
        )
        generate_learning_contents_for_confirmed_draft(
            db=db,
            draft_id=draft_id,
            current_user=current_user,
            task_id=task_id,
        )
    except Exception as exc:
        logger.exception("course content generation task failed | task_id=%s", task_id)
        try:
            _update_agent_task(
                db=db,
                task_id=task_id,
                status_value="failed",
                progress=100,
                current_step="任务执行失败",
                error_message=str(exc),
            )
        except Exception:
            db.rollback()
    finally:
        db.close()


def _format_learning_content(row: Any) -> dict[str, Any]:
    content_json = _json_loads(row["content_json"], None)
    if isinstance(content_json, dict):
        content_json = StudentLearningContentAgent.normalize_content_json(
            content_json,
            section_id=row["section_id"],
        )
    return {
        "content_id": row["id"],
        "course_id": row["course_id"],
        "chapter_id": row["chapter_id"],
        "section_id": row["section_id"],
        "knowledge_point_id": row["knowledge_point_id"],
        "title": row["title"],
        "content_type": row["content_type"],
        "content_markdown": row["content_markdown"],
        "content_json": content_json,
        "source_chunk_ids": _json_loads(row["source_chunk_ids"], []),
        "generation_model": row["generation_model"],
        "status": row["status"],
        "error_message": row["error_message"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


def list_section_learning_contents(
    db: Session,
    course_id: str,
    chapter_id: str | None = None,
    section_id: str | None = None,
) -> dict:
    where = ["course_id = :course_id"]
    params: dict[str, Any] = {"course_id": course_id}
    if chapter_id:
        where.append("chapter_id = :chapter_id")
        params["chapter_id"] = chapter_id
    if section_id:
        where.append("section_id = :section_id")
        params["section_id"] = section_id

    where_sql = " AND ".join(where)
    rows = db.execute(
        text(
            f"""
            SELECT *
            FROM course_section_learning_contents
            WHERE {where_sql}
            ORDER BY created_at ASC
            """
        ),
        params,
    ).mappings().all()
    return {
        "course_id": course_id,
        "chapter_id": chapter_id,
        "section_id": section_id,
        "total": len(rows),
        "items": [_format_learning_content(row) for row in rows],
    }
