from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.sql import func

from app.db.base import Base


class CourseChapter(Base):
    """课程章节表"""
    __tablename__ = "course_chapters"

    id = Column(String(64), primary_key=True, index=True)
    course_id = Column(String(64), ForeignKey("courses.course_id"), index=True, nullable=False)
    parent_id = Column(
        String(64),
        ForeignKey(
            "course_chapters.id",
            name="fk_course_chapters_parent_id",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=True,
    )
    level = Column(Integer, default=1, nullable=False)
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


class StudentSectionProgress(Base):
    """学生课程小节学习进度。"""

    __tablename__ = "student_section_progress"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "section_id",
            name="uq_student_section_progress_student_section",
        ),
        Index(
            "idx_student_section_progress_student_course",
            "student_id",
            "course_id",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    student_id = Column(String(64), nullable=False, index=True, comment="学生ID，对应用户主键的字符串形式")
    course_id = Column(
        String(64),
        ForeignKey("courses.course_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="课程业务ID",
    )
    section_id = Column(
        String(64),
        ForeignKey("course_chapters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="课程小节ID，对应二级课程章节",
    )
    progress = Column(Float, nullable=False, default=0.0, server_default=text("0"), comment="学习进度，范围0.0到1.0")
    status = Column(
        String(30),
        nullable=False,
        default="unlearned",
        server_default=text("'unlearned'"),
        index=True,
        comment="学习状态：completed、learning、unlearned、locked",
    )
    last_study_at = Column(DateTime(timezone=True), nullable=True, index=True, comment="最后学习时间")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )


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


class CourseStructureDraft(Base):
    """AI 识别出的课程结构草稿"""
    __tablename__ = "course_structure_drafts"
    __table_args__ = (
        Index("idx_course_structure_drafts_course_id", "course_id"),
        Index("idx_course_structure_drafts_status", "status"),
    )

    id = Column(String(64), primary_key=True)
    course_id = Column(String(64), ForeignKey("courses.course_id"), nullable=False)
    source_document_ids_json = Column(JSON, nullable=True)
    draft_json = Column(JSON, nullable=False)
    status = Column(String(30), server_default=text("'draft'"), nullable=False)
    created_by = Column(String(64), nullable=True)
    confirmed_by = Column(String(64), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
