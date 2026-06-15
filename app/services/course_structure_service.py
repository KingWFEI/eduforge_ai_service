import json
import uuid
from typing import Any

from fastapi import status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agents.course_structure_agent import CourseStructureAgent
from app.services.rag_service import (
    extract_text_from_file,
    rebuild_course_document_index_with_structure,
)
from app.utils.response import AppException, ErrorCode


STRUCTURE_SYSTEM_PROMPT = """
你是课程设计专家。请根据课程资料识别课程结构，只输出合法 JSON 对象。
JSON 格式必须为：
{
  "chapters": [
    {
      "title": "章标题",
      "description": "章说明",
      "sections": [
        {
          "title": "小节标题",
          "description": "小节说明",
          "knowledge_points": [
            {
              "name": "知识点名称",
              "description": "知识点说明",
              "difficulty": "基础/中等/较难"
            }
          ]
        }
      ]
    }
  ]
}
要求：
1. 章节、小节、知识点必须来自资料内容，不要凭空扩展。
2. 如果资料没有明显小节，也要按主题归纳出小节。
3. 知识点名称要短，适合用于检索和学习路径规划。
4. difficulty 只能使用：基础、中等、较难。
"""


def _ensure_course_exists(db: Session, course_id: str) -> None:
    course = db.execute(
        text("SELECT course_id FROM courses WHERE course_id = :course_id LIMIT 1"),
        {"course_id": course_id},
    ).mappings().first()
    if course is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="课程不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )


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
        normalized_sections = []
        for section in chapter.get("sections") or []:
            if not isinstance(section, dict) or not str(section.get("title", "")).strip():
                continue
            normalized_points = []
            for point in section.get("knowledge_points") or []:
                if not isinstance(point, dict) or not str(point.get("name", "")).strip():
                    continue
                difficulty = point.get("difficulty") or "基础"
                if difficulty not in {"基础", "中等", "较难"}:
                    difficulty = "基础"
                normalized_points.append(
                    {
                        "name": str(point["name"]).strip()[:100],
                        "description": str(point.get("description") or "").strip()[:1000] or None,
                        "difficulty": difficulty,
                    }
                )
            normalized_sections.append(
                {
                    "title": str(section["title"]).strip()[:200],
                    "description": str(section.get("description") or "").strip()[:1000] or None,
                    "knowledge_points": normalized_points,
                }
            )
        normalized_chapters.append(
            {
                "title": str(chapter["title"]).strip()[:200],
                "description": str(chapter.get("description") or "").strip()[:1000] or None,
                "sections": normalized_sections,
            }
        )

    if not normalized_chapters:
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message="课程结构草稿中没有有效章节",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return {"chapters": normalized_chapters}


def _document_rows(
    db: Session,
    course_id: str,
    document_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"course_id": course_id}
    where = [
        "course_id = :course_id",
        "COALESCE(status, 'active') <> 'deleted'",
        "parse_status IN ('parsed', 'processing')",
    ]
    if document_ids:
        placeholders = []
        for index, document_id in enumerate(document_ids):
            key = f"doc_{index}"
            params[key] = document_id
            placeholders.append(f":{key}")
        where.append(f"id IN ({', '.join(placeholders)})")

    rows = db.execute(
        text(
            f"""
            SELECT id, filename, file_path
            FROM course_documents
            WHERE {' AND '.join(where)}
            ORDER BY uploaded_at ASC
            """
        ),
        params,
    ).mappings().all()
    return [dict(row) for row in rows]


def generate_course_structure_draft(
    db: Session,
    course_id: str,
    document_ids: list[str] | None,
    created_by: str | None,
) -> dict:
    _ensure_course_exists(db, course_id)
    documents = _document_rows(db, course_id, document_ids)
    if not documents:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="没有可用于生成课程结构的课程资料，请先上传并解析资料",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    text_parts = []
    for document in documents:
        content = extract_text_from_file(document["file_path"]).strip()
        if content:
            text_parts.append(
                f"资料：{document['filename']}\n{content[:12000]}"
            )
    if not text_parts:
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message="课程资料没有可解析文本，无法生成课程结构",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    draft = CourseStructureAgent().run_sync({"text_parts": text_parts})
    normalized_draft = _normalize_draft(draft)
    draft_id = "csd_" + uuid.uuid4().hex[:12]
    source_document_ids = [document["id"] for document in documents]

    db.execute(
        text(
            """
            INSERT INTO course_structure_drafts (
                id, course_id, source_document_ids_json, draft_json, status,
                created_by, created_at, updated_at
            )
            VALUES (
                :id, :course_id, :source_document_ids_json, :draft_json, 'draft',
                :created_by, NOW(), NOW()
            )
            """
        ),
        {
            "id": draft_id,
            "course_id": course_id,
            "source_document_ids_json": json.dumps(source_document_ids, ensure_ascii=False),
            "draft_json": json.dumps(normalized_draft, ensure_ascii=False),
            "created_by": created_by,
        },
    )
    db.commit()
    return get_course_structure_draft(db, course_id, draft_id)


