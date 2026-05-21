import string
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.db.base import Base


class VerificationCode(Base):
    """短信验证码表"""
    __tablename__ = "verification_codes"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), index=True, nullable=False)
    code = Column(String(10), nullable=False)
    scene = Column(String(30), default="register")
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    @staticmethod
    def generate_code(length: int = 6) -> str:
        """生成随机数字验证码"""
        import random
        return ''.join(random.choices(string.digits, k=length))

    def is_expired(self) -> bool:
        return datetime.utcnow() >= self.expires_at
