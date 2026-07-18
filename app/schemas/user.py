from datetime import datetime
from typing import Optional

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.constants.role import Role


class RegisterRequest(BaseModel):
    """用户注册请求（手机号/验证码方式）"""
    name: str = Field(..., min_length=1, description="用户姓名")
    username: str = Field(..., min_length=1, description="登录用户名")
    phone: str = Field(..., pattern=r"^1\d{10}$", description="手机号")
    verification_code: str = Field(..., min_length=6, max_length=6, description="手机验证码")
    password: str = Field(..., min_length=6, description="登录密码")


class SendCodeRequest(BaseModel):
    """发送验证码请求"""
    phone: str = Field(..., pattern=r"^1\d{10}$")


class SendCodeResponse(BaseModel):
    """发送验证码响应"""
    expire_seconds: int
    resend_after_seconds: int


class UserCreate(BaseModel):
    """创建用户（管理员用）"""
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=6)
    name: str = Field(..., min_length=1)
    email: Optional[str] = None
    role: Role = Role.STUDENT


class AdminUserCreate(UserCreate):
    """管理员创建用户（显式声明 role，可选 phone）"""
    phone: Optional[str] = Field(default=None, pattern=r"^1\d{10}$", description="手机号")


class UserRoleUpdate(BaseModel):
    """用户角色更新请求"""
    role: Role


class UserProfileUpdate(BaseModel):
    """当前用户可修改的基本信息。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=2, max_length=30, description="姓名")
    phone: str = Field(..., pattern=r"^1[3-9]\d{9}$", description="中国大陆手机号")
    email: str = Field(default="", max_length=100, description="邮箱，允许为空字符串")

    @field_validator("name", "phone", mode="before")
    @classmethod
    def strip_required_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        if value is None:
            return ""
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("邮箱格式不正确")
        return value


class UserResponse(BaseModel):
    """用户信息响应"""
    user_id: str
    username: str
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    role: Role
    status: str = "normal"
    is_active: bool = True
    avatar_url: str = ""
    created_at: Optional[datetime] = None


class TokenResponse(BaseModel):
    """登录 Token 响应"""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: UserResponse


class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class PhoneLoginRequest(BaseModel):
    """手机号验证码登录请求"""
    phone: str = Field(..., pattern=r"^1\d{10}$")
    verification_code: str = Field(..., min_length=6, max_length=6)
