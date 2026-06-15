from sqlalchemy import Column, DateTime, Float, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.db.base import Base


class LearningStyleCharacter(Base):
    """Learning style character configured by teachers or admins."""

    __tablename__ = "learning_style_characters"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(50), unique=True, index=True, nullable=False)
    image_url = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    style_prompt = Column(Text, nullable=True)
    feature_tags = Column(JSON, nullable=True)
    suitable_methods = Column(JSON, nullable=True)
    status = Column(String(30), nullable=False, default="DRAFT", index=True)
    priority = Column(Integer, nullable=False, default=0)
    version = Column(Integer, nullable=False, default=1)
    created_by = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class StudentStyleMatch(Base):
    """Cached character match result for a student profile version."""

    __tablename__ = "student_style_matches"
    __table_args__ = (
        UniqueConstraint("student_id", "profile_id", name="uq_student_style_match_profile"),
    )

    id = Column(String(64), primary_key=True, index=True)
    student_id = Column(String(64), index=True, nullable=False)
    profile_id = Column(String(64), index=True, nullable=False)
    profile_version = Column(Integer, nullable=False, default=1)
    character_id = Column(String(64), index=True, nullable=False)
    character_version = Column(Integer, nullable=False)
    match_score = Column(Float, nullable=False, default=0)
    match_reason = Column(Text, nullable=True)
    matched_features = Column(JSON, nullable=True)
    matching_source = Column(String(50), nullable=False, default="rule")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
