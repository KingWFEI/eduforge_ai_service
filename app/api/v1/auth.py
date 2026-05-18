from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User
from app.constants.role import Role
from app.schemas.user import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.utils.response import ApiResponse, AppException, ErrorCode, success
from app.utils.user_utils import user_to_response

router = APIRouter(prefix="/auth", tags=["认证"])


def ensure_username_available(username: str, db: Session):
    """检查用户名是否已被注册"""
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        raise AppException(
            code=ErrorCode.CONFLICT,
            message="用户名已存在",
            status_code=status.HTTP_409_CONFLICT,
        )


@router.post("/register", response_model=ApiResponse[UserResponse])
def register_user(payload: RegisterRequest, db: Session = Depends(get_db)):
    """用户注册"""
    ensure_username_available(payload.username, db)

    # 注册时只能注册为学生角色
    role = payload.role
    if role != Role.STUDENT:
        role = Role.STUDENT

    new_user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        nickname=payload.nickname,
        role=role.value,
        avatar_url="",
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return success(user_to_response(new_user), message="注册成功")


@router.post("/login", response_model=ApiResponse[TokenResponse])
def login_user(payload: LoginRequest, db: Session = Depends(get_db)):
    """用户登录"""
    db_user = db.query(User).filter(User.username == payload.username).first()

    if db_user is None or not verify_password(payload.password, db_user.password_hash):
        raise AppException(
            code=ErrorCode.LOGIN_FAILED,
            message="账号或密码错误",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    access_token = create_access_token(
        data={
            "sub": db_user.username,
            "user_id": db_user.id,
            "role": db_user.role,
        }
    )

    return success(
        TokenResponse(
            access_token=access_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse(**user_to_response(db_user)),
        ),
        message="登录成功",
    )


@router.get("/me", response_model=ApiResponse[UserResponse])
def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return success(user_to_response(current_user))


@router.post("/logout", response_model=ApiResponse[bool])
def logout(current_user: User = Depends(get_current_user)):
    """退出登录（客户端丢弃 Token 即可）"""
    return success(True, message="退出成功")
