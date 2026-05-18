from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.core.dependencies import get_current_user, require_role
from app.core.security import decode_access_token, hash_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import PageResponse
from app.schemas.user import AdminUserCreate, UserResponse, UserRoleUpdate
from app.utils.response import ApiResponse, AppException, ErrorCode, success
from app.utils.user_utils import user_to_response

router = APIRouter(prefix="/users", tags=["用户"])


@router.post("/", response_model=ApiResponse[UserResponse])
def create_user(
    user: AdminUserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    """管理员创建新用户"""
    existing_user = db.query(User).filter(User.username == user.username).first()
    if existing_user:
        raise AppException(
            code=ErrorCode.CONFLICT,
            message="用户名已存在",
            status_code=status.HTTP_409_CONFLICT,
        )

    if user.email:
        existing_email = db.query(User).filter(User.email == user.email).first()
        if existing_email:
            raise AppException(
                code=ErrorCode.CONFLICT,
                message="邮箱已存在",
                status_code=status.HTTP_409_CONFLICT,
            )

    new_user = User(
        username=user.username,
        password_hash=hash_password(user.password),
        email=user.email,
        nickname=user.nickname,
        role=user.role.value,
        avatar_url="",
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return success(user_to_response(new_user))


@router.get("/me", response_model=ApiResponse[UserResponse])
def get_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return success(user_to_response(current_user))


@router.get("/", response_model=ApiResponse[PageResponse[UserResponse]])
def get_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """分页查询用户列表（教师/管理员权限）"""
    query = db.query(User)
    total = query.count()
    users = query.offset((page - 1) * page_size).limit(page_size).all()

    return success(
        PageResponse[UserResponse](
            items=[UserResponse(**user_to_response(user)) for user in users],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.patch("/{user_id}/role", response_model=ApiResponse[UserResponse])
def update_user_role(
    user_id: int,
    payload: UserRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    """管理员修改用户角色"""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="用户不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    user.role = payload.role.value
    db.commit()
    db.refresh(user)

    return success(user_to_response(user))
