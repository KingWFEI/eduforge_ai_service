from sqlalchemy import Column, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class OnboardingSubmission(Base):
    """问卷提交记录"""
    __tablename__ = "onboarding_submissions"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(String(50), unique=True, index=True, nullable=False)
    survey_id = Column(String(50), index=True, nullable=False)
    student_id = Column(String(100), nullable=False)
    answers = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class StudentProfile(Base):
    """学生学习画像"""
    __tablename__ = "student_profiles"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(String(50), unique=True, index=True, nullable=False)
    student_id = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(100), default="")
    major = Column(String(100), default="")
    grade = Column(String(50), default="")
    target_course = Column(String(200), default="")
    learning_goals = Column(JSON, default=list)
    coding_level = Column(String(50), default="")
    math_level = Column(String(50), default="")
    course_level = Column(String(50), default="")
    learning_preferences = Column(JSON, default=list)
    weaknesses = Column(JSON, default=list)
    cognitive_style = Column(JSON, default=list)
    time_budget = Column(String(100), default="")
    summary = Column(Text, default="")
    confidence = Column(Float, default=0.0)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
