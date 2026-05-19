"""feat: add status fields to profile_analyses

Revision ID: 11456e96ecba
Revises: d979c4500e56
Create Date: 2026-05-19 17:02:27.415837

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '11456e96ecba'
down_revision: Union[str, Sequence[str], None] = 'd979c4500e56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add status tracking fields to profile_analyses."""
    op.add_column('profile_analyses', sa.Column('submission_id', sa.String(length=64), nullable=False))
    op.add_column('profile_analyses', sa.Column('status', sa.String(length=20), nullable=False))
    op.add_column('profile_analyses', sa.Column('progress', sa.Integer(), nullable=True))
    op.add_column('profile_analyses', sa.Column('current_step', sa.String(length=200), nullable=True))
    op.add_column('profile_analyses', sa.Column('agent_trace_json', sa.JSON(), nullable=True))
    op.add_column('profile_analyses', sa.Column('error_json', sa.JSON(), nullable=True))
    op.add_column('profile_analyses', sa.Column('started_at', sa.DateTime(), nullable=True))
    op.add_column('profile_analyses', sa.Column('completed_at', sa.DateTime(), nullable=True))
    op.alter_column('profile_analyses', 'profile_id',
               existing_type=mysql.VARCHAR(length=64),
               nullable=True)
    op.alter_column('profile_analyses', 'analysis_text',
               existing_type=mysql.TEXT(),
               nullable=True)
    op.create_index(op.f('ix_profile_analyses_submission_id'), 'profile_analyses', ['submission_id'], unique=False)


def downgrade() -> None:
    """Revert profile_analyses changes."""
    op.drop_index(op.f('ix_profile_analyses_submission_id'), table_name='profile_analyses')
    op.alter_column('profile_analyses', 'analysis_text',
               existing_type=mysql.TEXT(),
               nullable=False)
    op.alter_column('profile_analyses', 'profile_id',
               existing_type=mysql.VARCHAR(length=64),
               nullable=False)
    op.drop_column('profile_analyses', 'completed_at')
    op.drop_column('profile_analyses', 'started_at')
    op.drop_column('profile_analyses', 'error_json')
    op.drop_column('profile_analyses', 'agent_trace_json')
    op.drop_column('profile_analyses', 'current_step')
    op.drop_column('profile_analyses', 'progress')
    op.drop_column('profile_analyses', 'status')
    op.drop_column('profile_analyses', 'submission_id')
