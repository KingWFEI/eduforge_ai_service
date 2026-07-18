"""restore users.id auto increment

Revision ID: f9a0b1c2d3e4
Revises: e7f8a9b0c1d2
Create Date: 2026-07-18 17:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "f9a0b1c2d3e4"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


USER_FOREIGN_KEYS = (
    ("courses_ibfk_1", "courses", ["created_by"], None),
    ("profile_dialogue_messages_ibfk_2", "profile_dialogue_messages", ["student_id"], "CASCADE"),
    ("profile_dialogue_sessions_ibfk_1", "profile_dialogue_sessions", ["student_id"], "CASCADE"),
    ("tutor_sessions_ibfk_1", "tutor_sessions", ["student_id"], "CASCADE"),
    ("user_onboarding_status_ibfk_1", "user_onboarding_status", ["user_id"], "CASCADE"),
)


def _drop_user_foreign_keys() -> None:
    for constraint_name, table_name, _columns, _ondelete in USER_FOREIGN_KEYS:
        op.drop_constraint(constraint_name, table_name, type_="foreignkey")


def _create_user_foreign_keys() -> None:
    for constraint_name, table_name, columns, ondelete in USER_FOREIGN_KEYS:
        op.create_foreign_key(
            constraint_name,
            table_name,
            "users",
            columns,
            ["id"],
            ondelete=ondelete,
        )


def upgrade() -> None:
    _drop_user_foreign_keys()
    op.alter_column(
        "users",
        "id",
        existing_type=sa.Integer(),
        existing_nullable=False,
        autoincrement=True,
    )
    _create_user_foreign_keys()


def downgrade() -> None:
    _drop_user_foreign_keys()
    op.alter_column(
        "users",
        "id",
        existing_type=sa.Integer(),
        existing_nullable=False,
        autoincrement=False,
    )
    _create_user_foreign_keys()
