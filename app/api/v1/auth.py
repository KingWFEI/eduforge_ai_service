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
from app.models.student_profile import StudentProfile
from app.constants.role import Role
from app.schemas.user import (
    LoginRequest,
    PhoneLoginRequest,
    RegisterRequest,
    SendCodeRequest,
    SendCodeResponse,
    TokenResponse,
    UserResponse,
)
from app.services.verification_service import create_and_send_code, verify_code
from app.utils.response import ApiResponse, AppException, ErrorCode, success
from app.utils.user_utils import user_to_response

router = APIRouter(prefix="/auth", tags=["认证"])


def _ensure_active(user: User):
    """检查用户是否被禁用"""
    if not user.is_active:
        raise AppException(
            code=ErrorCode.FORBIDDEN,
            message="账号已被禁用，请联系管理员",
            status_code=status.HTTP_403_FORBIDDEN,
        )


def _build_token_response(user: User) -> dict:
    """生成登录成功响应"""
    access_token = create_access_token(
        data={
            "sub": user.username,
            "user_id": user.id,
            "role": user.role,
        }
    )
    return {
        "access_token": access_token,
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": UserResponse(**user_to_response(user)),
    }


def ensure_username_available(username: str, db: Session):
    """检查用户名是否已被注册"""
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        raise AppException(
            code=ErrorCode.CONFLICT,
            message="用户名已存在",
            status_code=status.HTTP_409_CONFLICT,
        )


def ensure_phone_available(phone: str, db: Session):
    """检查手机号是否已被注册"""
    existing = db.query(User).filter(User.phone == phone).first()
    if existing:
        raise AppException(
            code=ErrorCode.CONFLICT,
            message="该手机号已注册",
            status_code=status.HTTP_409_CONFLICT,
        )


# ── 注册 ──────────────────────────────────────────────────


@router.post("/register-code", response_model=ApiResponse[SendCodeResponse])
def register_code(payload: SendCodeRequest, db: Session = Depends(get_db)):
    """发送注册验证码"""
    ensure_phone_available(payload.phone, db)
    result = create_and_send_code(payload.phone, db)
    return success(SendCodeResponse(**result), message="验证码已发送")


@router.post("/register", response_model=ApiResponse[UserResponse])
def register_user(payload: RegisterRequest, db: Session = Depends(get_db)):
    """学生注册（手机号/验证码方式）"""
    ensure_username_available(payload.username, db)
    ensure_phone_available(payload.phone, db)
    verify_code(payload.phone, payload.verification_code, db)

    new_user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        name=payload.name,
        phone=payload.phone,
        is_phone_verified=True,
        role=Role.STUDENT.value,
        avatar_url="",
    )
    db.add(new_user)
    db.flush()

    student_profile = StudentProfile(
        id=f"sp_{new_user.id:03d}",
        student_id=str(new_user.id),
    )
    db.add(student_profile)
    db.commit()
    db.refresh(new_user)

    return success(user_to_response(new_user), message="注册成功")


# ── 账号密码登录 ─────────────────────────────────────────


@router.post("/login", response_model=ApiResponse[TokenResponse])
def login_user(payload: LoginRequest, db: Session = Depends(get_db)):
    """账号密码登录（Flutter 学生端 / Vue 管理端共用）"""
    db_user = db.query(User).filter(User.username == payload.username).first()

    if db_user is None or not verify_password(payload.password, db_user.password_hash):
        raise AppException(
            code=ErrorCode.LOGIN_FAILED,
            message="账号或密码错误",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    _ensure_active(db_user)

    return success(
        _build_token_response(db_user),
        message="登录成功",
    )


# ── 手机号验证码登录 ──────────────────────────────────────


@router.post("/login-code", response_model=ApiResponse[SendCodeResponse])
def login_code(payload: SendCodeRequest, db: Session = Depends(get_db)):
    """发送登录验证码（手机号必须已注册）"""
    db_user = db.query(User).filter(User.phone == payload.phone).first()
    if db_user is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="该手机号未注册，请先注册账号",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    _ensure_active(db_user)

    result = create_and_send_code(payload.phone, db)
    return success(SendCodeResponse(**result), message="验证码已发送")


@router.post("/login/phone", response_model=ApiResponse[TokenResponse])
def login_by_phone(payload: PhoneLoginRequest, db: Session = Depends(get_db)):
    """手机号验证码登录"""
    db_user = db.query(User).filter(User.phone == payload.phone).first()
    if db_user is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="该手机号未注册，请先注册账号",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    _ensure_active(db_user)

    verify_code(payload.phone, payload.verification_code, db)

    return success(
        _build_token_response(db_user),
        message="登录成功",
    )


# ── 用户信息与登出 ───────────────────────────────────────


@router.get("/me", response_model=ApiResponse[UserResponse])
def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return success(user_to_response(current_user))


@router.post("/logout", response_model=ApiResponse[bool])
def logout(current_user: User = Depends(get_current_user)):
    """退出登录（客户端丢弃 Token 即可）"""
    return success(True, message="退出成功")
