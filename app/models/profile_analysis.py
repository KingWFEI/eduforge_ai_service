from sqlalchemy import Column, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class ProfileVersion(Base):
    """画像历史版本表"""
    __tablename__ = "profile_versions"

    id = Column(String(64), primary_key=True, index=True)
    profile_id = Column(String(64), index=True, nullable=False)
    student_id = Column(String(64), index=True, nullable=False)
    version = Column(Integer, nullable=False)
    source = Column(String(50), nullable=False)
    profile_snapshot_json = Column(JSON, nullable=False)
    changed_fields_json = Column(JSON, nullable=True)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ProfileAnalysis(Base):
    """画像分析任务表"""
    __tablename__ = "profile_analyses"

    id = Column(String(64), primary_key=True, index=True)
    student_id = Column(String(64), index=True, nullable=False)
    submission_id = Column(String(64), index=True, nullable=False)
    profile_id = Column(String(64), nullable=True, index=True)
    source = Column(String(50), nullable=False)
    analysis_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, index=True)
    progress = Column(Integer, default=0)
    current_step = Column(String(200), nullable=True)
    analysis_text = Column(Text, nullable=True)
    learning_suggestion = Column(Text, nullable=True)
    resource_strategy_json = Column(JSON, nullable=True)
    weakness_analysis_json = Column(JSON, nullable=True)
    agent_trace_json = Column(JSON, nullable=True)
    error_json = Column(JSON, nullable=True)
    confidence = Column(Float, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
