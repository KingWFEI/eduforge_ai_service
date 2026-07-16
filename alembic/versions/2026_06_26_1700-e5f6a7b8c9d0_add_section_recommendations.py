"""add section recommendations cache

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9, 793167c843eb
Create Date: 2026-06-26 17:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = ("d4e5f6a7b8c9", "793167c843eb")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "section_recommendations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("course_id", sa.String(length=64), nullable=False),
        sa.Column("section_id", sa.String(length=64), nullable=False),
        sa.Column("chapter_id", sa.String(length=64), nullable=True),
        sa.Column("suggestion", sa.Text(), nullable=False),
        sa.Column("resources_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "course_id", "section_id", name="uk_user_course_section"),
    )
    op.create_index(
        "idx_section_recommendations_user_course",
        "section_recommendations",
        ["user_id", "course_id"],
        unique=False,
    )
    op.create_index(
        "idx_section_recommendations_section",
        "section_recommendations",
        ["section_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_section_recommendations_section", table_name="section_recommendations")
    op.drop_index("idx_section_recommendations_user_course", table_name="section_recommendations")
    op.drop_table("section_recommendations")
