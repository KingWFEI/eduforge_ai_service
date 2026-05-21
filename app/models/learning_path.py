from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class LearningPath(Base):
    """学习路径表"""
    __tablename__ = "learning_paths"

    id = Column(String(64), primary_key=True, index=True)
    student_id = Column(String(64), index=True, nullable=False)
    course_id = Column(String(64), ForeignKey("courses.course_id"), index=True, nullable=False)
    title = Column(String(255), nullable=False)
    goal = Column(Text, nullable=True)
    duration_days = Column(Integer, nullable=True)
    daily_minutes = Column(Integer, nullable=True)
    progress = Column(Float, default=0)
    status = Column(String(30), default="active", index=True)
    plan_json = Column(JSON, nullable=True)
    created_by_task_id = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LearningPathTask(Base):
    """学习路径任务表"""
    __tablename__ = "learning_path_tasks"

    id = Column(String(64), primary_key=True, index=True)
    path_id = Column(String(64), ForeignKey("learning_paths.id"), index=True, nullable=False)
    day_no = Column(Integer, nullable=False)
    topic = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    estimated_minutes = Column(Integer, nullable=True)
    resource_ids_json = Column(JSON, nullable=True)
    status = Column(String(30), default="not_started", index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
