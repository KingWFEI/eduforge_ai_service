"""add student section progress

Revision ID: 793167c843eb
Revises: b7c8d9e0f1a2
Create Date: 2026-06-15 20:16:16.732897
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "793167c843eb"
down_revision: Union[str, Sequence[str], None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "student_section_progress",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column(
            "student_id",
            sa.String(length=64),
            nullable=False,
            comment="学生ID，对应用户主键的字符串形式",
        ),
        sa.Column(
            "course_id",
            sa.String(length=64),
            nullable=False,
            comment="课程业务ID",
        ),
        sa.Column(
            "section_id",
            sa.String(length=64),
            nullable=False,
            comment="课程小节ID，对应二级课程章节",
        ),
        sa.Column(
            "progress",
            sa.Float(),
            server_default=sa.text("0"),
            nullable=False,
            comment="学习进度，范围0.0到1.0",
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default=sa.text("'unlearned'"),
            nullable=False,
            comment="学习状态：completed、learning、unlearned、locked",
        ),
        sa.Column(
            "last_study_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="最后学习时间",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.course_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["section_id"],
            ["course_chapters.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "student_id",
            "section_id",
            name="uq_student_section_progress_student_section",
        ),
    )
    op.create_index(
        "idx_student_section_progress_student_course",
        "student_section_progress",
        ["student_id", "course_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_student_section_progress_course_id"),
        "student_section_progress",
        ["course_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_student_section_progress_last_study_at"),
        "student_section_progress",
        ["last_study_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_student_section_progress_section_id"),
        "student_section_progress",
        ["section_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_student_section_progress_status"),
        "student_section_progress",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_student_section_progress_student_id"),
        "student_section_progress",
        ["student_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_student_section_progress_student_id"),
        table_name="student_section_progress",
    )
    op.drop_index(
        op.f("ix_student_section_progress_status"),
        table_name="student_section_progress",
    )
    op.drop_index(
        op.f("ix_student_section_progress_section_id"),
        table_name="student_section_progress",
    )
    op.drop_index(
        op.f("ix_student_section_progress_last_study_at"),
        table_name="student_section_progress",
    )
    op.drop_index(
        op.f("ix_student_section_progress_course_id"),
        table_name="student_section_progress",
    )
    op.drop_index(
        "idx_student_section_progress_student_course",
        table_name="student_section_progress",
    )
    op.drop_table("student_section_progress")
