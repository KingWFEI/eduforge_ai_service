from app.models.user import User


def format_user_id(user_id: int) -> str:
    """Return the persisted users.id value as the external user identifier."""
    return str(user_id)


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
