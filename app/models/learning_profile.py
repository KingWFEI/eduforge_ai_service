from sqlalchemy import Column, DateTime, Float, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.db.base import Base


class StudentLearningProfile(Base):
    """跨课程、相对稳定的学生综合学习画像。"""

    __tablename__ = "student_learning_profiles"

    id = Column(String(64), primary_key=True, index=True)
    student_id = Column(String(64), unique=True, index=True, nullable=False)
    learning_preferences_json = Column(JSON, nullable=True)
    cognitive_traits_json = Column(JSON, nullable=True)
    learning_habits_json = Column(JSON, nullable=True)
    motivation_factors_json = Column(JSON, nullable=True)
    general_strengths_json = Column(JSON, nullable=True)
    general_challenges_json = Column(JSON, nullable=True)
    preferred_pace = Column(String(100), nullable=True)
    available_time_json = Column(JSON, nullable=True)
    summary = Column(Text, nullable=True)
    profile_dimensions_json = Column(JSON, nullable=True)
    evidence_json = Column(JSON, nullable=True)
    confidence_json = Column(JSON, nullable=True)
    version = Column(Integer, default=1, nullable=False)
    source = Column(String(50), nullable=True)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class StudentDomainCompetency(Base):
    """学生在某个课程、学科或技能领域中的能力画像。"""

    __tablename__ = "student_domain_competencies"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "domain_type",
            "domain_id",
            name="uq_student_domain_competency",
        ),
    )

    id = Column(String(64), primary_key=True, index=True)
    student_id = Column(String(64), index=True, nullable=False)
    domain_type = Column(String(50), nullable=False)
    domain_id = Column(String(64), nullable=True)
    domain_name = Column(String(200), nullable=False)
    competency_level = Column(String(50), nullable=True)
    strengths_json = Column(JSON, nullable=True)
    weaknesses_json = Column(JSON, nullable=True)
    knowledge_state_json = Column(JSON, nullable=True)
    evidence_json = Column(JSON, nullable=True)
    confidence = Column(Float, nullable=True)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class StudentLearningContext(Base):
    """学生当前或历史课程学习目标与上下文。"""

    __tablename__ = "student_learning_contexts"

    id = Column(String(64), primary_key=True, index=True)
    student_id = Column(String(64), index=True, nullable=False)
    course_id = Column(String(64), nullable=True, index=True)
    course_name = Column(String(200), nullable=True)
    learning_goals_json = Column(JSON, nullable=True)
    time_budget_json = Column(JSON, nullable=True)
    status = Column(String(30), default="active", index=True, nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
