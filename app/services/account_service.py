from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserProfileUpdate
from app.utils.response import AppException, ErrorCode
from app.utils.user_utils import user_to_response


AVATAR_UPLOAD_DIR = Path("uploads") / "avatars"
AVATAR_URL_PREFIX = "/uploads/avatars"
AVATAR_MAX_BYTES = 5 * 1024 * 1024
AVATAR_CHUNK_BYTES = 1024 * 1024
ALLOWED_AVATAR_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _conflict(message: str) -> AppException:
    return AppException(
        code=ErrorCode.CONFLICT,
        message=message,
        status_code=status.HTTP_409_CONFLICT,
    )


def update_current_user_profile(
    db: Session,
    current_user: User,
    payload: UserProfileUpdate,
) -> dict:
    phone_owner = (
        db.query(User)
        .filter(User.phone == payload.phone, User.id != current_user.id)
        .first()
    )
    if phone_owner is not None:
        raise _conflict("该手机号已被其他账号使用")

    normalized_email = payload.email or None
    if normalized_email:
        email_owner = (
            db.query(User)
            .filter(User.email == normalized_email, User.id != current_user.id)
            .first()
        )
        if email_owner is not None:
            raise _conflict("该邮箱已被其他账号使用")

    phone_changed = current_user.phone != payload.phone
    current_user.name = payload.name
    current_user.phone = payload.phone
    current_user.email = normalized_email
    if phone_changed:
        current_user.is_phone_verified = False

    try:
        db.commit()
        db.refresh(current_user)
    except IntegrityError as exc:
        db.rollback()
        raise _conflict("手机号或邮箱已被其他账号使用") from exc

    return user_to_response(current_user)


def _is_valid_image(data: bytes, content_type: str) -> bool:
    if content_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


async def _read_avatar(file: UploadFile, max_bytes: int) -> bytes:
    content = bytearray()
    while True:
        chunk = await file.read(AVATAR_CHUNK_BYTES)
        if not chunk:
            break
        content.extend(chunk)
        if len(content) > max_bytes:
            raise AppException(
                code=ErrorCode.PAYLOAD_TOO_LARGE,
                message="头像文件不能超过 5MB",
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            )
    if not content:
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message="头像文件不能为空",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return bytes(content)


def _remove_local_avatar(avatar_url: str | None, upload_dir: Path) -> None:
    if not avatar_url or not avatar_url.startswith(f"{AVATAR_URL_PREFIX}/"):
        return
    filename = Path(avatar_url).name
    candidate = (upload_dir / filename).resolve()
    root = upload_dir.resolve()
    if candidate.parent == root and candidate.is_file():
        candidate.unlink()


async def update_current_user_avatar(
    db: Session,
    current_user: User,
    file: UploadFile,
    *,
    upload_dir: Path = AVATAR_UPLOAD_DIR,
    max_bytes: int = AVATAR_MAX_BYTES,
) -> dict:
    content_type = (file.content_type or "").lower().split(";", 1)[0].strip()
    extension = ALLOWED_AVATAR_TYPES.get(content_type)
    if extension is None:
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message="头像仅支持 JPEG、PNG、WebP 格式",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    content = await _read_avatar(file, max_bytes)
    if not _is_valid_image(content, content_type):
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message="文件内容与图片格式不匹配",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"avatar_{current_user.id}_{uuid4().hex}{extension}"
    target = upload_dir / stored_name
    temporary = upload_dir / f".{stored_name}.tmp"
    old_avatar_url = current_user.avatar_url

    try:
        temporary.write_bytes(content)
        temporary.replace(target)
        current_user.avatar_url = f"{AVATAR_URL_PREFIX}/{stored_name}"
        db.commit()
        db.refresh(current_user)
    except Exception:
        db.rollback()
        temporary.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        raise

    try:
        _remove_local_avatar(old_avatar_url, upload_dir)
    except OSError:
        # 数据库和新头像已经更新成功，旧文件清理失败不应让接口返回失败。
        pass
    return user_to_response(current_user)
