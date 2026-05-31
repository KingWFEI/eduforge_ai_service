from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.utils.response import AppException, ErrorCode

# Bearer Token 认证方案（不自动报错，允许手动处理）
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    从请求头中提取并验证 JWT Token，返回当前用户。

    验证流程：提取 Token → 解码 → 提取用户名 → 数据库查询
    """
    if credentials is None:
        raise AppException(
            code=ErrorCode.UNAUTHORIZED,
            message="未提供认证令牌",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise AppException(
            code=ErrorCode.UNAUTHORIZED,
            message="令牌无效或已过期",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    username = payload.get("sub")
    if username is None:
        raise AppException(
            code=ErrorCode.UNAUTHORIZED,
            message="令牌中缺少用户标识",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise AppException(
            code=ErrorCode.UNAUTHORIZED,
            message="用户不存在或已注销",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    return user


def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """仅允许管理员访问：校验 is_active、status、role"""
    if not current_user.is_active:
        raise AppException(
            code=ErrorCode.FORBIDDEN,
            message="当前账号已被禁用",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    if current_user.status != "normal":
        raise AppException(
            code=ErrorCode.FORBIDDEN,
            message="当前账号状态异常",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    if current_user.role != Role.ADMIN.value:
        raise AppException(
            code=ErrorCode.FORBIDDEN,
            message="无权限操作，仅管理员可以访问",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return current_user


def require_role(*roles: Role):
    """
    角色权限验证依赖：要求当前用户拥有指定角色之一。

    用法：Depends(require_role(Role.ADMIN)) 或 Depends(require_role(Role.TEACHER, Role.ADMIN))
    """
    allowed_roles = {role.value for role in roles}

    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise AppException(
                code=ErrorCode.FORBIDDEN,
                message="当前角色没有权限",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return current_user

    return checker
