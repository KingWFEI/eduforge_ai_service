"""normalize student ids to user ids

Revision ID: b4f7e0a9c2d1
Revises: 89739d0f2742
Create Date: 2026-05-31 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b4f7e0a9c2d1"
down_revision: Union[str, Sequence[str], None] = "89739d0f2742"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convert old display IDs such as u_001 into real user ID strings."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name in sorted(inspector.get_table_names()):
        column_names = {column["name"] for column in inspector.get_columns(table_name)}
        if "student_id" not in column_names:
            continue

        op.execute(
            f"""
            UPDATE IGNORE `{table_name}`
            SET student_id = CAST(CAST(SUBSTRING(student_id, 3) AS UNSIGNED) AS CHAR)
            WHERE student_id REGEXP '^u_[0-9]+$'
            """
        )


def downgrade() -> None:
    """Data normalization is intentionally irreversible."""
    pass
