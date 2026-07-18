from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from pathlib import Path

from fastapi import status
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.core.config import settings
from app.models.resource_agent import LearningResource, ResourceGenerationTask
from app.models.user import User
from app.utils.response import AppException, ErrorCode


class SignedResourceAccess:
    @staticmethod
    def issue(resource_id: str, expires_in: int | None = None) -> tuple[str, int]:
        expires_at = int(time.time()) + (expires_in or settings.PPT_SIGNED_URL_EXPIRE_SECONDS)
        payload = json.dumps({"resource_id": resource_id, "exp": expires_at}, separators=(",", ":")).encode()
        encoded = base64.urlsafe_b64encode(payload).rstrip(b"=")
        signature = hmac.new(settings.SECRET_KEY.encode(), encoded, hashlib.sha256).digest()
        token = encoded + b"." + base64.urlsafe_b64encode(signature).rstrip(b"=")
        return token.decode(), expires_at

    @staticmethod
    def verify(token: str) -> str:
        try:
            encoded_text, signature_text = token.split(".", 1)
            encoded = encoded_text.encode()
            expected = hmac.new(settings.SECRET_KEY.encode(), encoded, hashlib.sha256).digest()
            signature = base64.urlsafe_b64decode(signature_text + "=" * (-len(signature_text) % 4))
            if not hmac.compare_digest(expected, signature):
                raise ValueError("signature")
            payload = json.loads(base64.urlsafe_b64decode(encoded_text + "=" * (-len(encoded_text) % 4)))
            if int(payload["exp"]) < int(time.time()):
                raise AppException(code=ErrorCode.UNAUTHORIZED, message="课件访问链接已过期", status_code=status.HTTP_401_UNAUTHORIZED)
            return str(payload["resource_id"])
        except AppException:
            raise
        except Exception as exc:
            raise AppException(code=ErrorCode.UNAUTHORIZED, message="课件访问签名无效", status_code=status.HTTP_401_UNAUTHORIZED) from exc


def authorize_resource(db: Session, current_user: User, resource_id: str) -> LearningResource:
    resource = db.get(LearningResource, resource_id)
    if resource is None:
        raise AppException(code=ErrorCode.NOT_FOUND, message="资源不存在", status_code=status.HTTP_404_NOT_FOUND)
    if current_user.role == Role.STUDENT.value and str(resource.student_id) != str(current_user.id):
        raise AppException(code=ErrorCode.FORBIDDEN, message="无权访问该资源", status_code=status.HTTP_403_FORBIDDEN)
    return resource


def resolve_artifact(db: Session, resource_id: str, asset_path: str) -> Path:
    resource = db.get(LearningResource, resource_id)
    if resource is None or resource.generation_mode != "interactive_html_slides":
        raise AppException(code=ErrorCode.NOT_FOUND, message="HTML 课件不存在", status_code=status.HTTP_404_NOT_FOUND)
    task_id = resource.generation_task_id or resource.generated_by_task_id
    task = db.get(ResourceGenerationTask, task_id) if task_id else None
    artifacts = (task.artifacts_json or {}).get(resource_id) if task and isinstance(task.artifacts_json, dict) else None
    if not artifacts:
        raise AppException(code=ErrorCode.NOT_FOUND, message="课件产物不存在", status_code=status.HTTP_404_NOT_FOUND)
    html_path = Path(artifacts["html_path"]).resolve()
    base = html_path.parent.resolve()
    requested = (base / asset_path).resolve()
    if requested != base and base not in requested.parents:
        raise AppException(code=ErrorCode.FORBIDDEN, message="非法资源路径", status_code=status.HTTP_403_FORBIDDEN)
    if not requested.is_file():
        raise AppException(code=ErrorCode.NOT_FOUND, message="课件文件不存在", status_code=status.HTTP_404_NOT_FOUND)
    return requested
