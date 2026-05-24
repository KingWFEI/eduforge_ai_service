import logging
from datetime import datetime, timedelta

from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.verification_code import VerificationCode
from app.services.sms_service import send_sms_code
from app.utils.response import AppException, ErrorCode

logger = logging.getLogger(__name__)

# 同一手机号发送冷却时间（秒）
COOLDOWN_SECONDS = 60
# 每日发送上限
DAILY_LIMIT = 10


def create_and_send_code(phone: str, db: Session) -> dict:
    """生成验证码、存入数据库、发送短信"""

    # 检查冷却时间
    _check_cooldown(phone, db)

    # 检查每日上限（以防刷接口）
    _check_daily_limit(phone, db)

    # 生成验证码
    code = VerificationCode.generate_code()
    now = datetime.utcnow()
    expires_at = now + timedelta(minutes=settings.SMS_CODE_EXPIRE_MINUTES)

    # 将旧验证码标记为已使用（防止堆积）
    db.query(VerificationCode).filter(
        VerificationCode.phone == phone,
        VerificationCode.is_used == False,
    ).update({"is_used": True})

    # 存入新验证码
    vc = VerificationCode(
        phone=phone,
        code=code,
        expires_at=expires_at,
        is_used=False,
        created_at=now,
    )
    db.add(vc)
    db.commit()

    # 发送短信（控制台打印）
    send_sms_code(phone, code)

    return {
        "expire_seconds": settings.SMS_CODE_EXPIRE_MINUTES * 60,
        "resend_after_seconds": COOLDOWN_SECONDS,
    }


def verify_code(phone: str, code: str, db: Session, mark_used: bool = True) -> bool:
    """
    校验验证码。
    mark_used=True 时校验通过后立即标记为已使用（防止重复使用）。
    """
    record = (
        db.query(VerificationCode)
        .filter(
            VerificationCode.phone == phone,
            VerificationCode.code == code,
            VerificationCode.is_used == False,
        )
        .order_by(VerificationCode.created_at.desc())
        .first()
    )

    if record is None:
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message="验证码错误",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if record.is_expired():
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message="验证码已过期，请重新获取",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if mark_used:
        record.is_used = True
        db.commit()

    return True


def _check_cooldown(phone: str, db: Session) -> int:
    """检查发送冷却，返回剩余冷却秒数"""
    recent = (
        db.query(VerificationCode)
        .filter(
            VerificationCode.phone == phone,
        )
        .order_by(VerificationCode.created_at.desc())
        .first()
    )

    if recent:
        elapsed = (datetime.utcnow() - recent.created_at).total_seconds()
        if elapsed < COOLDOWN_SECONDS:
            remaining = int(COOLDOWN_SECONDS - elapsed)
            raise AppException(
                code=ErrorCode.PARAM_ERROR,
                message="验证码发送过于频繁，请稍后再试",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                data={"resend_after_seconds": remaining},
            )
    return COOLDOWN_SECONDS


def _check_daily_limit(phone: str, db: Session):
    """检查每日发送上限"""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    count = (
        db.query(VerificationCode)
        .filter(
            VerificationCode.phone == phone,
            VerificationCode.created_at >= today_start,
        )
        .count()
    )

    if count >= DAILY_LIMIT:
        raise AppException(
            code=ErrorCode.RATE_LIMITED,
            message="今日验证码发送次数已达上限",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )
