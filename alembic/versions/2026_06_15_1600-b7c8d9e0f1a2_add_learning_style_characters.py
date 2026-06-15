"""add learning style characters

Revision ID: b7c8d9e0f1a2
Revises: 0ab6eb679a23
Create Date: 2026-06-15 16:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = "0ab6eb679a23"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "learning_style_characters",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("image_url", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("style_prompt", sa.Text(), nullable=True),
        sa.Column("feature_tags", sa.JSON(), nullable=True),
        sa.Column("suitable_methods", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="DRAFT"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_learning_style_characters_id", "learning_style_characters", ["id"])
    op.create_index("ix_learning_style_characters_code", "learning_style_characters", ["code"], unique=True)
    op.create_index("ix_learning_style_characters_status", "learning_style_characters", ["status"])

    op.create_table(
        "student_style_matches",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("student_id", sa.String(length=64), nullable=False),
        sa.Column("profile_id", sa.String(length=64), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("character_id", sa.String(length=64), nullable=False),
        sa.Column("character_version", sa.Integer(), nullable=False),
        sa.Column("match_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("match_reason", sa.Text(), nullable=True),
        sa.Column("matched_features", sa.JSON(), nullable=True),
        sa.Column("matching_source", sa.String(length=50), nullable=False, server_default="rule"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", "profile_id", name="uq_student_style_match_profile"),
    )
    op.create_index("ix_student_style_matches_id", "student_style_matches", ["id"])
    op.create_index("ix_student_style_matches_student_id", "student_style_matches", ["student_id"])
    op.create_index("ix_student_style_matches_profile_id", "student_style_matches", ["profile_id"])
    op.create_index("ix_student_style_matches_character_id", "student_style_matches", ["character_id"])


def downgrade() -> None:
    op.drop_index("ix_student_style_matches_character_id", table_name="student_style_matches")
    op.drop_index("ix_student_style_matches_profile_id", table_name="student_style_matches")
    op.drop_index("ix_student_style_matches_student_id", table_name="student_style_matches")
    op.drop_index("ix_student_style_matches_id", table_name="student_style_matches")
    op.drop_table("student_style_matches")
    op.drop_index("ix_learning_style_characters_status", table_name="learning_style_characters")
    op.drop_index("ix_learning_style_characters_code", table_name="learning_style_characters")
    op.drop_index("ix_learning_style_characters_id", table_name="learning_style_characters")
    op.drop_table("learning_style_characters")
