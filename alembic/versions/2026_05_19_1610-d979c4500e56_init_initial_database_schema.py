"""init: initial database schema

Revision ID: d979c4500e56
Revises:
Create Date: 2026-05-19 16:10:10.390220

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd979c4500e56'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """迁移至新模型 schema。

    仅处理 3 张变更的表，其余表保持不变。
    - onboarding_submissions：旧表（int PK）→ 新表（string PK，列更名）
    - student_profiles：旧表（int PK）→ 新表（string PK，列更名 + 新增字段）
    - profile_analyses：全新表
    """

    # --- onboarding_submissions（旧表结构差异过大，DROP + CREATE）---
    op.drop_table('onboarding_submissions')
    op.create_table('onboarding_submissions',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('survey_id', sa.String(length=64), nullable=False),
        sa.Column('student_id', sa.String(length=64), nullable=False),
        sa.Column('answers_json', sa.JSON(), nullable=False),
        sa.Column('generated_profile_id', sa.String(length=64), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_onboarding_submissions_id'), 'onboarding_submissions', ['id'], unique=False)
    op.create_index(op.f('ix_onboarding_submissions_survey_id'), 'onboarding_submissions', ['survey_id'], unique=False)
    op.create_index(op.f('ix_onboarding_submissions_student_id'), 'onboarding_submissions', ['student_id'], unique=False)

    # --- student_profiles（旧表结构差异过大，DROP + CREATE）---
    op.drop_table('student_profiles')
    op.create_table('student_profiles',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('student_id', sa.String(length=64), nullable=False),
        sa.Column('major', sa.String(length=100), nullable=True),
        sa.Column('grade', sa.String(length=50), nullable=True),
        sa.Column('target_course', sa.String(length=100), nullable=True),
        sa.Column('learning_goals_json', sa.JSON(), nullable=True),
        sa.Column('coding_level', sa.String(length=50), nullable=True),
        sa.Column('math_level', sa.String(length=50), nullable=True),
        sa.Column('course_level', sa.String(length=50), nullable=True),
        sa.Column('learning_preferences_json', sa.JSON(), nullable=True),
        sa.Column('weaknesses_json', sa.JSON(), nullable=True),
        sa.Column('cognitive_style_json', sa.JSON(), nullable=True),
        sa.Column('time_budget', sa.String(length=100), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=True),
        sa.Column('last_updated', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_student_profiles_id'), 'student_profiles', ['id'], unique=False)
    op.create_index(op.f('ix_student_profiles_student_id'), 'student_profiles', ['student_id'], unique=False)

    # --- profile_analyses（全新表）---
    op.create_table('profile_analyses',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('student_id', sa.String(length=64), nullable=False),
        sa.Column('profile_id', sa.String(length=64), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('analysis_type', sa.String(length=50), nullable=False),
        sa.Column('analysis_text', sa.Text(), nullable=False),
        sa.Column('learning_suggestion', sa.Text(), nullable=True),
        sa.Column('resource_strategy_json', sa.JSON(), nullable=True),
        sa.Column('weakness_analysis_json', sa.JSON(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_profile_analyses_id'), 'profile_analyses', ['id'], unique=False)
    op.create_index(op.f('ix_profile_analyses_profile_id'), 'profile_analyses', ['profile_id'], unique=False)
    op.create_index(op.f('ix_profile_analyses_student_id'), 'profile_analyses', ['student_id'], unique=False)


def downgrade() -> None:
    """回退至旧 schema。"""
    op.drop_table('profile_analyses')

    op.drop_table('student_profiles')
    op.create_table('student_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('profile_id', sa.String(length=50), nullable=False),
        sa.Column('student_id', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=True),
        sa.Column('major', sa.String(length=100), nullable=True),
        sa.Column('grade', sa.String(length=50), nullable=True),
        sa.Column('target_course', sa.String(length=200), nullable=True),
        sa.Column('learning_goals', sa.JSON(), nullable=True),
        sa.Column('coding_level', sa.String(length=50), nullable=True),
        sa.Column('math_level', sa.String(length=50), nullable=True),
        sa.Column('course_level', sa.String(length=50), nullable=True),
        sa.Column('learning_preferences', sa.JSON(), nullable=True),
        sa.Column('weaknesses', sa.JSON(), nullable=True),
        sa.Column('cognitive_style', sa.JSON(), nullable=True),
        sa.Column('time_budget', sa.String(length=100), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_student_profiles_profile_id', 'student_profiles', ['profile_id'], unique=True)
    op.create_index('ix_student_profiles_student_id', 'student_profiles', ['student_id'], unique=True)

    op.drop_table('onboarding_submissions')
    op.create_table('onboarding_submissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('submission_id', sa.String(length=50), nullable=False),
        sa.Column('survey_id', sa.String(length=50), nullable=False),
        sa.Column('student_id', sa.String(length=100), nullable=False),
        sa.Column('answers', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_onboarding_submissions_submission_id', 'onboarding_submissions', ['submission_id'], unique=True)
