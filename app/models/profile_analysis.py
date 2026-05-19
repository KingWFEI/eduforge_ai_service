from sqlalchemy import Column, DateTime, Integer, JSON, String, Text, Float
from sqlalchemy.sql import func

from app.db.base import Base


class ProfileAnalysis(Base):
    """画像分析记录（同时也是异步任务记录）"""
    __tablename__ = "profile_analyses"

    id = Column(String(64), primary_key=True, index=True)
    submission_id = Column(String(64), nullable=False, index=True)
    student_id = Column(String(64), nullable=False, index=True)
    profile_id = Column(String(64), nullable=True, index=True)

    source = Column(String(50), nullable=False, default="onboarding")
    analysis_type = Column(String(50), nullable=False, default="initial")

    # ── 异步任务状态 ──
    status = Column(String(20), nullable=False, default="pending")  # pending / processing / completed / failed
    progress = Column(Integer, default=0)
    current_step = Column(String(200), nullable=True)

    # ── 分析结果 ──
    analysis_text = Column(Text, nullable=True)
    learning_suggestion = Column(Text, nullable=True)
    resource_strategy_json = Column(JSON, nullable=True)
    weakness_analysis_json = Column(JSON, nullable=True)
    confidence = Column(Float, nullable=True)

    # ── 调用跟踪 ──
    agent_trace_json = Column(JSON, nullable=True)
    error_json = Column(JSON, nullable=True)

    # ── 时间戳 ──
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
