from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.constants.role import Role
from app.db.base import Base


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=True)
    nickname = Column(String(100), nullable=True)
    avatar_url = Column(String(500), default="")
    role = Column(String(30), default=Role.STUDENT.value)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
