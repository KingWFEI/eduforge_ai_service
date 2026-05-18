from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.constants.role import Role


class RegisterRequest(BaseModel):
    """用户注册请求"""
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=6)
    nickname: str = Field(..., min_length=1)
    role: Role = Role.STUDENT


class UserCreate(RegisterRequest):
    """创建用户（带可选邮箱）"""
    email: Optional[str] = None


class AdminUserCreate(UserCreate):
    """管理员创建用户"""
    role: Role = Role.STUDENT


class UserRoleUpdate(BaseModel):
    """用户角色更新请求"""
    role: Role


class UserResponse(BaseModel):
    """用户信息响应"""
    user_id: str
    username: str
    nickname: str
    role: Role
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
