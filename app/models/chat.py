from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class ChatSession(Base):
    """AI 对话会话表"""
    __tablename__ = "chat_sessions"

    id = Column(String(64), primary_key=True, index=True)
    student_id = Column(String(64), index=True, nullable=False)
    title = Column(String(200), nullable=False)
    course_id = Column(String(64), index=True, nullable=True)
    resource_id = Column(String(64), nullable=True)
    mode = Column(String(30), default="tutor")
    last_message = Column(String(500), nullable=True)
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    message_count = Column(Integer, default=0)
    status = Column(String(30), default="active", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ChatMessage(Base):
    """AI 对话消息表"""
    __tablename__ = "chat_messages"

    id = Column(String(64), primary_key=True, index=True)
    session_id = Column(String(64), ForeignKey("chat_sessions.id"), index=True, nullable=False)
    student_id = Column(String(64), index=True, nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    content_type = Column(String(30), default="text")
    status = Column(String(30), default="completed", index=True)
    agent_task_id = Column(String(64), nullable=True)
    token_count = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ChatMessageSource(Base):
    """消息知识来源表（RAG 引用记录）"""
    __tablename__ = "chat_message_sources"

    id = Column(String(64), primary_key=True, index=True)
    message_id = Column(String(64), ForeignKey("chat_messages.id"), index=True, nullable=False)
    chunk_id = Column(String(64), ForeignKey("knowledge_chunks.id"), index=True, nullable=False)
    source_title = Column(String(255), nullable=True)
    source_page = Column(Integer, nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ChatFeedback(Base):
    """对话反馈表"""
    __tablename__ = "chat_feedback"

    id = Column(String(64), primary_key=True, index=True)
    message_id = Column(String(64), ForeignKey("chat_messages.id"), index=True, nullable=False)
    student_id = Column(String(64), index=True, nullable=False)
    rating = Column(Integer, nullable=True)
    liked = Column(Integer, nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
