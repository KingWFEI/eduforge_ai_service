import json
import os
import uuid
from pathlib import Path
from typing import Any, List

import chromadb
import numpy as np
from fastapi import UploadFile, status
from sentence_transformers import SentenceTransformer
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agents.chunk_classifier_agent import ChunkClassifierAgent
from app.services.document_asset_service import load_document_assets, prepare_document_assets
from app.services.markdown_document_service import (
    convert_file_to_markdown,
    match_chunk_to_structure,
    split_markdown_into_chunks,
)
from app.services.llm_service import DeepSeekService
from app.utils.response import AppException, ErrorCode

_MODEL = None
_CHROMA_CLIENT = None
_COLLECTION = None

CHROMA_DIR = "chroma_db"
COLLECTION_NAME = "eduforge_knowledge_chunks"
RAG_RELEVANCE_THRESHOLD = float(os.getenv("RAG_RELEVANCE_THRESHOLD", "0.5"))
RELEVANT_DOCUMENT_LIMIT = 10
RELEVANT_DOCUMENT_CANDIDATE_CHUNKS = 50
EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL_NAME",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
EMBEDDING_LOCAL_FILES_ONLY = os.getenv("EMBEDDING_LOCAL_FILES_ONLY", "false").lower() == "true"
SUPPORTED_DOCUMENT_EXTENSIONS = {
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".py",
    ".dot",
    ".pdf",
    ".docx",
    ".pptx",
    ".ipynb",
}
SUPPORTED_DOCUMENT_TYPES_MESSAGE = "仅支持 txt、md、csv、json、py、dot、pdf、docx、pptx、ipynb 文件"


