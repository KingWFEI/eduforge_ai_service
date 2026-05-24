from app.models.user import User


def format_user_id(user_id: int) -> str:
    """将数字 ID 格式化为前端友好的字符串格式（如 u_001）"""
    return f"u_{user_id:03d}"


def user_to_response(user: User) -> dict:
    """将 User ORM 对象转换为统一的响应字典"""
    return {
        "user_id": format_user_id(user.id),
        "username": user.username,
        "name": user.name or user.username,
        "phone": user.phone or "",
        "email": user.email or "",
        "role": user.role,
        "status": user.status or "normal",
        "is_active": user.is_active if user.is_active is not None else True,
        "avatar_url": user.avatar_url or "",
        "created_at": user.created_at,
    }
