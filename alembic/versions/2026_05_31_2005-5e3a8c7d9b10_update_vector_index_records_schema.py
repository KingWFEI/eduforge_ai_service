"""update vector index records schema

Revision ID: 5e3a8c7d9b10
Revises: b4f7e0a9c2d1
Create Date: 2026-05-31 20:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5e3a8c7d9b10"
down_revision: Union[str, Sequence[str], None] = "b4f7e0a9c2d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "vector_index_records"


def _column_names(connection) -> set[str]:
    return {column["name"] for column in sa.inspect(connection).get_columns(TABLE_NAME)}


def _drop_foreign_keys(connection) -> None:
    inspector = sa.inspect(connection)

    for fk in inspector.get_foreign_keys(TABLE_NAME):
        constrained_columns = set(fk.get("constrained_columns") or [])

        if constrained_columns & {"course_id", "document_id"} and fk.get("name"):
            op.drop_constraint(fk["name"], TABLE_NAME, type_="foreignkey")


def _drop_indexes(connection, index_names: set[str]) -> None:
    inspector = sa.inspect(connection)
    existing_indexes = {index["name"] for index in inspector.get_indexes(TABLE_NAME)}

    for index_name in index_names & existing_indexes:
        op.drop_index(index_name, table_name=TABLE_NAME)


def _create_index_if_missing(connection, index_name: str, columns: list[str]) -> None:
    inspector = sa.inspect(connection)
    existing_indexes = {index["name"] for index in inspector.get_indexes(TABLE_NAME)}

    if index_name not in existing_indexes:
        op.create_index(index_name, TABLE_NAME, columns, unique=False)


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()

    _drop_foreign_keys(connection)
    _drop_indexes(
        connection,
        {
            "ix_vector_index_records_course_id",
            "ix_vector_index_records_document_id",
            "ix_vector_index_records_id",
            "ix_vector_index_records_status",
        },
    )

    columns = _column_names(connection)

    if "vector_store" in columns and "index_type" not in columns:
        op.alter_column(
            TABLE_NAME,
            "vector_store",
            new_column_name="index_type",
            existing_type=sa.String(length=50),
            type_=sa.String(length=50),
            nullable=True,
            server_default="chroma",
        )
    elif "index_type" in columns:
        op.alter_column(
            TABLE_NAME,
            "index_type",
            existing_type=sa.String(length=50),
            nullable=True,
            server_default="chroma",
        )
    else:
        op.add_column(
            TABLE_NAME,
            sa.Column("index_type", sa.String(length=50), server_default="chroma", nullable=True),
        )

    if "completed_at" in columns and "finished_at" not in columns:
        op.alter_column(
            TABLE_NAME,
            "completed_at",
            new_column_name="finished_at",
            existing_type=sa.DateTime(),
            type_=sa.DateTime(),
            nullable=True,
        )
    elif "finished_at" not in columns:
        op.add_column(TABLE_NAME, sa.Column("finished_at", sa.DateTime(), nullable=True))

    columns = _column_names(connection)

    if "success_count" not in columns:
        op.add_column(
            TABLE_NAME,
            sa.Column("success_count", sa.Integer(), server_default="0", nullable=True),
        )

    if "failed_count" not in columns:
        op.add_column(
            TABLE_NAME,
            sa.Column("failed_count", sa.Integer(), server_default="0", nullable=True),
        )

    if "started_at" not in columns:
        op.add_column(
            TABLE_NAME,
            sa.Column("started_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        )

    if "created_by" not in columns:
        op.add_column(TABLE_NAME, sa.Column("created_by", sa.String(length=64), nullable=True))

    connection.execute(sa.text(f"UPDATE {TABLE_NAME} SET document_id = '' WHERE document_id IS NULL"))
    connection.execute(sa.text(f"UPDATE {TABLE_NAME} SET index_type = 'chroma' WHERE index_type IS NULL"))
    connection.execute(sa.text(f"UPDATE {TABLE_NAME} SET status = 'processing' WHERE status IS NULL"))
    connection.execute(sa.text(f"UPDATE {TABLE_NAME} SET chunk_count = 0 WHERE chunk_count IS NULL"))
    connection.execute(sa.text(f"UPDATE {TABLE_NAME} SET success_count = 0 WHERE success_count IS NULL"))
    connection.execute(sa.text(f"UPDATE {TABLE_NAME} SET failed_count = 0 WHERE failed_count IS NULL"))
    connection.execute(sa.text(f"UPDATE {TABLE_NAME} SET started_at = created_at WHERE started_at IS NULL"))

    op.alter_column(
        TABLE_NAME,
        "document_id",
        existing_type=sa.String(length=64),
        nullable=False,
    )
    op.alter_column(
        TABLE_NAME,
        "collection_name",
        existing_type=sa.String(length=100),
        nullable=True,
    )
    op.alter_column(
        TABLE_NAME,
        "status",
        existing_type=sa.String(length=30),
        nullable=True,
        server_default="processing",
    )
    op.alter_column(
        TABLE_NAME,
        "chunk_count",
        existing_type=sa.Integer(),
        nullable=True,
        server_default="0",
    )
    op.alter_column(
        TABLE_NAME,
        "created_at",
        existing_type=sa.DateTime(),
        nullable=True,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )

    _create_index_if_missing(connection, "idx_vector_index_course_id", ["course_id"])
    _create_index_if_missing(connection, "idx_vector_index_document_id", ["document_id"])
    _create_index_if_missing(connection, "idx_vector_index_status", ["status"])


def downgrade() -> None:
    """Downgrade schema."""
    connection = op.get_bind()

    _drop_indexes(
        connection,
        {
            "idx_vector_index_course_id",
            "idx_vector_index_document_id",
            "idx_vector_index_status",
        },
    )

    columns = _column_names(connection)

    connection.execute(sa.text(f"UPDATE {TABLE_NAME} SET document_id = NULL WHERE document_id = ''"))
    connection.execute(sa.text(f"UPDATE {TABLE_NAME} SET index_type = 'chroma' WHERE index_type IS NULL"))
    connection.execute(sa.text(f"UPDATE {TABLE_NAME} SET collection_name = '' WHERE collection_name IS NULL"))
    connection.execute(sa.text(f"UPDATE {TABLE_NAME} SET status = 'processing' WHERE status IS NULL"))

    op.alter_column(
        TABLE_NAME,
        "document_id",
        existing_type=sa.String(length=64),
        nullable=True,
    )

    if "index_type" in columns and "vector_store" not in columns:
        op.alter_column(
            TABLE_NAME,
            "index_type",
            new_column_name="vector_store",
            existing_type=sa.String(length=50),
            type_=sa.String(length=50),
            nullable=False,
            server_default=None,
        )

    if "finished_at" in columns and "completed_at" not in columns:
        op.alter_column(
            TABLE_NAME,
            "finished_at",
            new_column_name="completed_at",
            existing_type=sa.DateTime(),
            type_=sa.DateTime(),
            nullable=True,
        )

    for column_name in ("success_count", "failed_count", "started_at", "created_by"):
        if column_name in columns:
            op.drop_column(TABLE_NAME, column_name)

    op.alter_column(
        TABLE_NAME,
        "collection_name",
        existing_type=sa.String(length=100),
        nullable=False,
    )
    op.alter_column(
        TABLE_NAME,
        "status",
        existing_type=sa.String(length=30),
        nullable=False,
        server_default=None,
    )
    op.alter_column(
        TABLE_NAME,
        "chunk_count",
        existing_type=sa.Integer(),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        TABLE_NAME,
        "created_at",
        existing_type=sa.DateTime(),
        nullable=True,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )

    op.create_index(op.f("ix_vector_index_records_course_id"), TABLE_NAME, ["course_id"], unique=False)
    op.create_index(op.f("ix_vector_index_records_document_id"), TABLE_NAME, ["document_id"], unique=False)
    op.create_index(op.f("ix_vector_index_records_id"), TABLE_NAME, ["id"], unique=False)
    op.create_index(op.f("ix_vector_index_records_status"), TABLE_NAME, ["status"], unique=False)
    op.create_foreign_key(
        "fk_vector_index_records_course_id",
        TABLE_NAME,
        "courses",
        ["course_id"],
        ["course_id"],
    )
    op.create_foreign_key(
        "fk_vector_index_records_document_id",
        TABLE_NAME,
        "course_documents",
        ["document_id"],
        ["id"],
    )
