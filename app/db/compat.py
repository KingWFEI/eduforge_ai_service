from sqlalchemy import inspect, text


def ensure_user_profile_columns(engine):
    """
    数据库兼容迁移：确保 users 表包含 nickname 和 avatar_url 列。
    用于在模型变更后对已有数据库表做增量列补充。
    """
    inspector = inspect(engine)
    if not inspector.has_table("users"):
        return

    columns = {column["name"] for column in inspector.get_columns("users")}

    with engine.begin() as connection:
        if "nickname" not in columns:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN nickname VARCHAR(100) NULL")
            )

        if "avatar_url" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500) "
                    "NULL DEFAULT ''"
                )
            )
