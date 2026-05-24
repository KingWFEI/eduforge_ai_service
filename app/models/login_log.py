from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.db.base import Base


class LoginLog(Base):
    """登录日志表"""
    __tablename__ = "login_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String(64), nullable=True, index=True)
    username = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    login_type = Column(String(30), nullable=False)
    success = Column(Integer, nullable=False)
    fail_reason = Column(String(255), nullable=True)
    client_type = Column(String(30), nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
