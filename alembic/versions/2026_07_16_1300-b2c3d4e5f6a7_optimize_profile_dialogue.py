"""optimize profile dialogue state and idempotency

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-16 13:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "profile_dialogue_sessions",
        sa.Column("dialogue_state", sa.JSON(), nullable=True),
    )
    op.execute("UPDATE profile_dialogue_sessions SET dialogue_state = JSON_OBJECT() WHERE dialogue_state IS NULL")
    op.alter_column(
        "profile_dialogue_sessions",
        "dialogue_state",
        existing_type=sa.JSON(),
        nullable=False,
    )
    op.add_column(
        "profile_dialogue_messages",
        sa.Column("client_message_id", sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_profile_dialogue_message_client_id",
        "profile_dialogue_messages",
        ["session_id", "client_message_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_profile_dialogue_message_client_id",
        "profile_dialogue_messages",
        type_="unique",
    )
    op.drop_column("profile_dialogue_messages", "client_message_id")
    op.drop_column("profile_dialogue_sessions", "dialogue_state")
