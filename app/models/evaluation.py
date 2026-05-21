from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class EvaluationReport(Base):
    """学习报告表"""
    __tablename__ = "evaluation_reports"

    id = Column(String(64), primary_key=True, index=True)
    student_id = Column(String(64), index=True, nullable=False)
    course_id = Column(String(64), nullable=True)
    report_range = Column(String(30), nullable=False)
    completion_rate = Column(Float, nullable=True)
    accuracy_rate = Column(Float, nullable=True)
    study_hours = Column(Float, nullable=True)
    mastery_json = Column(JSON, nullable=True)
    good_points_json = Column(JSON, nullable=True)
    weak_points_json = Column(JSON, nullable=True)
    recommendations_json = Column(JSON, nullable=True)
    next_suggestion = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MasteryRecord(Base):
    """知识点掌握度表"""
    __tablename__ = "mastery_records"

    id = Column(String(64), primary_key=True, index=True)
    student_id = Column(String(64), index=True, nullable=False)
    course_id = Column(String(64), ForeignKey("courses.course_id"), index=True, nullable=False)
    knowledge_point_id = Column(String(64), nullable=True)
    knowledge_point = Column(String(100), nullable=False)
    score = Column(Float, nullable=False)
    source = Column(String(50), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class WeakPointRecord(Base):
    """薄弱点记录表"""
    __tablename__ = "weak_point_records"

    id = Column(String(64), primary_key=True, index=True)
    student_id = Column(String(64), index=True, nullable=False)
    course_id = Column(String(64), nullable=True)
    knowledge_point = Column(String(100), nullable=False)
    mastery_score = Column(Float, nullable=True)
    wrong_count = Column(Integer, default=0)
    reason = Column(Text, nullable=True)
    suggested_action = Column(Text, nullable=True)
    source = Column(String(50), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
