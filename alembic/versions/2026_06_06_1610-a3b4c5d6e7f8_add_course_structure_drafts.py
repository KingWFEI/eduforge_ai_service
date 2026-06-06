"""add course structure drafts

Revision ID: a3b4c5d6e7f8
Revises: f2a7c9d8e1b4
Create Date: 2026-06-06 16:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "f2a7c9d8e1b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    rows = bind.execute(sa.text(f"SHOW COLUMNS FROM `{table_name}`")).mappings().all()
    return {row["Field"] for row in rows}


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    chapter_columns = _columns("course_chapters")
    if "parent_id" not in chapter_columns:
        op.add_column(
            "course_chapters",
            sa.Column(
                "parent_id",
                sa.String(length=64),
                nullable=True,
                comment="父级ID，用于课程章/小节层级结构",
            ),
        )
        op.create_index("ix_course_chapters_parent_id", "course_chapters", ["parent_id"])
        op.create_foreign_key(
            "fk_course_chapters_parent_id",
            "course_chapters",
            "course_chapters",
            ["parent_id"],
            ["id"],
            ondelete="CASCADE",
        )

    if "level" not in chapter_columns:
        op.add_column(
            "course_chapters",
            sa.Column(
                "level",
                sa.Integer(),
                nullable=False,
                server_default="1",
                comment="层级，1 表示章，2 表示小节",
            ),
        )

    if "course_structure_drafts" not in _tables():
        op.create_table(
            "course_structure_drafts",
            sa.Column("id", sa.String(length=64), nullable=False, comment="主键ID"),
            sa.Column("course_id", sa.String(length=64), nullable=False, comment="课程业务ID，通常关联 courses.course_id"),
            sa.Column("source_document_ids_json", sa.JSON(), nullable=True, comment="JSON 数组，生成草稿所使用的课程资料ID"),
            sa.Column("draft_json", sa.JSON(), nullable=False, comment="JSON 对象，AI 识别出的课程章节、小节和知识点草稿"),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="draft", comment="草稿状态，可选值：draft、confirmed、cancelled"),
            sa.Column("created_by", sa.String(length=64), nullable=True, comment="创建人标识"),
            sa.Column("confirmed_by", sa.String(length=64), nullable=True, comment="确认人标识"),
            sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True, comment="确认草稿时间"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True, comment="创建时间"),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True, comment="更新时间"),
            sa.ForeignKeyConstraint(["course_id"], ["courses.course_id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_course_structure_drafts_course_id", "course_structure_drafts", ["course_id"])
        op.create_index("idx_course_structure_drafts_status", "course_structure_drafts", ["status"])


def downgrade() -> None:
    if "course_structure_drafts" in _tables():
        op.drop_index("idx_course_structure_drafts_status", table_name="course_structure_drafts")
        op.drop_index("idx_course_structure_drafts_course_id", table_name="course_structure_drafts")
        op.drop_table("course_structure_drafts")

    chapter_columns = _columns("course_chapters")
    if "parent_id" in chapter_columns:
        op.drop_constraint("fk_course_chapters_parent_id", "course_chapters", type_="foreignkey")
        op.drop_index("ix_course_chapters_parent_id", table_name="course_chapters")
        op.drop_column("course_chapters", "parent_id")
    if "level" in chapter_columns:
        op.drop_column("course_chapters", "level")
