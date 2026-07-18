"""resource generation v2 fields

Revision ID: e7f8a9b0c1d2
Revises: c3d4e5f6a7b8
Create Date: 2026-07-18 12:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "e7f8a9b0c1d2"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("resource_generation_tasks") as batch:
        batch.add_column(sa.Column("chapter_id", sa.String(64), nullable=True))
        batch.add_column(sa.Column("section_id", sa.String(64), nullable=True))
        batch.add_column(sa.Column("resource_type", sa.String(50), nullable=True))
        batch.add_column(sa.Column("generation_scope", sa.String(30), nullable=True))
        batch.add_column(sa.Column("knowledge_point_ids_json", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("user_request", sa.Text(), nullable=True))
        batch.add_column(sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("error_code", sa.String(100), nullable=True))
        batch.add_column(sa.Column("failed_step", sa.String(100), nullable=True))
        batch.add_column(sa.Column("retryable", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("artifacts_json", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_index("ix_resource_generation_tasks_chapter_id", ["chapter_id"])
        batch.create_index("ix_resource_generation_tasks_section_id", ["section_id"])
        batch.create_foreign_key("fk_resource_generation_tasks_chapter", "course_chapters", ["chapter_id"], ["id"])
        batch.create_foreign_key("fk_resource_generation_tasks_section", "course_chapters", ["section_id"], ["id"])

    with op.batch_alter_table("learning_resources") as batch:
        batch.add_column(sa.Column("chapter_id", sa.String(64), nullable=True))
        batch.add_column(sa.Column("section_id", sa.String(64), nullable=True))
        batch.add_column(sa.Column("generation_scope", sa.String(30), nullable=True))
        batch.add_column(sa.Column("overview", sa.Text(), nullable=True))
        batch.add_column(sa.Column("source_type", sa.String(30), nullable=True))
        batch.add_column(sa.Column("generation_mode", sa.String(50), nullable=True))
        batch.add_column(sa.Column("external_provider", sa.String(50), nullable=True))
        batch.add_column(sa.Column("external_id", sa.String(100), nullable=True))
        batch.add_column(sa.Column("file_url", sa.String(500), nullable=True))
        batch.add_column(sa.Column("preview_url", sa.String(500), nullable=True))
        batch.add_column(sa.Column("source_references_json", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("generation_task_id", sa.String(64), nullable=True))
        batch.add_column(sa.Column("review_score", sa.Float(), nullable=True))
        batch.add_column(sa.Column("status", sa.String(30), nullable=True))
        batch.create_index("ix_learning_resources_chapter_id", ["chapter_id"])
        batch.create_index("ix_learning_resources_section_id", ["section_id"])
        batch.create_index("ix_learning_resources_external_id", ["external_id"])
        batch.create_index("ix_learning_resources_generation_task_id", ["generation_task_id"])
        batch.create_index("ix_learning_resources_status", ["status"])
        batch.create_foreign_key("fk_learning_resources_chapter", "course_chapters", ["chapter_id"], ["id"])
        batch.create_foreign_key("fk_learning_resources_section", "course_chapters", ["section_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("learning_resources") as batch:
        batch.drop_constraint("fk_learning_resources_section", type_="foreignkey")
        batch.drop_constraint("fk_learning_resources_chapter", type_="foreignkey")
        for name in ("status", "generation_task_id", "external_id", "section_id", "chapter_id"):
            batch.drop_index(f"ix_learning_resources_{name}")
        for name in (
            "status", "review_score", "generation_task_id", "source_references_json", "preview_url",
            "file_url", "external_id", "external_provider", "generation_mode", "source_type", "overview",
            "generation_scope", "section_id", "chapter_id",
        ):
            batch.drop_column(name)

    with op.batch_alter_table("resource_generation_tasks") as batch:
        batch.drop_constraint("fk_resource_generation_tasks_section", type_="foreignkey")
        batch.drop_constraint("fk_resource_generation_tasks_chapter", type_="foreignkey")
        batch.drop_index("ix_resource_generation_tasks_section_id")
        batch.drop_index("ix_resource_generation_tasks_chapter_id")
        for name in (
            "completed_at", "started_at", "artifacts_json", "retryable", "failed_step", "error_code",
            "retry_count", "user_request", "knowledge_point_ids_json", "generation_scope", "resource_type",
            "section_id", "chapter_id",
        ):
            batch.drop_column(name)
