from sqlalchemy import Column, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class StudentProfile(Base):
    """学生学习画像表"""
    __tablename__ = "student_profiles"

    id = Column(String(64), primary_key=True, index=True)
    student_id = Column(String(64), unique=True, index=True, nullable=False)
    major = Column(String(100), nullable=True)
    grade = Column(String(50), nullable=True)
    target_course_id = Column(String(64), nullable=True)
    target_course = Column(String(100), nullable=True)
    learning_goals_json = Column(JSON, nullable=True)
    coding_level = Column(String(50), nullable=True)
    math_level = Column(String(50), nullable=True)
    course_level = Column(String(50), nullable=True)
    learning_preferences_json = Column(JSON, nullable=True)
    weaknesses_json = Column(JSON, nullable=True)
    cognitive_style_json = Column(JSON, nullable=True)
    time_budget = Column(String(100), nullable=True)
    summary = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    source = Column(String(50), nullable=True)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
