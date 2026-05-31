"""normalize vector index records column order

Revision ID: a7c6e5d4b3a2
Revises: 5e3a8c7d9b10
Create Date: 2026-05-31 20:12:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a7c6e5d4b3a2"
down_revision: Union[str, Sequence[str], None] = "5e3a8c7d9b10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        ALTER TABLE vector_index_records
            MODIFY COLUMN id VARCHAR(64) NOT NULL FIRST,
            MODIFY COLUMN course_id VARCHAR(64) NOT NULL AFTER id,
            MODIFY COLUMN document_id VARCHAR(64) NOT NULL AFTER course_id,
            MODIFY COLUMN index_type VARCHAR(50) NULL DEFAULT 'chroma' AFTER document_id,
            MODIFY COLUMN collection_name VARCHAR(100) NULL AFTER index_type,
            MODIFY COLUMN status VARCHAR(30) NULL DEFAULT 'processing' AFTER collection_name,
            MODIFY COLUMN chunk_count INT NULL DEFAULT 0 AFTER status,
            MODIFY COLUMN success_count INT NULL DEFAULT 0 AFTER chunk_count,
            MODIFY COLUMN failed_count INT NULL DEFAULT 0 AFTER success_count,
            MODIFY COLUMN error_message TEXT NULL AFTER failed_count,
            MODIFY COLUMN started_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP AFTER error_message,
            MODIFY COLUMN finished_at DATETIME NULL AFTER started_at,
            MODIFY COLUMN created_by VARCHAR(64) NULL AFTER finished_at,
            MODIFY COLUMN created_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP AFTER created_by
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    pass
