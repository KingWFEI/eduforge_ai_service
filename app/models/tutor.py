from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects import mysql
from sqlalchemy.sql import func

from app.db.base import Base


PRECISE_DATETIME = DateTime(timezone=True).with_variant(mysql.DATETIME(fsp=6), "mysql")


class TutorSession(Base):
    """Persistent AI tutor conversation owned by one student."""

    __tablename__ = "tutor_sessions"
    __table_args__ = (
        Index("idx_tutor_sessions_student_status", "student_id", "status"),
    )

    id = Column(String(64), primary_key=True)
    student_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title = Column(String(200), nullable=False, default="", server_default="")
    session_type = Column(
        String(20),
        nullable=False,
        default="general",
        server_default="general",
    )
    course_id = Column(
        String(64),
        ForeignKey("courses.course_id", ondelete="SET NULL"),
        nullable=True,
    )
    section_id = Column(
        String(64),
        ForeignKey("course_chapters.id", ondelete="SET NULL"),
        nullable=True,
    )
    status = Column(
        String(20),
        nullable=False,
        default="active",
        server_default="active",
    )
    last_message = Column(String(500), nullable=True)
    created_at = Column(PRECISE_DATETIME, nullable=False, server_default=func.now())
    updated_at = Column(
        PRECISE_DATETIME,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class TutorMessage(Base):
    """One user or assistant message in a tutor conversation."""

    __tablename__ = "tutor_messages"
    __table_args__ = (
        Index("idx_tutor_messages_session_created", "session_id", "created_at"),
    )

    id = Column(String(64), primary_key=True)
    session_id = Column(
        String(64),
        ForeignKey("tutor_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role = Column(String(10), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(
        PRECISE_DATETIME,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
