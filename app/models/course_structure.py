from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, text
from sqlalchemy.sql import func

from app.db.base import Base


class CourseChapter(Base):
    """课程章节表"""
    __tablename__ = "course_chapters"

    id = Column(String(64), primary_key=True, index=True)
    course_id = Column(String(64), ForeignKey("courses.course_id"), index=True, nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class KnowledgePoint(Base):
    """知识点表"""
    __tablename__ = "knowledge_points"

    id = Column(String(64), primary_key=True, index=True)
    course_id = Column(String(64), ForeignKey("courses.course_id"), index=True, nullable=False)
    chapter_id = Column(String(64), ForeignKey("course_chapters.id"), index=True, nullable=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    difficulty = Column(String(30), nullable=True)
    prerequisites_json = Column(JSON, nullable=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CourseDocument(Base):
    """课程资料表"""
    __tablename__ = "course_documents"

    id = Column(String(64), primary_key=True, index=True)
    course_id = Column(String(64), ForeignKey("courses.course_id"), index=True, nullable=False)
    chapter_id = Column(String(64), ForeignKey("course_chapters.id"), index=True, nullable=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=True)
    file_size = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(30), default="active", index=True)
    parse_status = Column(String(30), default="pending", index=True)
    index_status = Column(String(30), default="pending", index=True)
    chunk_count = Column(Integer, default=0)
    uploaded_by = Column(String(64), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class KnowledgeChunk(Base):
    """知识块表（用于 RAG 检索）"""
    __tablename__ = "knowledge_chunks"

    id = Column(String(64), primary_key=True, index=True)
    course_id = Column(String(64), ForeignKey("courses.course_id"), index=True, nullable=False)
    document_id = Column(String(64), ForeignKey("course_documents.id"), index=True, nullable=False)
    chapter_id = Column(String(64), ForeignKey("course_chapters.id"), index=True, nullable=True)
    knowledge_point_id = Column(String(64), ForeignKey("knowledge_points.id"), index=True, nullable=True)
    section = Column(String(200), nullable=True)
    content = Column(Text, nullable=False)
    keywords_json = Column(JSON, nullable=True)
    page_no = Column(Integer, nullable=True)
    chunk_index = Column(Integer, nullable=False)
    vector_id = Column(String(100), nullable=True)
    indexed = Column(Integer, default=0)
    deleted = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class VectorIndexRecord(Base):
    """向量索引记录表"""
    __tablename__ = "vector_index_records"
    __table_args__ = (
        Index("idx_vector_index_course_id", "course_id"),
        Index("idx_vector_index_document_id", "document_id"),
        Index("idx_vector_index_status", "status"),
    )

    id = Column(String(64), primary_key=True)
    course_id = Column(String(64), nullable=False)
    document_id = Column(String(64), nullable=False)
    index_type = Column(String(50), server_default=text("'chroma'"))
    collection_name = Column(String(100), nullable=True)
    status = Column(String(30), server_default=text("'processing'"))
    chunk_count = Column(Integer, server_default=text("0"))
    success_count = Column(Integer, server_default=text("0"))
    failed_count = Column(Integer, server_default=text("0"))
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