def get_embedding_model():
    """
    懒加载向量模型。
    第一次调用会下载模型，后面复用。
    """
    global _MODEL

    if _MODEL is None:
        try:
            _MODEL = SentenceTransformer(
                EMBEDDING_MODEL_NAME,
                local_files_only=EMBEDDING_LOCAL_FILES_ONLY,
            )
        except Exception as exc:
            raise AppException(
                code=ErrorCode.KNOWLEDGE_RETRIEVAL_ERROR,
                message=(
                    "向量模型未就绪，暂时无法解析并索引课程资料。"
                    "请检查服务器网络，或提前下载/缓存 embedding 模型后重试。"
                ),
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from exc

    return _MODEL


def ensure_embedding_model_ready() -> None:
    get_embedding_model()


def embed_text(text_value: str) -> List[float]:
    model = get_embedding_model()
    vector = model.encode(text_value, normalize_embeddings=True)
    return vector.tolist()


def get_chroma_collection():
    """
    获取 Chroma collection。
    所有课程的知识块都放在同一个 collection 里，
    通过 metadata.course_id 过滤。
    """
    global _CHROMA_CLIENT, _COLLECTION

    if _CHROMA_CLIENT is None:
        _CHROMA_CLIENT = chromadb.PersistentClient(path=CHROMA_DIR)

    if _COLLECTION is None:
        _COLLECTION = _CHROMA_CLIENT.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    return _COLLECTION


def extract_text_from_file(file_path: str) -> str:
    """Convert an uploaded document to Markdown-compatible text."""
    suffix = Path(file_path).suffix.lower()

    if suffix not in SUPPORTED_DOCUMENT_EXTENSIONS:
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message=SUPPORTED_DOCUMENT_TYPES_MESSAGE,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return convert_file_to_markdown(file_path)


def split_text(text_value: str, chunk_size: int = 500, overlap: int = 80) -> List[str]:
    """
    简单按字符切块。
    先跑通 RAG，后面再优化为按标题、段落切分。
    """
    text_value = text_value.replace("\r\n", "\n").strip()

    if not text_value:
        return []

    chunks = []
    start = 0

    while start < len(text_value):
        end = start + chunk_size
        chunk = text_value[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start = end - overlap

        if start < 0:
            start = 0

        if start >= len(text_value):
            break

    return chunks


def _normalize_text(value: str | None) -> str:
    return (value or "").replace(" ", "").replace("\n", "").lower()


def _load_course_structure(db: Session, course_id: str) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT
                kp.id AS knowledge_point_id,
                kp.name AS knowledge_point_name,
                kp.description AS knowledge_point_description,
                sec.id AS section_id,
                sec.title AS section_title,
                ch.id AS chapter_id,
                ch.title AS chapter_title
            FROM knowledge_points kp
            LEFT JOIN course_chapters sec ON sec.id = kp.chapter_id
            LEFT JOIN course_chapters ch ON ch.id = COALESCE(sec.parent_id, sec.id)
            WHERE kp.course_id = :course_id
            ORDER BY ch.sort_order ASC, sec.sort_order ASC, kp.sort_order ASC
            """
        ),
        {"course_id": course_id},
    ).mappings().all()
    return [dict(row) for row in rows]


def _infer_chunk_structure(
    chunk: str,
    structure_items: list[dict[str, Any]],
) -> tuple[str | None, str | None, list[str]]:
    normalized_chunk = _normalize_text(chunk)
    best_item = None
    best_score = 0
    keywords: list[str] = []

    for item in structure_items:
        score = 0
        candidates = [
            ("knowledge_point_name", 5),
            ("section_title", 3),
            ("chapter_title", 2),
        ]
        for key, weight in candidates:
            value = item.get(key)
            if value and _normalize_text(str(value)) in normalized_chunk:
                score += weight
        if score > best_score:
            best_item = item
            best_score = score

    if best_item is None:
        return None, None, keywords

    for key in ("chapter_title", "section_title", "knowledge_point_name"):
        value = best_item.get(key)
        if value:
            keywords.append(str(value))

    return (
        best_item.get("section_id") or best_item.get("chapter_id"),
        best_item.get("knowledge_point_id"),
        keywords,
    )


def _infer_chunk_structures_with_llm(
    chunks: list[str],
    structure_items: list[dict[str, Any]],
    batch_size: int = 12,
) -> dict[int, tuple[str | None, str | None, list[str]]]:
    if not chunks or not structure_items:
        return {}

    structure_payload = []
    valid_chapter_ids = set()
    valid_knowledge_point_ids = set()
    for item in structure_items:
        chapter_id = item.get("section_id") or item.get("chapter_id")
        knowledge_point_id = item.get("knowledge_point_id")
        if chapter_id:
            valid_chapter_ids.add(chapter_id)
        if knowledge_point_id:
            valid_knowledge_point_ids.add(knowledge_point_id)
        structure_payload.append(
            {
                "chapter_id": chapter_id,
                "chapter_title": item.get("chapter_title"),
                "section_title": item.get("section_title"),
                "knowledge_point_id": knowledge_point_id,
                "knowledge_point_name": item.get("knowledge_point_name"),
                "knowledge_point_description": item.get("knowledge_point_description"),
            }
        )

    assignments: dict[int, tuple[str | None, str | None, list[str]]] = {}
    llm = DeepSeekService()

    for start in range(0, len(chunks), batch_size):
        batch = [
            {
                "chunk_index": index,
                "content": chunks[index][:900],
            }
            for index in range(start, min(start + batch_size, len(chunks)))
        ]
        prompt = f"""
你是 EduForge AI 的课程知识块归属识别智能体。

请根据课程结构，为每个 chunk 选择最匹配的 chapter_id 和 knowledge_point_id。

课程结构：
{json.dumps(structure_payload, ensure_ascii=False, indent=2)}

待识别 chunks：
{json.dumps(batch, ensure_ascii=False, indent=2)}

要求：
1. chapter_id 必须来自课程结构中的 chapter_id。
2. knowledge_point_id 必须来自课程结构中的 knowledge_point_id。
3. 如果无法判断，chapter_id 和 knowledge_point_id 返回 null。
4. confidence 为 0 到 1。
5. keywords 返回用于解释匹配的短关键词。
6. 严格输出 JSON 对象。

JSON 格式：
{{
  "assignments": [
    {{
      "chunk_index": 0,
      "chapter_id": null,
      "knowledge_point_id": null,
      "confidence": 0.0,
      "keywords": []
    }}
  ]
}}
"""
        try:
            result = llm.generate_json_sync(
                system_prompt="你是课程结构识别智能体，只输出合法 JSON。",
                user_prompt=prompt,
                max_tokens=3000,
                temperature=0.1,
            )
        except Exception:
            continue

        rows = result.get("assignments", [])
        if not isinstance(rows, list):
            continue

        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                chunk_index = int(row.get("chunk_index"))
            except (TypeError, ValueError):
                continue
            if chunk_index < 0 or chunk_index >= len(chunks):
                continue

            chapter_id = row.get("chapter_id")
            knowledge_point_id = row.get("knowledge_point_id")
            if chapter_id not in valid_chapter_ids:
                chapter_id = None
            if knowledge_point_id not in valid_knowledge_point_ids:
                knowledge_point_id = None

            keywords = row.get("keywords") or []
            if not isinstance(keywords, list):
                keywords = []
            assignments[chunk_index] = (
                chapter_id,
                knowledge_point_id,
                [str(keyword)[:50] for keyword in keywords[:8]],
            )

    return assignments


def rebuild_course_document_index_with_structure(
    db: Session,
    course_id: str,
    document_id: str,
    created_by: str | None = None,
) -> dict:
    document = db.execute(
        text(
            """
            SELECT id, filename, file_path
            FROM course_documents
            WHERE id = :document_id
              AND course_id = :course_id
              AND COALESCE(status, 'active') <> 'deleted'
            LIMIT 1
            """
        ),
        {"document_id": document_id, "course_id": course_id},
    ).mappings().first()

    if document is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="课程资料不存在或不属于该课程",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    structure_items = _load_course_structure(db, course_id)
    markdown = extract_text_from_file(document["file_path"])
    markdown, assets = prepare_document_assets(
        markdown=markdown,
        file_path=document["file_path"],
        course_id=course_id,
        document_id=document_id,
    )
    structured_chunks = split_markdown_into_chunks(markdown)
    if not structured_chunks:
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message="文件内容为空，无法生成知识块。如果是扫描版 PDF，需要 OCR。",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    delete_document_chunks_from_chroma(document_id=document_id)
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
        {"document_id": document_id, "course_id": course_id},
    )

    index_record_id = "idx_" + uuid.uuid4().hex[:12]
    db.execute(
        text(
            """
            INSERT INTO vector_index_records (
                id, course_id, document_id, index_type, collection_name,
                status, chunk_count, success_count, failed_count,
                error_message, started_at, finished_at, created_by, created_at
            )
            VALUES (
                :id, :course_id, :document_id, 'chroma', :collection_name,
                'processing', 0, 0, 0, NULL, NOW(), NULL, :created_by, NOW()
            )
            """
        ),
        {
            "id": index_record_id,
            "course_id": course_id,
            "document_id": document_id,
            "collection_name": COLLECTION_NAME,
            "created_by": created_by,
        },
    )

    collection = get_chroma_collection()
    ids = []
    documents = []
    embeddings = []
    metadatas = []
    first_chapter_id = None
    deterministic_assignments = {
        index: match_chunk_to_structure(chunk, structure_items)
        for index, chunk in enumerate(structured_chunks)
    }
    unresolved_indexes = [
        index
        for index, assignment in deterministic_assignments.items()
        if assignment[0] is None
    ]
    llm_assignments: dict[int, tuple[str | None, str | None, list[str]]] = {}
    try:
        classifier_result = ChunkClassifierAgent().run_sync(
            {
                "chunks": [
                    structured_chunks[index].content
                    for index in unresolved_indexes
                ],
                "structure_items": structure_items,
                "batch_size": 12,
            }
        )
        unresolved_assignments = classifier_result.get("assignments", {})
        if isinstance(unresolved_assignments, dict):
            llm_assignments = {
                unresolved_indexes[relative_index]: assignment
                for relative_index, assignment in unresolved_assignments.items()
                if isinstance(relative_index, int)
                and 0 <= relative_index < len(unresolved_indexes)
            }
    except Exception:
        llm_assignments = {}

    for index, structured_chunk in enumerate(structured_chunks):
        chunk = structured_chunk.content
        chunk_id = "chunk_" + uuid.uuid4().hex[:12]
        deterministic = deterministic_assignments[index]
        chapter_id, knowledge_point_id, keywords = (
            deterministic
            if deterministic[0] is not None
            else llm_assignments.get(
                index,
                _infer_chunk_structure(chunk, structure_items),
            )
        )
        if first_chapter_id is None and chapter_id:
            first_chapter_id = chapter_id
        section = (structured_chunk.section or document["filename"])[:200]
        embedding = embed_text(chunk)
        metadata = {
            "course_id": course_id,
            "document_id": document_id,
            "filename": document["filename"],
            "chunk_index": index,
            "section": section,
            "vector_id": chunk_id,
            "heading_title": structured_chunk.heading_title or "",
            "heading_level": structured_chunk.heading_level or 0,
            "heading_path": " > ".join(structured_chunk.heading_path),
        }
        if chapter_id:
            metadata["chapter_id"] = chapter_id
        if knowledge_point_id:
            metadata["knowledge_point_id"] = knowledge_point_id

        ids.append(chunk_id)
        documents.append(chunk)
        embeddings.append(embedding)
        metadatas.append(metadata)

        db.execute(
            text(
                """
                INSERT INTO knowledge_chunks (
                    id, course_id, document_id, chapter_id, knowledge_point_id,
                    section, content, keywords_json, page_no, chunk_index,
                    vector_id, indexed, deleted, created_at
                )
                VALUES (
                    :id, :course_id, :document_id, :chapter_id, :knowledge_point_id,
                    :section, :content, :keywords_json, NULL, :chunk_index,
                    :vector_id, 1, FALSE, NOW()
                )
                """
            ),
            {
                "id": chunk_id,
                "course_id": course_id,
                "document_id": document_id,
                "chapter_id": chapter_id,
                "knowledge_point_id": knowledge_point_id,
                "section": section,
                "content": chunk,
                "keywords_json": json.dumps(keywords, ensure_ascii=False),
                "chunk_index": index,
                "vector_id": chunk_id,
            },
        )

    collection.add(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)

    db.execute(
        text(
            """
            UPDATE course_documents
            SET chapter_id = :chapter_id,
                parse_status = 'parsed',
                index_status = 'indexed',
                chunk_count = :chunk_count,
                updated_at = NOW()
            WHERE id = :document_id
              AND course_id = :course_id
            """
        ),
        {
            "chapter_id": first_chapter_id,
            "chunk_count": len(structured_chunks),
            "document_id": document_id,
            "course_id": course_id,
        },
    )
    db.execute(
        text(
            """
            UPDATE vector_index_records
            SET status = 'completed',
                chunk_count = :chunk_count,
                success_count = :success_count,
                failed_count = 0,
                error_message = NULL,
                finished_at = NOW()
            WHERE id = :index_record_id
            """
        ),
        {
            "chunk_count": len(structured_chunks),
            "success_count": len(structured_chunks),
            "index_record_id": index_record_id,
        },
    )

    return {
        "document_id": document_id,
        "chunk_count": len(structured_chunks),
        "index_record_id": index_record_id,
        "asset_count": len(assets),
        "assets": load_document_assets(course_id, document_id),
    }


def upload_and_index_course_document(
    db: Session,
    course_id: str,
    file: UploadFile,
    current_user_id: str | None = None,
    chapter_id: str | None = None,
    description: str | None = None,
) -> dict:
    """
    上传课程资料：
    1. 保存文件到本地
    2. 保存文档记录到 course_documents
    3. 创建 vector_index_records 索引任务记录
    4. 解析文本
    5. 切分 chunks
    6. chunks 写入 Chroma
    7. chunks 同步写入 MySQL knowledge_chunks
    8. 更新索引任务状态
    """

    if not file.filename:
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message="文件名不能为空",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    file_suffix = Path(file.filename).suffix.lower()

    if file_suffix not in SUPPORTED_DOCUMENT_EXTENSIONS:
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message=SUPPORTED_DOCUMENT_TYPES_MESSAGE,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

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
            message="课程不存在，请先创建课程后再上传资料",
            status_code=status.HTTP_404_NOT_FOUND,
        )

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

    ensure_embedding_model_ready()

    document_id = "doc_" + uuid.uuid4().hex[:12]
    index_record_id = "idx_" + uuid.uuid4().hex[:12]

    upload_dir = Path("uploads") / "course_documents" / course_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_filename = file.filename.replace("\\", "_").replace("/", "_")
    file_path = upload_dir / f"{document_id}_{safe_filename}"

    file_bytes = file.file.read()

    with open(file_path, "wb") as f:
        f.write(file_bytes)

    file_type = file_suffix.replace(".", "")
    file_size = len(file_bytes)

    try:
        # 2. 先插入文档记录，初始状态为 processing
        db.execute(
            text(
                """
                INSERT INTO course_documents (
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
                )
                VALUES (
                    :id,
                    :course_id,
                    :chapter_id,
                    :filename,
                    :file_path,
                    :file_type,
                    :file_size,
                    :description,
                    'active',
                    'processing',
                    'processing',
                    0,
                    :uploaded_by,
                    NOW(),
                    NOW()
                )
                """
            ),
            {
                "id": document_id,
                "course_id": course_id,
                "chapter_id": chapter_id,
                "filename": file.filename,
                "file_path": str(file_path),
                "file_type": file_type,
                "file_size": file_size,
                "description": description,
                "uploaded_by": current_user_id,
            },
        )

        # 3. 创建索引任务记录
        db.execute(
            text(
                """
                INSERT INTO vector_index_records (
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
                    created_by,
                    created_at
                )
                VALUES (
                    :id,
                    :course_id,
                    :document_id,
                    'chroma',
                    :collection_name,
                    'processing',
                    0,
                    0,
                    0,
                    NULL,
                    NOW(),
                    NULL,
                    :created_by,
                    NOW()
                )
                """
            ),
            {
                "id": index_record_id,
                "course_id": course_id,
                "document_id": document_id,
                "collection_name": COLLECTION_NAME,
                "created_by": current_user_id,
            },
        )

        db.commit()

        # 4. 转换为 Markdown，并按标题层级切分
        markdown = extract_text_from_file(str(file_path))
        markdown, assets = prepare_document_assets(
            markdown=markdown,
            file_path=str(file_path),
            course_id=course_id,
            document_id=document_id,
        )
        structured_chunks = split_markdown_into_chunks(markdown)

        if not structured_chunks:
            raise AppException(
                code=ErrorCode.PARAM_ERROR,
                message="文件内容为空，无法生成知识块。如果是扫描版 PDF，需要 OCR。",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # 5. 写入 Chroma，同时准备写 MySQL knowledge_chunks
        collection = get_chroma_collection()

        ids = []
        documents = []
        embeddings = []
        metadatas = []

        mysql_chunk_rows = []

        for index, structured_chunk in enumerate(structured_chunks):
            chunk = structured_chunk.content
            chunk_id = "chunk_" + uuid.uuid4().hex[:12]
            section = (
                structured_chunk.section or f"{file.filename} - 片段 {index + 1}"
            )[:200]
            embedding = embed_text(chunk)

            # Chroma 数据
            ids.append(chunk_id)
            documents.append(chunk)
            embeddings.append(embedding)
            metadata = {
                "course_id": course_id,
                "document_id": document_id,
                "filename": file.filename,
                "chunk_index": index,
                "section": section,
                "vector_id": chunk_id,
                "heading_title": structured_chunk.heading_title or "",
                "heading_level": structured_chunk.heading_level or 0,
                "heading_path": " > ".join(structured_chunk.heading_path),
            }
            if chapter_id:
                metadata["chapter_id"] = chapter_id
            metadatas.append(metadata)

            # MySQL knowledge_chunks 数据
            mysql_chunk_rows.append(
                {
                    "id": chunk_id,
                    "course_id": course_id,
                    "document_id": document_id,
                    "chapter_id": chapter_id,
                    "section": section,
                    "content": chunk,
                    "keywords_json": json.dumps([], ensure_ascii=False),
                    "chunk_index": index,
                    "vector_id": chunk_id,
                }
            )

        collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        # 6. 同步写入 MySQL knowledge_chunks
        for row in mysql_chunk_rows:
            db.execute(
                text(
                    """
                    INSERT INTO knowledge_chunks (
                        id,
                        course_id,
                        document_id,
                        chapter_id,
                        knowledge_point_id,
                        section,
                        content,
                        keywords_json,
                        page_no,
                        chunk_index,
                        vector_id,
                        indexed,
                        deleted,
                        created_at
                    )
                    VALUES (
                        :id,
                        :course_id,
                        :document_id,
                        :chapter_id,
                        NULL,
                        :section,
                        :content,
                        :keywords_json,
                        NULL,
                        :chunk_index,
                        :vector_id,
                        1,
                        FALSE,
                        NOW()
                    )
                    """
                ),
                row,
            )

        # 7. 更新 course_documents 状态
        db.execute(
            text(
                """
                UPDATE course_documents
                SET parse_status = 'parsed',
                    index_status = 'indexed',
                    chunk_count = :chunk_count,
                    updated_at = NOW()
                WHERE id = :document_id
                  AND course_id = :course_id
                """
            ),
            {
                "chunk_count": len(structured_chunks),
                "document_id": document_id,
                "course_id": course_id,
            },
        )

        # 8. 更新索引任务记录
        db.execute(
            text(
                """
                UPDATE vector_index_records
                SET status = 'completed',
                    chunk_count = :chunk_count,
                    success_count = :success_count,
                    failed_count = 0,
                    error_message = NULL,
                    finished_at = NOW()
                WHERE id = :index_record_id
                """
            ),
            {
                "chunk_count": len(structured_chunks),
                "success_count": len(structured_chunks),
                "index_record_id": index_record_id,
            },
        )

        db.commit()

        return {
            "document_id": document_id,
            "course_id": course_id,
            "filename": file.filename,
            "chunk_count": len(structured_chunks),
            "parse_status": "parsed",
            "index_status": "indexed",
            "asset_count": len(assets),
            "assets": load_document_assets(course_id, document_id),
        }

    except Exception as e:
        db.rollback()

        error_message = str(e)

        # 尽量更新文档失败状态
        try:
            db.execute(
                text(
                    """
                    UPDATE course_documents
                    SET parse_status = 'failed',
                        index_status = 'failed',
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

            db.execute(
                text(
                    """
                    UPDATE vector_index_records
                    SET status = 'failed',
                        error_message = :error_message,
                        finished_at = NOW()
                    WHERE id = :index_record_id
                    """
                ),
                {
                    "index_record_id": index_record_id,
                    "error_message": error_message,
                },
            )

            db.commit()
        except Exception:
            db.rollback()

        if isinstance(e, AppException):
            raise e

        raise AppException(
            code=ErrorCode.SERVER_ERROR,
            message=f"资料解析或 Chroma 向量索引失败：{error_message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


def build_chroma_where(
    course_id: str,
    chapter_id: str | None = None,
    knowledge_point_id: str | None = None,
) -> dict:
    """
    构造 Chroma metadata 过滤条件。

    只传 course_id：
    where = {"course_id": "course_ai_basic"}

    传 course_id + chapter_id：
    where = {
        "$and": [
            {"course_id": "course_ai_basic"},
            {"chapter_id": "ch_xxx"}
        ]
    }
    """

    conditions = [
        {"course_id": course_id}
    ]

    if chapter_id:
        conditions.append({"chapter_id": chapter_id})

    if knowledge_point_id:
        conditions.append({"knowledge_point_id": knowledge_point_id})

    if len(conditions) == 1:
        return conditions[0]

    return {
        "$and": conditions
    }


def resolve_course_id(db: Session, course_identifier: str) -> str | None:
    """Resolve either courses.course_id or numeric courses.id to course_id."""

    course = db.execute(
        text(
            """
            SELECT course_id
            FROM courses
            WHERE course_id = :course_identifier
            LIMIT 1
            """
        ),
        {"course_identifier": course_identifier},
    ).mappings().first()
    if course is not None:
        return course["course_id"]

    if course_identifier.isdigit():
        course = db.execute(
            text(
                """
                SELECT course_id
                FROM courses
                WHERE id = :course_id
                LIMIT 1
                """
            ),
            {"course_id": int(course_identifier)},
        ).mappings().first()
        if course is not None:
            return course["course_id"]

    return None


def search_knowledge_chunks(
    db: Session,
    course_id: str,
    query: str,
    top_k: int = 5,
    chapter_id: str | None = None,
    knowledge_point_id: str | None = None,
) -> dict:
    """
    在 Chroma 中做向量检索。

    支持：
    1. 按课程检索
    2. 按课程 + 章节检索
    3. 按课程 + 章节 + 知识点检索
    """

    if not query.strip():
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message="检索问题不能为空",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # 1. 先确认课程存在，并兼容移动端误传 courses.id 的情况
    resolved_course_id = resolve_course_id(db, course_id)
    if resolved_course_id is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="课程不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    course_id = resolved_course_id

    # 2. 如果传了 chapter_id，确认章节存在
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

    # 3. 如果传了 knowledge_point_id，确认知识点存在
    if knowledge_point_id:
        knowledge_point = db.execute(
            text(
                """
                SELECT id
                FROM knowledge_points
                WHERE id = :knowledge_point_id
                  AND course_id = :course_id
                LIMIT 1
                """
            ),
            {
                "knowledge_point_id": knowledge_point_id,
                "course_id": course_id,
            },
        ).mappings().first()

        if knowledge_point is None:
            raise AppException(
                code=ErrorCode.NOT_FOUND,
                message="知识点不存在或不属于该课程",
                status_code=status.HTTP_404_NOT_FOUND,
            )

    collection = get_chroma_collection()

    query_embedding = embed_text(query)

    where_filter = build_chroma_where(
        course_id=course_id,
        chapter_id=chapter_id,
        knowledge_point_id=knowledge_point_id,
    )

    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )

    ids = result.get("ids", [[]])[0]
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    active_chunk_ids = set()
    if ids:
        id_params = {f"id_{index}": chunk_id for index, chunk_id in enumerate(ids)}
        placeholders = ", ".join(f":{key}" for key in id_params)
        active_rows = db.execute(
            text(
                f"""
                SELECT kc.id
                FROM knowledge_chunks kc
                JOIN course_documents cd ON cd.id = kc.document_id
                WHERE kc.id IN ({placeholders})
                  AND COALESCE(kc.deleted, 0) = 0
                  AND COALESCE(cd.status, 'active') <> 'deleted'
                """
            ),
            id_params,
        ).mappings().all()
        active_chunk_ids = {row["id"] for row in active_rows}

    items = []

    for index, chunk_id in enumerate(ids):
        if chunk_id not in active_chunk_ids:
            continue

        metadata = metadatas[index] or {}
        distance = distances[index]

        # cosine 距离越小越相似，转成越大越好的 score
        score = round(1 - float(distance), 4)

        items.append(
            {
                "chunk_id": chunk_id,
                "document_id": metadata.get("document_id"),
                "course_id": metadata.get("course_id"),
                "chapter_id": metadata.get("chapter_id"),
                "knowledge_point_id": metadata.get("knowledge_point_id"),
                "section": metadata.get("section"),
                "content": documents[index],
                "chunk_index": metadata.get("chunk_index", 0),
                "score": score,
            }
        )

    relevant_count = sum(1 for item in items if item["score"] >= RAG_RELEVANCE_THRESHOLD)
    retrieval_accuracy = round(relevant_count / len(items), 4) if items else 0.0

    return {
        "course_id": course_id,
        "query": query,
        "total": len(items),
        "retrieval_accuracy": retrieval_accuracy,
        "relevance_threshold": RAG_RELEVANCE_THRESHOLD,
        "relevant_count": relevant_count,
        "items": items,
    }


def search_relevant_documents(
    db: Session,
    course_id: str,
    query: str,
    chapter_id: str | None = None,
    knowledge_point_id: str | None = None,
) -> dict:
    """检索并按文档聚合，返回相关度最高的 10 篇文档。"""
    search_result = search_knowledge_chunks(
        db=db,
        course_id=course_id,
        query=query,
        top_k=RELEVANT_DOCUMENT_CANDIDATE_CHUNKS,
        chapter_id=chapter_id,
        knowledge_point_id=knowledge_point_id,
    )
    chunks = search_result["items"]
    document_ids = sorted({item["document_id"] for item in chunks if item.get("document_id")})
    filenames: dict[str, str] = {}
    if document_ids:
        params = {f"document_id_{index}": value for index, value in enumerate(document_ids)}
        placeholders = ", ".join(f":{key}" for key in params)
        rows = db.execute(
            text(
                f"""
                SELECT id, filename FROM course_documents
                WHERE id IN ({placeholders})
                  AND COALESCE(status, 'active') <> 'deleted'
                """
            ),
            params,
        ).mappings().all()
        filenames = {row["id"]: row["filename"] for row in rows}

    grouped: dict[str, list[dict]] = {}
    for chunk in chunks:
        document_id = chunk.get("document_id")
        if document_id and document_id in filenames:
            grouped.setdefault(document_id, []).append(chunk)

    items = []
    for document_id, matches in grouped.items():
        matches.sort(key=lambda item: item["score"], reverse=True)
        best = matches[0]
        content = best.get("content") or ""
        items.append({
            "document_id": document_id,
            "filename": filenames.get(document_id),
            "best_score": best["score"],
            "average_score": round(sum(item["score"] for item in matches) / len(matches), 4),
            "matched_chunk_count": len(matches),
            "best_chunk_id": best["chunk_id"],
            "section": best.get("section"),
            "content_preview": content[:300] + ("..." if len(content) > 300 else ""),
        })

    items.sort(key=lambda item: (item["best_score"], item["average_score"]), reverse=True)
    items = items[:RELEVANT_DOCUMENT_LIMIT]
    return {
        "course_id": search_result["course_id"],
        "query": query,
        "total": len(items),
        "retrieval_accuracy": search_result["retrieval_accuracy"],
        "relevance_threshold": search_result["relevance_threshold"],
        "items": items,
    }


def list_knowledge_chunks(
    db: Session,
    course_id: str,
) -> dict:
    """
    查看某门课程在 Chroma 中的知识块。
    """

    collection = get_chroma_collection()

    result = collection.get(
        where={"course_id": course_id},
        include=["documents", "metadatas"],
    )

    ids = result.get("ids", [])
    documents = result.get("documents", [])
    metadatas = result.get("metadatas", [])

    items = []

    for index, chunk_id in enumerate(ids):
        metadata = metadatas[index] or {}

        items.append(
            {
                "chunk_id": chunk_id,
                "document_id": metadata.get("document_id"),
                "course_id": metadata.get("course_id"),
                "section": metadata.get("section"),
                "content": documents[index],
                "chunk_index": metadata.get("chunk_index", 0),
                "indexed": 1,
            }
        )

    items.sort(key=lambda item: (item["document_id"] or "", item["chunk_index"]))

    return {
        "course_id": course_id,
        "total": len(items),
        "items": items,
    }


def delete_document_chunks_from_chroma(document_id: str) -> int:
    """
    根据 document_id 删除 Chroma 中的知识块。
    """

    collection = get_chroma_collection()

    existing = collection.get(
        where={"document_id": document_id},
        include=["metadatas"],
    )

    ids = existing.get("ids", [])

    if not ids:
        return 0

    collection.delete(ids=ids)

    return len(ids)


def update_document_chunks_metadata_in_chroma(
    document_id: str,
    metadata_patch: dict,
) -> int:
    """
    更新 Chroma 中某个文档下所有 chunks 的 metadata。

    用途：
    当课程资料关联章节 / 知识点后，同步更新 Chroma metadata，
    这样后续可以按 chapter_id / knowledge_point_id 过滤检索。
    """

    collection = get_chroma_collection()

    existing = collection.get(
        where={"document_id": document_id},
        include=["metadatas"],
    )

    ids = existing.get("ids", [])
    metadatas = existing.get("metadatas", [])

    if not ids:
        return 0

    new_metadatas = []

    for old_metadata in metadatas:
        merged = dict(old_metadata or {})

        for key, value in metadata_patch.items():
            if value is not None:
                merged[key] = value

        new_metadatas.append(merged)

    collection.update(
        ids=ids,
        metadatas=new_metadatas,
    )

    return len(ids)


def _build_rag_context(search_items: list[dict]) -> str:
    """
    把检索到的 chunks 拼成给大模型看的上下文。
    """

    context_parts = []

    for index, item in enumerate(search_items, start=1):
        section = item.get("section") or "未知来源"
        content = item.get("content") or ""

        context_parts.append(
            f"【资料片段 {index}】\n"
            f"来源：{section}\n"
            f"内容：\n{content}\n"
        )

    return "\n".join(context_parts)


def _build_rag_system_prompt() -> str:
    """
    RAG 问答系统提示词。
    """

    return (
        "你是 EduForge-AI 智学工坊的课程知识库问答助手。\n"
        "你必须严格基于用户提供的【资料片段】回答问题。\n"
        "如果资料片段中没有足够信息，请明确说明：当前课程资料中没有找到足够依据。\n"
        "不要编造课程资料中没有出现的内容。\n"
        "回答要求：\n"
        "1. 用中文回答。\n"
        "2. 面向初学者，解释要清楚。\n"
        "3. 可以适当分点说明。\n"
        "4. 如果涉及公式或概念，请先讲直观含义，再讲专业表达。\n"
        "5. 最后可以给出一句学习建议。\n"
        "6. 不要输出 JSON，只输出自然语言答案。"
    )


def _build_rag_user_prompt(question: str, context: str) -> str:
    """
    构造用户 prompt。
    """

    return (
        f"下面是从课程知识库中检索到的资料片段：\n\n"
        f"{context}\n\n"
        f"请你基于以上资料片段回答用户问题。\n\n"
        f"用户问题：{question}"
    )


def ask_knowledge_base(
    db: Session,
    course_id: str,
    question: str,
    top_k: int = 5,
    chapter_id: str | None = None,
    knowledge_point_id: str | None = None,
) -> dict:
    """
    RAG 知识库问答：
    1. 先向量检索
    2. 再把检索结果交给 DeepSeek 生成回答
    3. 返回 answer + references
    """

    if not question.strip():
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message="问题不能为空",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # 1. 先复用已有向量检索
    search_result = search_knowledge_chunks(
        db=db,
        course_id=course_id,
        query=question,
        top_k=top_k,
        chapter_id=chapter_id,
        knowledge_point_id=knowledge_point_id,
    )

    search_items = search_result.get("items", [])

    if not search_items:
        return {
            "course_id": course_id,
            "chapter_id": chapter_id,
            "knowledge_point_id": knowledge_point_id,
            "question": question,
            "answer": "当前课程资料中没有检索到足够相关的内容，暂时无法基于知识库回答这个问题。建议教师先上传相关课程资料，或扩大检索范围后重试。",
            "references": [],
            "retrieval_accuracy": search_result["retrieval_accuracy"],
            "relevance_threshold": search_result["relevance_threshold"],
            "llm_used": False,
            "provider": "DeepSeek",
        }

    # 2. 构造 references
    references = []

    for item in search_items:
        content = item.get("content") or ""
        preview = content[:180] + "..." if len(content) > 180 else content

        references.append(
            {
                "chunk_id": item.get("chunk_id"),
                "document_id": item.get("document_id"),
                "course_id": item.get("course_id"),
                "chapter_id": item.get("chapter_id"),
                "knowledge_point_id": item.get("knowledge_point_id"),
                "section": item.get("section"),
                "score": item.get("score", 0),
                "content_preview": preview,
            }
        )

    # 3. 构造 RAG prompt
    context = _build_rag_context(search_items)
    system_prompt = _build_rag_system_prompt()
    user_prompt = _build_rag_user_prompt(
        question=question,
        context=context,
    )

    # 4. 调用 llm
    try:
        llm = DeepSeekService()

        # 这里我们需要一个普通文本生成方法
        answer = llm.rag_generate_text_sync(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=1200,
        )

        return {
            "course_id": course_id,
            "chapter_id": chapter_id,
            "knowledge_point_id": knowledge_point_id,
            "question": question,
            "answer": answer,
            "references": references,
            "retrieval_accuracy": search_result["retrieval_accuracy"],
            "relevance_threshold": search_result["relevance_threshold"],
            "llm_used": True,
            "provider": "llm",
        }

    except Exception as e:
        # LLM 失败时，不让整个接口崩，返回检索结果兜底
        fallback_answer = (
            "已检索到相关课程资料，但大模型生成回答失败。"
            "你可以先查看下方引用片段进行学习。\n\n"
            f"失败原因：{str(e)}"
        )

        return {
            "course_id": course_id,
            "chapter_id": chapter_id,
            "knowledge_point_id": knowledge_point_id,
            "question": question,
            "answer": fallback_answer,
            "references": references,
            "retrieval_accuracy": search_result["retrieval_accuracy"],
            "relevance_threshold": search_result["relevance_threshold"],
            "llm_used": False,
            "provider": "llm",
        }
