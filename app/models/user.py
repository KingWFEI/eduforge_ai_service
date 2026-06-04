from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
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
    name = Column(String(100), nullable=True)
    phone = Column(String(20), unique=True, index=True, nullable=True)
    is_phone_verified = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    avatar_url = Column(String(500), default="")
    role = Column(String(30), default=Role.STUDENT.value, index=True)
    status = Column(String(30), default="normal", index=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    onboarding_status = relationship(
        "UserOnboardingStatus",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )

class UserOnboardingStatus(Base):
    """用户引导问卷状态表"""

    __tablename__ = "user_onboarding_status"

    id = Column(Integer, primary_key=True, index=True)

    # 关联 users.id
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
        comment="用户ID",
    )

    # 引导状态：
    # not_started：未开始
    # processing：问卷已提交，正在生成画像
    # completed：已完成
    # failed：画像生成失败，可重新提交
    # skipped：已跳过
    # reset_required：需要重新填写
    status = Column(
        String(30),
        default="not_started",
        index=True,
        nullable=False,
        comment="引导问卷状态",
    )

    # 当前使用的问卷 ID
    survey_id = Column(
        String(64),
        nullable=True,
        index=True,
        comment="问卷ID",
    )

    # 最近一次问卷提交 ID
    submission_id = Column(
        String(64),
        nullable=True,
        index=True,
        comment="问卷提交ID",
    )

    # 生成的学习画像 ID
    profile_id = Column(
        String(64),
        nullable=True,
        index=True,
        comment="学习画像ID",
    )

    # 是否需要强制填写
    # 一般情况下：
    # not_started / failed / reset_required => true
    # processing / completed / skipped => false
    need_onboarding = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="是否需要进入引导问卷",
    )

    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="完成问卷时间",
    )

    skipped_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="跳过问卷时间",
    )

    reset_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="重置问卷时间",
    )

    reset_reason = Column(
        Text,
        nullable=True,
        comment="重置原因",
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间",
    )
    # 关系映射
    user = relationship("User", back_populates="onboarding_status")
