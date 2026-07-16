"""add section exercise submissions

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-26 18:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "section_exercise_submissions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("submit_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("course_id", sa.String(length=64), nullable=False),
        sa.Column("section_id", sa.String(length=64), nullable=False),
        sa.Column("total_count", sa.Integer(), nullable=False),
        sa.Column("correct_count", sa.Integer(), nullable=False),
        sa.Column("incorrect_count", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.course_id"]),
        sa.ForeignKeyConstraint(["section_id"], ["course_chapters.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("submit_id"),
    )
    op.create_index(
        "ix_section_exercise_submissions_submit_id",
        "section_exercise_submissions",
        ["submit_id"],
        unique=False,
    )
    op.create_index(
        "idx_section_exercise_submissions_user_course_section",
        "section_exercise_submissions",
        ["user_id", "course_id", "section_id"],
        unique=False,
    )

    op.create_table(
        "section_exercise_answers",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("submit_id", sa.String(length=64), nullable=False),
        sa.Column("exercise_id", sa.String(length=128), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("user_answer", sa.JSON(), nullable=False),
        sa.Column("is_correct", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_section_exercise_answers_submit_id",
        "section_exercise_answers",
        ["submit_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_section_exercise_answers_submit_id", table_name="section_exercise_answers")
    op.drop_table("section_exercise_answers")
    op.drop_index(
        "idx_section_exercise_submissions_user_course_section",
        table_name="section_exercise_submissions",
    )
    op.drop_index("ix_section_exercise_submissions_submit_id", table_name="section_exercise_submissions")
    op.drop_table("section_exercise_submissions")
