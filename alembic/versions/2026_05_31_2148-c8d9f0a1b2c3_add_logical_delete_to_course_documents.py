"""add logical delete to course documents

Revision ID: c8d9f0a1b2c3
Revises: a7c6e5d4b3a2
Create Date: 2026-05-31 21:48:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c8d9f0a1b2c3"
down_revision: Union[str, Sequence[str], None] = "a7c6e5d4b3a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def upgrade() -> None:
    """Add logical-delete fields for course documents and knowledge chunks."""
    course_document_columns = _columns("course_documents")
    if "status" not in course_document_columns:
        op.add_column(
            "course_documents",
            sa.Column("status", sa.String(length=30), nullable=True, server_default="active"),
        )
        op.execute("UPDATE course_documents SET status = 'active' WHERE status IS NULL")

    course_document_indexes = _indexes("course_documents")
    if "ix_course_documents_status" not in course_document_indexes:
        op.create_index("ix_course_documents_status", "course_documents", ["status"], unique=False)

    knowledge_chunk_columns = _columns("knowledge_chunks")
    if "deleted" not in knowledge_chunk_columns:
        op.add_column(
            "knowledge_chunks",
            sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )
        op.execute("UPDATE knowledge_chunks SET deleted = 0 WHERE deleted IS NULL")

    knowledge_chunk_indexes = _indexes("knowledge_chunks")
    if "ix_knowledge_chunks_deleted" not in knowledge_chunk_indexes:
        op.create_index("ix_knowledge_chunks_deleted", "knowledge_chunks", ["deleted"], unique=False)


def downgrade() -> None:
    """Remove logical-delete fields."""
    knowledge_chunk_indexes = _indexes("knowledge_chunks")
    if "ix_knowledge_chunks_deleted" in knowledge_chunk_indexes:
        op.drop_index("ix_knowledge_chunks_deleted", table_name="knowledge_chunks")

    knowledge_chunk_columns = _columns("knowledge_chunks")
    if "deleted" in knowledge_chunk_columns:
        op.drop_column("knowledge_chunks", "deleted")

    course_document_indexes = _indexes("course_documents")
    if "ix_course_documents_status" in course_document_indexes:
        op.drop_index("ix_course_documents_status", table_name="course_documents")

    course_document_columns = _columns("course_documents")
    if "status" in course_document_columns:
        op.drop_column("course_documents", "status")
