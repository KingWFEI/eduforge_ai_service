from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class LearningResource(Base):
    """学习资源表"""
    __tablename__ = "learning_resources"

    id = Column(String(64), primary_key=True, index=True)
    student_id = Column(String(64), index=True, nullable=True)
    course_id = Column(String(64), ForeignKey("courses.course_id"), index=True, nullable=False)
    knowledge_point_id = Column(String(64), ForeignKey("knowledge_points.id"), index=True, nullable=True)
    title = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False, index=True)
    difficulty = Column(String(30), nullable=True)
    description = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    content_text = Column(Text, nullable=True)
    content_json = Column(JSON, nullable=True)
    source = Column(String(255), nullable=True)
    review_status = Column(String(30), default="pending", index=True)
    safety_score = Column(Float, nullable=True)
    hallucination_risk = Column(String(30), nullable=True)
    generated_by_task_id = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ResourceReference(Base):
    """资源引用来源表"""
    __tablename__ = "resource_references"

    id = Column(String(64), primary_key=True, index=True)
    resource_id = Column(String(64), ForeignKey("learning_resources.id"), index=True, nullable=False)
    chunk_id = Column(String(64), ForeignKey("knowledge_chunks.id"), index=True, nullable=False)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ResourceFeedback(Base):
    """资源反馈表"""
    __tablename__ = "resource_feedback"

    id = Column(String(64), primary_key=True, index=True)
    resource_id = Column(String(64), ForeignKey("learning_resources.id"), index=True, nullable=False)
    student_id = Column(String(64), index=True, nullable=False)
    liked = Column(Integer, nullable=True)
    favorite = Column(Integer, default=0)
    difficulty_feedback = Column(String(30), nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ResourceFavorite(Base):
    """资源收藏表"""
    __tablename__ = "resource_favorites"

    id = Column(String(64), primary_key=True, index=True)
    resource_id = Column(String(64), ForeignKey("learning_resources.id"), index=True, nullable=False)
    student_id = Column(String(64), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ResourceReview(Base):
    """资源审核表"""
    __tablename__ = "resource_reviews"

    id = Column(String(64), primary_key=True, index=True)
    resource_id = Column(String(64), ForeignKey("learning_resources.id"), index=True, nullable=False)
    reviewer_id = Column(String(64), index=True, nullable=False)
    action = Column(String(30), nullable=False)
    comment = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), server_default=func.now())


class ResourceGenerationTask(Base):
    """资源生成任务表"""
    __tablename__ = "resource_generation_tasks"

    id = Column(String(64), primary_key=True, index=True)
    student_id = Column(String(64), index=True, nullable=False)
    course_id = Column(String(64), ForeignKey("courses.course_id"), index=True, nullable=False)
    knowledge_point = Column(String(100), nullable=True)
    goal = Column(Text, nullable=True)
    resource_types_json = Column(JSON, nullable=False)
    difficulty = Column(String(30), nullable=True)
    status = Column(String(30), nullable=False, index=True)
    progress = Column(Integer, default=0)
    current_step = Column(String(200), nullable=True)
    result_resource_ids_json = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AgentTask(Base):
    """智能体任务表"""
    __tablename__ = "agent_tasks"

    id = Column(String(64), primary_key=True, index=True)
    task_type = Column(String(50), nullable=False, index=True)
    related_task_id = Column(String(64), nullable=True, index=True)
    student_id = Column(String(64), index=True, nullable=True)
    course_id = Column(String(64), index=True, nullable=True)
    status = Column(String(30), nullable=False, index=True)
    progress = Column(Integer, default=0)
    input_json = Column(JSON, nullable=True)
    output_json = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AgentTaskStep(Base):
    """智能体任务步骤表"""
    __tablename__ = "agent_task_steps"

    id = Column(String(64), primary_key=True, index=True)
    task_id = Column(String(64), ForeignKey("agent_tasks.id"), index=True, nullable=False)
    agent_name = Column(String(100), nullable=False)
    step_order = Column(Integer, nullable=False)
    status = Column(String(30), nullable=False)
    input_summary = Column(Text, nullable=True)
    output_summary = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
