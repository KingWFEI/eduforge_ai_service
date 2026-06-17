"""add course section learning contents

Revision ID: c1d2e3f4a5b6
Revises: b7c8d9e0f1a2
Create Date: 2026-06-16 11:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "course_section_learning_contents",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("course_id", sa.String(length=64), nullable=False),
        sa.Column("chapter_id", sa.String(length=64), nullable=True),
        sa.Column("section_id", sa.String(length=64), nullable=False),
        sa.Column("knowledge_point_id", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=50), nullable=False, server_default="student_learning_content"),
        sa.Column("content_markdown", sa.Text(), nullable=True),
        sa.Column("content_json", sa.JSON(), nullable=True),
        sa.Column("source_chunk_ids", sa.JSON(), nullable=True),
        sa.Column("generation_prompt", sa.Text(), nullable=True),
        sa.Column("generation_model", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="generated"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["course_id"], ["courses.course_id"]),
        sa.ForeignKeyConstraint(["chapter_id"], ["course_chapters.id"]),
        sa.ForeignKeyConstraint(["section_id"], ["course_chapters.id"]),
        sa.ForeignKeyConstraint(["knowledge_point_id"], ["knowledge_points.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_course_section_learning_contents_id", "course_section_learning_contents", ["id"])
    op.create_index("idx_course_section_learning_contents_course_id", "course_section_learning_contents", ["course_id"])
    op.create_index("idx_course_section_learning_contents_chapter_id", "course_section_learning_contents", ["chapter_id"])
    op.create_index("idx_course_section_learning_contents_section_id", "course_section_learning_contents", ["section_id"])
    op.create_index("idx_course_section_learning_contents_status", "course_section_learning_contents", ["status"])


def downgrade() -> None:
    op.drop_index("idx_course_section_learning_contents_status", table_name="course_section_learning_contents")
    op.drop_index("idx_course_section_learning_contents_section_id", table_name="course_section_learning_contents")
    op.drop_index("idx_course_section_learning_contents_chapter_id", table_name="course_section_learning_contents")
    op.drop_index("idx_course_section_learning_contents_course_id", table_name="course_section_learning_contents")
    op.drop_index("ix_course_section_learning_contents_id", table_name="course_section_learning_contents")
    op.drop_table("course_section_learning_contents")
