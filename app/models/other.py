from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class StudyRecord(Base):
    """学习记录表"""
    __tablename__ = "study_records"

    id = Column(String(64), primary_key=True, index=True)
    student_id = Column(String(64), index=True, nullable=False)
    course_id = Column(String(64), nullable=True)
    resource_id = Column(String(64), nullable=True)
    path_task_id = Column(String(64), nullable=True)
    action_type = Column(String(50), nullable=False)
    study_minutes = Column(Integer, default=0)
    progress_delta = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserNotification(Base):
    """消息通知表"""
    __tablename__ = "user_notifications"

    id = Column(String(64), primary_key=True, index=True)
    user_id = Column(String(64), index=True, nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    type = Column(String(50), nullable=False, index=True)
    related_id = Column(String(64), nullable=True)
    is_read = Column(Integer, default=0, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    read_at = Column(DateTime(timezone=True), nullable=True)


class DashboardDailyStat(Base):
    """每日统计表"""
    __tablename__ = "dashboard_daily_stats"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    stat_date = Column(Date, nullable=False, index=True)
    student_count = Column(Integer, default=0)
    course_count = Column(Integer, default=0)
    generated_resource_count = Column(Integer, default=0)
    agent_task_count = Column(Integer, default=0)
    average_accuracy = Column(Float, nullable=True)
    learning_path_completion_rate = Column(Float, nullable=True)
    agent_task_success_rate = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SystemSetting(Base):
    """系统配置表"""
    __tablename__ = "system_settings"

    id = Column(String(64), primary_key=True, index=True)
    setting_key = Column(String(100), unique=True, index=True, nullable=False)
    setting_value_json = Column(JSON, nullable=True)
    description = Column(String(255), nullable=True)
    updated_by = Column(String(64), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PromptTemplate(Base):
    """Prompt 模板表"""
    __tablename__ = "prompt_templates"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    scene = Column(String(50), nullable=False, index=True)
    content = Column(Text, nullable=False)
    version = Column(Integer, default=1)
    enabled = Column(Integer, default=1, index=True)
    created_by = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
