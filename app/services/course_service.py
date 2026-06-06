import json
import uuid

from fastapi import status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.utils.response import AppException, ErrorCode
from app.services.rag_service import delete_document_chunks_from_chroma, update_document_chunks_metadata_in_chroma

def list_course_documents(
    db: Session,
    course_id: str,
) -> dict:
    """
    获取某门课程已上传资料列表。
    用于 Vue 管理端知识库管理页。
    """

    rows = db.execute(
        text(
            """
            SELECT
                id,
                course_id,
                chapter_id,
                filename,
                file_path,
                file_type,
                file_size,
                description,
                status,
                parse_status,
                index_status,
                chunk_count,
                uploaded_by,
                uploaded_at,
                updated_at
            FROM course_documents
            WHERE course_id = :course_id
              AND COALESCE(status, 'active') <> 'deleted'
            ORDER BY uploaded_at DESC
            """
        ),
        {"course_id": course_id},
    ).mappings().all()

    items = []

    for row in rows:
        items.append(
            {
                "document_id": row["id"],
                "course_id": row["course_id"],
                "chapter_id": row["chapter_id"],
                "filename": row["filename"],
                "file_path": row["file_path"],
                "file_type": row["file_type"],
                "file_size": row["file_size"],
                "description": row["description"],
                "status": row["status"],
                "parse_status": row["parse_status"],
                "index_status": row["index_status"],
                "chunk_count": row["chunk_count"] or 0,
                "uploaded_by": row["uploaded_by"],
                "uploaded_at": row["uploaded_at"].isoformat() if row["uploaded_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            }
        )

    return {
        "course_id": course_id,
        "total": len(items),
        "items": items,
    }


def list_course_knowledge_chunks(
    db: Session,
    course_id: str,
    document_id: str | None = None,
    keyword: str | None = None,
    chapter_id: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> dict:
    """
    获取课程知识块列表。
    阶段 6 标准接口：GET /api/courses/{course_id}/chunks
    """

    course = db.execute(
        text(
            """
            SELECT course_id
            FROM courses
            WHERE course_id = :course_id
            LIMIT 1
            """
        ),
        {"course_id": course_id},
    ).mappings().first()

    if course is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="课程不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    where_clauses = [
        "kc.course_id = :course_id",
        "COALESCE(kc.deleted, 0) = 0",
        "COALESCE(cd.status, 'active') <> 'deleted'",
    ]
    params = {
        "course_id": course_id,
        "limit": page_size,
        "offset": (page - 1) * page_size,
    }

    if document_id:
        where_clauses.append("kc.document_id = :document_id")
        params["document_id"] = document_id

    if chapter_id:
        where_clauses.append("kc.chapter_id = :chapter_id")
        params["chapter_id"] = chapter_id

    if keyword:
        where_clauses.append(
            """
            (
                kc.content LIKE :keyword
                OR kc.section LIKE :keyword
                OR cd.filename LIKE :keyword
            )
            """
        )
        params["keyword"] = f"%{keyword}%"

    where_sql = " AND ".join(where_clauses)

    total = db.execute(
        text(
            f"""
            SELECT COUNT(*) AS total
            FROM knowledge_chunks kc
            LEFT JOIN course_documents cd ON cd.id = kc.document_id
            WHERE {where_sql}
            """
        ),
        params,
    ).mappings().first()["total"]

    rows = db.execute(
        text(
            f"""
            SELECT
                kc.id,
                kc.document_id,
                kc.course_id,
                kc.chapter_id,
                cc.title AS chapter,
                kc.section,
                kc.content,
                kc.keywords_json,
                cd.filename AS source,
                kc.page_no,
                kc.chunk_index,
                kc.indexed
            FROM knowledge_chunks kc
            LEFT JOIN course_documents cd ON cd.id = kc.document_id
            LEFT JOIN course_chapters cc ON cc.id = kc.chapter_id
            WHERE {where_sql}
            ORDER BY kc.document_id ASC, kc.chunk_index ASC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()

    items = []

    for row in rows:
        keywords = row["keywords_json"] or []
        if isinstance(keywords, str):
            try:
                keywords = json.loads(keywords)
            except json.JSONDecodeError:
                keywords = []

        items.append(
            {
                "chunk_id": row["id"],
                "document_id": row["document_id"],
                "course_id": row["course_id"],
                "chapter_id": row["chapter_id"],
                "chapter": row["chapter"],
                "section": row["section"],
                "content": row["content"],
                "keywords": keywords if isinstance(keywords, list) else [],
                "source": row["source"],
                "page": row["page_no"],
                "chunk_index": row["chunk_index"],
                "indexed": bool(row["indexed"]),
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def delete_course_document(
    db: Session,
    course_id: str,
    document_id: str,
    current_user_id: int,
    current_user_role: str,
    delete_vectors: bool = True,
) -> dict:
    """
    逻辑删除课程资料及其知识块，并按需删除 Chroma 向量。
    """

    document = db.execute(
        text(
            """
            SELECT
                cd.id,
                cd.filename,
                c.created_by
            FROM course_documents cd
            JOIN courses c ON c.course_id = cd.course_id
            WHERE cd.id = :document_id
              AND cd.course_id = :course_id
              AND COALESCE(cd.status, 'active') <> 'deleted'
            LIMIT 1
            """
        ),
        {
            "document_id": document_id,
            "course_id": course_id,
        },
    ).mappings().first()

    if document is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="课程资料不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if current_user_role != "admin" and document["created_by"] != current_user_id:
        raise AppException(
            code=ErrorCode.FORBIDDEN,
            message="无权限删除该课程资料",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    deleted_vectors = 0
    if delete_vectors:
        deleted_vectors = delete_document_chunks_from_chroma(
            document_id=document_id
        )

    chunk_count_row = db.execute(
        text(
            """
            SELECT COUNT(*) AS total
            FROM knowledge_chunks
            WHERE document_id = :document_id
              AND course_id = :course_id
              AND COALESCE(deleted, 0) = 0
            """
        ),
        {
            "document_id": document_id,
            "course_id": course_id,
        },
    ).mappings().first()

    mysql_deleted_chunks = int(chunk_count_row["total"] or 0)

    db.execute(
        text(
            """
            UPDATE knowledge_chunks
            SET deleted = TRUE
            WHERE document_id = :document_id
              AND course_id = :course_id
              AND COALESCE(deleted, 0) = 0
            """
        ),
        {
            "document_id": document_id,
            "course_id": course_id,
        },
    )

    db.execute(
        text(
            """
            UPDATE course_documents
            SET status = 'deleted',
                parse_status = 'deleted',
                index_status = 'deleted',
                updated_at = NOW()
            WHERE id = :document_id
              AND course_id = :course_id
            """
        ),
        {
            "document_id": document_id,
            "course_id": course_id,
        },
    )

    db.commit()

    return {
        "document_id": document_id,
        "course_id": course_id,
        "filename": document["filename"],
        "deleted_chunks": mysql_deleted_chunks,
        "deleted_vectors": deleted_vectors,
        "document_status": "deleted",
    }


def create_course_chapter(
    db: Session,
    course_id: str,
    title: str,
    sort_order: int = 0,
    description: str | None = None,
    parent_id: str | None = None,
    level: int = 1,
) -> dict:
    """
    给指定课程新增章节。
    """

    # 1. 先确认课程存在
    course = db.execute(
        text(
            """
            SELECT course_id
            FROM courses
            WHERE course_id = :course_id
            LIMIT 1
            """
        ),
        {"course_id": course_id},
    ).mappings().first()

    if course is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="课程不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # 2. 同一门课程下，不建议重复创建同名章节
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
        {
            "course_id": course_id,
            "title": title,
            "parent_id": parent_id,
        },
    ).mappings().first()

    if existing is not None:
        raise AppException(
            code=ErrorCode.CONFLICT,
            message="该课程下已存在同名章节",
            status_code=status.HTTP_409_CONFLICT,
        )

    # 3. 创建章节
    chapter_id = "ch_" + uuid.uuid4().hex[:12]

    db.execute(
        text(
            """
            INSERT INTO course_chapters (
                id,
                course_id,
                parent_id,
                level,
                title,
                description,
                sort_order,
                created_at,
                updated_at
            )
            VALUES (
                :id,
                :course_id,
                :parent_id,
                :level,
                :title,
                :description,
                :sort_order,
                NOW(),
                NOW()
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

    db.commit()

    return {
        "chapter_id": chapter_id,
        "course_id": course_id,
        "parent_id": parent_id,
        "level": level,
        "title": title,
        "sort_order": sort_order,
        "description": description,
    }


def list_course_chapters(
    db: Session,
    course_id: str,
) -> dict:
    """
    获取指定课程的章节列表。
    """

    # 1. 先确认课程存在
    course = db.execute(
        text(
            """
            SELECT course_id
            FROM courses
            WHERE course_id = :course_id
            LIMIT 1
            """
        ),
        {"course_id": course_id},
    ).mappings().first()

    if course is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="课程不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # 2. 查询课程章节
    rows = db.execute(
        text(
            """
            SELECT
                id,
                course_id,
                parent_id,
                level,
                title,
                description,
                sort_order,
                created_at,
                updated_at
            FROM course_chapters
            WHERE course_id = :course_id
            ORDER BY COALESCE(parent_id, id) ASC, level ASC, sort_order ASC, created_at ASC
            """
        ),
        {"course_id": course_id},
    ).mappings().all()

    items = []

    for row in rows:
        items.append(
            {
                "chapter_id": row["id"],
                "course_id": row["course_id"],
                "parent_id": row["parent_id"],
                "level": row["level"],
                "title": row["title"],
                "description": row["description"],
                "sort_order": row["sort_order"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            }
        )

    return {
        "course_id": course_id,
        "total": len(items),
        "items": items,
    }


def create_knowledge_point(
    db: Session,
    course_id: str,
    chapter_id: str,
    name: str,
    description: str | None = None,
    difficulty: str | None = "基础",
    sort_order: int = 0,
) -> dict:
    """
    给指定课程章节新增知识点。
    """

    # 1. 先确认课程存在
    course = db.execute(
        text(
            """
            SELECT course_id
            FROM courses
            WHERE course_id = :course_id
            LIMIT 1
            """
        ),
        {"course_id": course_id},
    ).mappings().first()

    if course is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="课程不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # 2. 确认章节存在，并且属于这门课程
    chapter = db.execute(
        text(
            """
            SELECT id
            FROM course_chapters
            WHERE id = :chapter_id
              AND course_id = :course_id
            LIMIT 1
            """
        ),
        {
            "chapter_id": chapter_id,
            "course_id": course_id,
        },
    ).mappings().first()

    if chapter is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="章节不存在或不属于该课程",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # 3. 同一章节下不建议重复创建同名知识点
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
            "name": name,
        },
    ).mappings().first()

    if existing is not None:
        raise AppException(
            code=ErrorCode.CONFLICT,
            message="该章节下已存在同名知识点",
            status_code=status.HTTP_409_CONFLICT,
        )

    # 4. 新增知识点
    knowledge_point_id = "kp_" + uuid.uuid4().hex[:12]

    db.execute(
        text(
            """
            INSERT INTO knowledge_points (
                id,
                course_id,
                chapter_id,
                name,
                description,
                difficulty,
                sort_order,
                created_at,
                updated_at
            )
            VALUES (
                :id,
                :course_id,
                :chapter_id,
                :name,
                :description,
                :difficulty,
                :sort_order,
                NOW(),
                NOW()
            )
            """
        ),
        {
            "id": knowledge_point_id,
            "course_id": course_id,
            "chapter_id": chapter_id,
            "name": name,
            "description": description,
            "difficulty": difficulty,
            "sort_order": sort_order,
        },
    )

    db.commit()

    return {
        "knowledge_point_id": knowledge_point_id,
        "course_id": course_id,
        "chapter_id": chapter_id,
        "name": name,
        "description": description,
        "difficulty": difficulty,
        "sort_order": sort_order,
    }


def list_knowledge_points(
    db: Session,
    course_id: str,
    chapter_id: str | None = None,
) -> dict:
    """
    查询某门课程下的知识点列表。

    如果传 chapter_id：
    - 只查询该章节下的知识点

    如果不传 chapter_id：
    - 查询整门课程下的所有知识点
    """

    # 1. 先确认课程存在
    course = db.execute(
        text(
            """
            SELECT course_id
            FROM courses
            WHERE course_id = :course_id
            LIMIT 1
            """
        ),
        {"course_id": course_id},
    ).mappings().first()

    if course is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="课程不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # 2. 如果传了 chapter_id，确认章节属于当前课程
    if chapter_id:
        chapter = db.execute(
            text(
                """
                SELECT id
                FROM course_chapters
                WHERE id = :chapter_id
                  AND course_id = :course_id
                LIMIT 1
                """
            ),
            {
                "chapter_id": chapter_id,
                "course_id": course_id,
            },
        ).mappings().first()

        if chapter is None:
            raise AppException(
                code=ErrorCode.NOT_FOUND,
                message="章节不存在或不属于该课程",
                status_code=status.HTTP_404_NOT_FOUND,
            )

    # 3. 查询知识点
    if chapter_id:
        rows = db.execute(
            text(
                """
                SELECT
                    kp.id,
                    kp.course_id,
                    kp.chapter_id,
                    kp.name,
                    kp.description,
                    kp.difficulty,
                    kp.sort_order,
                    kp.created_at,
                    kp.updated_at,
                    ch.title AS chapter_title
                FROM knowledge_points kp
                LEFT JOIN course_chapters ch ON ch.id = kp.chapter_id
                WHERE kp.course_id = :course_id
                  AND kp.chapter_id = :chapter_id
                ORDER BY ch.sort_order ASC, kp.sort_order ASC, kp.created_at ASC
                """
            ),
            {
                "course_id": course_id,
                "chapter_id": chapter_id,
            },
        ).mappings().all()
    else:
        rows = db.execute(
            text(
                """
                SELECT
                    kp.id,
                    kp.course_id,
                    kp.chapter_id,
                    kp.name,
                    kp.description,
                    kp.difficulty,
                    kp.sort_order,
                    kp.created_at,
                    kp.updated_at,
                    ch.title AS chapter_title
                FROM knowledge_points kp
                LEFT JOIN course_chapters ch ON ch.id = kp.chapter_id
                WHERE kp.course_id = :course_id
                ORDER BY ch.sort_order ASC, kp.sort_order ASC, kp.created_at ASC
                """
            ),
            {
                "course_id": course_id,
            },
        ).mappings().all()

    items = []

    for row in rows:
        items.append(
            {
                "knowledge_point_id": row["id"],
                "course_id": row["course_id"],
                "chapter_id": row["chapter_id"],
                "chapter_title": row["chapter_title"],
                "name": row["name"],
                "description": row["description"],
                "difficulty": row["difficulty"],
                "sort_order": row["sort_order"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            }
        )

    return {
        "course_id": course_id,
        "chapter_id": chapter_id,
        "total": len(items),
        "items": items,
    }


def list_vector_index_records(
    db: Session,
    course_id: str,
) -> dict:
    """
    查询某门课程的向量索引任务记录。
    """

    rows = db.execute(
        text(
            """
            SELECT
                id,
                course_id,
                document_id,
                index_type,
                collection_name,
                status,
                chunk_count,
                success_count,
                failed_count,
                error_message,
                started_at,
                finished_at,
                created_by
            FROM vector_index_records
            WHERE course_id = :course_id
            ORDER BY started_at DESC
            """
        ),
        {"course_id": course_id},
    ).mappings().all()

    items = []

    for row in rows:
        items.append(
            {
                "index_record_id": row["id"],
                "course_id": row["course_id"],
                "document_id": row["document_id"],
                "index_type": row["index_type"],
                "collection_name": row["collection_name"],
                "status": row["status"],
                "chunk_count": row["chunk_count"] or 0,
                "success_count": row["success_count"] or 0,
                "failed_count": row["failed_count"] or 0,
                "error_message": row["error_message"],
                "started_at": row["started_at"].isoformat() if row["started_at"] else None,
                "finished_at": row["finished_at"].isoformat() if row["finished_at"] else None,
                "created_by": row["created_by"],
            }
        )

    return {
        "course_id": course_id,
        "total": len(items),
        "items": items,
    }


def link_course_document_to_chapter_and_knowledge_point(
    db: Session,
    course_id: str,
    document_id: str,
    chapter_id: str,
    knowledge_point_id: str | None = None,
) -> dict:
    """
    将课程资料关联到章节 / 知识点。

    作用：
    1. 更新 course_documents.chapter_id
    2. 更新 knowledge_chunks.chapter_id / knowledge_point_id
    3. 更新 Chroma metadata
    """

    # 1. 确认课程存在
    course = db.execute(
        text(
            """
            SELECT course_id
            FROM courses
            WHERE course_id = :course_id
            LIMIT 1
            """
        ),
        {"course_id": course_id},
    ).mappings().first()

    if course is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="课程不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # 2. 确认文档存在，并且属于该课程
    document = db.execute(
        text(
            """
            SELECT id
            FROM course_documents
            WHERE id = :document_id
              AND course_id = :course_id
              AND COALESCE(status, 'active') <> 'deleted'
            LIMIT 1
            """
        ),
        {
            "document_id": document_id,
            "course_id": course_id,
        },
    ).mappings().first()

    if document is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="课程资料不存在或不属于该课程",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # 3. 确认章节存在，并且属于该课程
    chapter = db.execute(
        text(
            """
            SELECT id
            FROM course_chapters
            WHERE id = :chapter_id
              AND course_id = :course_id
            LIMIT 1
            """
        ),
        {
            "chapter_id": chapter_id,
            "course_id": course_id,
        },
    ).mappings().first()

    if chapter is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="章节不存在或不属于该课程",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # 4. 如果传了 knowledge_point_id，确认知识点存在，并且属于该课程和该章节
    if knowledge_point_id:
        knowledge_point = db.execute(
            text(
                """
                SELECT id
                FROM knowledge_points
                WHERE id = :knowledge_point_id
                  AND course_id = :course_id
                  AND chapter_id = :chapter_id
                LIMIT 1
                """
            ),
            {
                "knowledge_point_id": knowledge_point_id,
                "course_id": course_id,
                "chapter_id": chapter_id,
            },
        ).mappings().first()

        if knowledge_point is None:
            raise AppException(
                code=ErrorCode.NOT_FOUND,
                message="知识点不存在，或不属于该课程章节",
                status_code=status.HTTP_404_NOT_FOUND,
            )

    # 5. 更新 course_documents
    db.execute(
        text(
            """
            UPDATE course_documents
            SET chapter_id = :chapter_id,
                updated_at = NOW()
            WHERE id = :document_id
              AND course_id = :course_id
            """
        ),
        {
            "chapter_id": chapter_id,
            "document_id": document_id,
            "course_id": course_id,
        },
    )

    # 6. 更新 knowledge_chunks
    result = db.execute(
        text(
            """
            UPDATE knowledge_chunks
            SET chapter_id = :chapter_id,
                knowledge_point_id = :knowledge_point_id
            WHERE document_id = :document_id
              AND course_id = :course_id
              AND COALESCE(deleted, 0) = 0
            """
        ),
        {
            "chapter_id": chapter_id,
            "knowledge_point_id": knowledge_point_id,
            "document_id": document_id,
            "course_id": course_id,
        },
    )

    updated_chunks = result.rowcount or 0

    # 7. 同步更新 Chroma metadata
    updated_chroma_chunks = update_document_chunks_metadata_in_chroma(
        document_id=document_id,
        metadata_patch={
            "chapter_id": chapter_id,
            "knowledge_point_id": knowledge_point_id,
        },
    )

    db.commit()

    return {
        "document_id": document_id,
        "course_id": course_id,
        "chapter_id": chapter_id,
        "knowledge_point_id": knowledge_point_id,
        "updated_chunks": updated_chunks,
        "updated_chroma_chunks": updated_chroma_chunks,
        "linked": True,
    }


def list_vector_index_records(
    db: Session,
    course_id: str,
) -> dict:
    """
    查询某门课程的向量索引任务记录。

    用于 Vue 知识库管理页查看：
    1. 哪些资料已经完成索引
    2. 哪些资料索引失败
    3. 每次索引生成了多少 chunks
    """

    # 1. 确认课程存在
    course = db.execute(
        text(
            """
            SELECT course_id
            FROM courses
            WHERE course_id = :course_id
            LIMIT 1
            """
        ),
        {"course_id": course_id},
    ).mappings().first()

    if course is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="课程不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # 2. 查询索引记录，同时关联文档名称
    rows = db.execute(
        text(
            """
            SELECT
                vir.id,
                vir.course_id,
                vir.document_id,
                cd.filename,
                vir.index_type,
                vir.collection_name,
                vir.status,
                vir.chunk_count,
                vir.success_count,
                vir.failed_count,
                vir.error_message,
                vir.started_at,
                vir.finished_at,
                vir.created_by
            FROM vector_index_records vir
            LEFT JOIN course_documents cd ON cd.id = vir.document_id
            WHERE vir.course_id = :course_id
            ORDER BY vir.started_at DESC
            """
        ),
        {"course_id": course_id},
    ).mappings().all()

    items = []

    for row in rows:
        items.append(
            {
                "index_record_id": row["id"],
                "course_id": row["course_id"],
                "document_id": row["document_id"],
                "filename": row["filename"],
                "index_type": row["index_type"],
                "collection_name": row["collection_name"],
                "status": row["status"],
                "chunk_count": row["chunk_count"] or 0,
                "success_count": row["success_count"] or 0,
                "failed_count": row["failed_count"] or 0,
                "error_message": row["error_message"],
                "started_at": row["started_at"].isoformat() if row["started_at"] else None,
                "finished_at": row["finished_at"].isoformat() if row["finished_at"] else None,
                "created_by": row["created_by"],
            }
        )

    return {
        "course_id": course_id,
        "total": len(items),
        "items": items,
    }


def reindex_course_document(
    db: Session,
    course_id: str,
    document_id: str,
    created_by: str,
) -> dict:
    """
    重新索引指定文档：
    - 生成 chunks
    - 写入 Chroma
    - 更新 knowledge_chunks
    - 新增 vector_index_records
    """
    # 1. 查询文档
    doc = db.execute(
        text(
            """
            SELECT *
            FROM course_documents
            WHERE id = :document_id
              AND course_id = :course_id
              AND COALESCE(status, 'active') <> 'deleted'
            """
        ),
        {"document_id": document_id, "course_id": course_id},
    ).mappings().first()

    if not doc:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="文档不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # 2. 调用你已有的上传/索引逻辑
    # 这里复用现有方法 upload_and_index_course_document
    # 需要传 file_path、filename、course_id、uploaded_by
    from app.services.rag_service import upload_and_index_course_document

    index_record = upload_and_index_course_document(
        db=db,
        course_id=course_id,
        file_path=doc["file_path"],
        filename=doc["filename"],
        uploaded_by=created_by,
        reindex=True,  # 标记为重建索引
    )

    return index_record


def delete_course_document_and_chunks(
    db: Session,
    course_id: str,
    document_id: str,
    deleted_by: str,
):
    """
    删除文档，同时删除对应知识块和 Chroma 向量。
    """

    # 1. 查询文档是否存在
    doc = db.execute(
        text(
            "SELECT * FROM course_documents WHERE id = :document_id AND course_id = :course_id"
        ),
        {"document_id": document_id, "course_id": course_id},
    ).mappings().first()

    if not doc:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="文档不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # 2. 删除 Chroma 中对应向量
    try:
        chroma_deleted_chunks = delete_document_chunks_from_chroma(
            document_id=document_id
        )
    except Exception as e:
        chroma_deleted_chunks = 0
        print(f"[WARN] 删除 Chroma 向量失败: {e}")

    # 3. 逻辑删除 MySQL knowledge_chunks
    chunk_count_row = db.execute(
        text(
            """
            SELECT COUNT(*) AS total
            FROM knowledge_chunks
            WHERE document_id = :document_id
              AND course_id = :course_id
            """
        ),
        {
            "document_id": document_id,
            "course_id": course_id,
        },
    ).mappings().first()

    mysql_deleted_chunks = int(chunk_count_row["total"] or 0)

    db.execute(
        text(
            """
            UPDATE knowledge_chunks
            SET deleted = TRUE
            WHERE document_id = :document_id
              AND course_id = :course_id
              AND COALESCE(deleted, 0) = 0
            """
        ),
        {
            "document_id": document_id,
            "course_id": course_id,
        },
    )

    db.execute(
        text(
            """
            UPDATE course_documents
            SET status = 'deleted',
                parse_status = 'deleted',
                index_status = 'deleted',
                updated_at = NOW()
            WHERE id = :document_id
              AND course_id = :course_id
            """
        ),
        {
            "document_id": document_id,
            "course_id": course_id,
        },
    )
    db.commit()

    return {
        "course_id": course_id,
        "document_id": document_id,
        "deleted_by": deleted_by,
        "mysql_deleted_chunks": mysql_deleted_chunks,
        "chroma_deleted_chunks": chroma_deleted_chunks,
        "status": "deleted",
    }