def get_course_structure_draft(db: Session, course_id: str, draft_id: str) -> dict:
    row = db.execute(
        text(
            """
            SELECT *
            FROM course_structure_drafts
            WHERE id = :draft_id
              AND course_id = :course_id
            LIMIT 1
            """
        ),
        {"draft_id": draft_id, "course_id": course_id},
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
        "draft": _json_loads(row["draft_json"], {}),
        "status": row["status"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        "confirmed_at": row["confirmed_at"].isoformat() if row["confirmed_at"] else None,
    }


def update_course_structure_draft(
    db: Session,
    course_id: str,
    draft_id: str,
    draft: dict[str, Any],
) -> dict:
    current = get_course_structure_draft(db, course_id, draft_id)
    if current["status"] != "draft":
        raise AppException(
            code=ErrorCode.CONFLICT,
            message="只有 draft 状态的课程结构草稿可以编辑",
            status_code=status.HTTP_409_CONFLICT,
        )
    normalized_draft = _normalize_draft(draft)
    db.execute(
        text(
            """
            UPDATE course_structure_drafts
            SET draft_json = :draft_json,
                updated_at = NOW()
            WHERE id = :draft_id
              AND course_id = :course_id
            """
        ),
        {
            "draft_json": json.dumps(normalized_draft, ensure_ascii=False),
            "draft_id": draft_id,
            "course_id": course_id,
        },
    )
    db.commit()
    return get_course_structure_draft(db, course_id, draft_id)


def _insert_chapter(
    db: Session,
    course_id: str,
    title: str,
    description: str | None,
    sort_order: int,
    parent_id: str | None,
    level: int,
) -> str:
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
        return existing["id"]

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
    return chapter_id


def _insert_knowledge_point(
    db: Session,
    course_id: str,
    chapter_id: str,
    point: dict[str, Any],
    sort_order: int,
) -> str:
    existing = db.execute(
        text(
            """
            SELECT id
            FROM knowledge_points
            WHERE course_id = :course_id
              AND chapter_id = :chapter_id
              AND name = :name
            LIMIT 1
            """
        ),
        {
            "course_id": course_id,
            "chapter_id": chapter_id,
            "name": point["name"],
        },
    ).mappings().first()
    if existing:
        return existing["id"]

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
            "chapter_id": chapter_id,
            "name": point["name"],
            "description": point.get("description"),
            "difficulty": point.get("difficulty") or "基础",
            "sort_order": sort_order,
        },
    )
    return point_id


def confirm_course_structure_draft(
    db: Session,
    course_id: str,
    draft_id: str,
    confirmed_by: str | None,
    draft: dict[str, Any] | None = None,
    rebuild_index: bool = True,
) -> dict:
    current = get_course_structure_draft(db, course_id, draft_id)
    if current["status"] != "draft":
        raise AppException(
            code=ErrorCode.CONFLICT,
            message="只有 draft 状态的课程结构草稿可以确认",
            status_code=status.HTTP_409_CONFLICT,
        )

    final_draft = _normalize_draft(draft or current["draft"])
    created_chapters = 0
    created_sections = 0
    created_points = 0

    for chapter_index, chapter in enumerate(final_draft["chapters"], start=1):
        chapter_id = _insert_chapter(
            db=db,
            course_id=course_id,
            title=chapter["title"],
            description=chapter.get("description"),
            sort_order=chapter_index,
            parent_id=None,
            level=1,
        )
        created_chapters += 1

        sections = chapter.get("sections") or []
        if not sections:
            sections = [
                {
                    "title": chapter["title"],
                    "description": chapter.get("description"),
                    "knowledge_points": [],
                }
            ]

        for section_index, section in enumerate(sections, start=1):
            section_id = _insert_chapter(
                db=db,
                course_id=course_id,
                title=section["title"],
                description=section.get("description"),
                sort_order=section_index,
                parent_id=chapter_id,
                level=2,
            )
            created_sections += 1
            for point_index, point in enumerate(section.get("knowledge_points") or [], start=1):
                _insert_knowledge_point(
                    db=db,
                    course_id=course_id,
                    chapter_id=section_id,
                    point=point,
                    sort_order=point_index,
                )
                created_points += 1

    db.execute(
        text(
            """
            UPDATE course_structure_drafts
            SET draft_json = :draft_json,
                status = 'confirmed',
                confirmed_by = :confirmed_by,
                confirmed_at = NOW(),
                updated_at = NOW()
            WHERE id = :draft_id
              AND course_id = :course_id
            """
        ),
        {
            "draft_json": json.dumps(final_draft, ensure_ascii=False),
            "confirmed_by": confirmed_by,
            "draft_id": draft_id,
            "course_id": course_id,
        },
    )
    db.commit()

    rebuilt_documents = 0
    rebuilt_chunks = 0
    if rebuild_index:
        documents = _document_rows(db, course_id, current["source_document_ids"] or None)
        for document in documents:
            result = rebuild_course_document_index_with_structure(
                db=db,
                course_id=course_id,
                document_id=document["id"],
                created_by=confirmed_by,
            )
            rebuilt_documents += 1
            rebuilt_chunks += result["chunk_count"]
        db.commit()

    return {
        "draft_id": draft_id,
        "course_id": course_id,
        "created_chapters": created_chapters,
        "created_sections": created_sections,
        "created_knowledge_points": created_points,
        "rebuilt_documents": rebuilt_documents,
        "rebuilt_chunks": rebuilt_chunks,
        "status": "confirmed",
    }
