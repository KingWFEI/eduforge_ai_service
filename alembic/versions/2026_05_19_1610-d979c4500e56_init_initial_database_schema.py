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

    创建全部 9 张表。
    """

    # --- onboarding_submissions（旧表结构差异过大，DROP + CREATE）---
    op.execute('DROP TABLE IF EXISTS onboarding_submissions')
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
    op.execute('DROP TABLE IF EXISTS student_profiles')
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

    # --- users ---
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=True),
        sa.Column('nickname', sa.String(length=100), nullable=True),
        sa.Column('avatar_url', sa.String(length=500), server_default=''),
        sa.Column('role', sa.String(length=30), server_default='student'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # --- courses ---
    op.create_table('courses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_courses_id'), 'courses', ['id'], unique=False)

    # --- course_files ---
    op.create_table('course_files',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('course_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('file_type', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_course_files_id'), 'course_files', ['id'], unique=False)

    # --- onboarding_surveys ---
    op.create_table('onboarding_surveys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('survey_id', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('status', sa.String(length=30), server_default='draft', nullable=False),
        sa.Column('target_role', sa.String(length=30), server_default='student', nullable=False),
        sa.Column('target_course_id', sa.String(length=100), nullable=True),
        sa.Column('submit_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('created_by', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_onboarding_surveys_id'), 'onboarding_surveys', ['id'], unique=False)
    op.create_index(op.f('ix_onboarding_surveys_survey_id'), 'onboarding_surveys', ['survey_id'], unique=True)
    op.create_index(op.f('ix_onboarding_surveys_status'), 'onboarding_surveys', ['status'], unique=False)
    op.create_index(op.f('ix_onboarding_surveys_target_role'), 'onboarding_surveys', ['target_role'], unique=False)

    # --- onboarding_questions ---
    op.create_table('onboarding_questions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.String(length=50), nullable=False),
        sa.Column('survey_id', sa.String(length=50), nullable=False),
        sa.Column('step', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('subtitle', sa.String(length=500), nullable=True),
        sa.Column('type', sa.String(length=30), nullable=False),
        sa.Column('required', sa.Boolean(), server_default=sa.text('1'), nullable=False),
        sa.Column('matrix_items', sa.JSON(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default=sa.text('0'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_onboarding_questions_id'), 'onboarding_questions', ['id'], unique=False)
    op.create_index(op.f('ix_onboarding_questions_question_id'), 'onboarding_questions', ['question_id'], unique=True)
    op.create_index(op.f('ix_onboarding_questions_survey_id'), 'onboarding_questions', ['survey_id'], unique=False)

    # --- onboarding_options ---
    op.create_table('onboarding_options',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('option_id', sa.String(length=50), nullable=False),
        sa.Column('question_id', sa.String(length=50), nullable=False),
        sa.Column('label', sa.String(length=200), nullable=False),
        sa.Column('value', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('icon', sa.String(length=100), nullable=True),
        sa.Column('color', sa.String(length=50), nullable=True),
        sa.Column('profile_mapping', sa.JSON(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default=sa.text('0'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_onboarding_options_id'), 'onboarding_options', ['id'], unique=False)
    op.create_index(op.f('ix_onboarding_options_option_id'), 'onboarding_options', ['option_id'], unique=True)
    op.create_index(op.f('ix_onboarding_options_question_id'), 'onboarding_options', ['question_id'], unique=False)

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

    op.drop_table('onboarding_options')
    op.drop_table('onboarding_questions')
    op.drop_table('onboarding_surveys')
    op.drop_table('course_files')
    op.drop_table('courses')
    op.drop_table('users')

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
