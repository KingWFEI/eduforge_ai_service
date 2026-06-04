"""add general learning profile tables

Revision ID: d1e2f3a4b5c6
Revises: c8d9f0a1b2c3
Create Date: 2026-06-04 22:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c8d9f0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "user_onboarding_status",
        "status",
        existing_type=sa.String(length=30),
        existing_nullable=False,
        comment="引导问卷状态",
    )

    op.create_table(
        "student_learning_profiles",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("student_id", sa.String(length=64), nullable=False),
        sa.Column("learning_preferences_json", sa.JSON(), nullable=True),
        sa.Column("cognitive_traits_json", sa.JSON(), nullable=True),
        sa.Column("learning_habits_json", sa.JSON(), nullable=True),
        sa.Column("motivation_factors_json", sa.JSON(), nullable=True),
        sa.Column("general_strengths_json", sa.JSON(), nullable=True),
        sa.Column("general_challenges_json", sa.JSON(), nullable=True),
        sa.Column("preferred_pace", sa.String(length=100), nullable=True),
        sa.Column("available_time_json", sa.JSON(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("profile_dimensions_json", sa.JSON(), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        sa.Column("confidence_json", sa.JSON(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_student_learning_profiles_id", "student_learning_profiles", ["id"])
    op.create_index(
        "ix_student_learning_profiles_student_id",
        "student_learning_profiles",
        ["student_id"],
        unique=True,
    )

    op.create_table(
        "student_domain_competencies",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("student_id", sa.String(length=64), nullable=False),
        sa.Column("domain_type", sa.String(length=50), nullable=False),
        sa.Column("domain_id", sa.String(length=64), nullable=True),
        sa.Column("domain_name", sa.String(length=200), nullable=False),
        sa.Column("competency_level", sa.String(length=50), nullable=True),
        sa.Column("strengths_json", sa.JSON(), nullable=True),
        sa.Column("weaknesses_json", sa.JSON(), nullable=True),
        sa.Column("knowledge_state_json", sa.JSON(), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", "domain_type", "domain_id", name="uq_student_domain_competency"),
    )
    op.create_index("ix_student_domain_competencies_id", "student_domain_competencies", ["id"])
    op.create_index("ix_student_domain_competencies_student_id", "student_domain_competencies", ["student_id"])

    op.create_table(
        "student_learning_contexts",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("student_id", sa.String(length=64), nullable=False),
        sa.Column("course_id", sa.String(length=64), nullable=True),
        sa.Column("course_name", sa.String(length=200), nullable=True),
        sa.Column("learning_goals_json", sa.JSON(), nullable=True),
        sa.Column("time_budget_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_student_learning_contexts_id", "student_learning_contexts", ["id"])
    op.create_index("ix_student_learning_contexts_student_id", "student_learning_contexts", ["student_id"])
    op.create_index("ix_student_learning_contexts_course_id", "student_learning_contexts", ["course_id"])
    op.create_index("ix_student_learning_contexts_status", "student_learning_contexts", ["status"])

    op.execute(
        """
        INSERT INTO student_learning_profiles (
            id,
            student_id,
            learning_preferences_json,
            cognitive_traits_json,
            general_challenges_json,
            available_time_json,
            summary,
            confidence_json,
            version,
            source,
            last_updated,
            created_at
        )
        SELECT
            id,
            student_id,
            learning_preferences_json,
            cognitive_style_json,
            weaknesses_json,
            CASE
                WHEN time_budget IS NULL THEN NULL
                ELSE JSON_OBJECT('description', time_budget)
            END,
            summary,
            CASE
                WHEN confidence IS NULL THEN NULL
                ELSE JSON_OBJECT('overall', confidence)
            END,
            1,
            source,
            last_updated,
            created_at
        FROM student_profiles
        WHERE learning_preferences_json IS NOT NULL
           OR cognitive_style_json IS NOT NULL
           OR weaknesses_json IS NOT NULL
           OR time_budget IS NOT NULL
           OR summary IS NOT NULL
           OR confidence IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE profile_dialogue_sessions
        SET current_slot = 'learning_style',
            collected_slots_json = JSON_ARRAY(),
            missing_slots_json = JSON_ARRAY(
                'learning_style',
                'learning_habits',
                'motivation',
                'strengths_challenges',
                'pace_and_time'
            ),
            extracted_fields_json = JSON_OBJECT(),
            progress = 0
        WHERE status = 'collecting'
        """
    )
    op.alter_column(
        "profile_dialogue_sessions",
        "current_slot",
        existing_type=sa.String(length=50),
        server_default="learning_style",
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "user_onboarding_status",
        "status",
        existing_type=sa.String(length=30),
        existing_nullable=False,
        comment=(
            "    # not_started：未开始     # processing：问卷已提交，正在生成画像 "
            "    # completed：已完成     # failed：画像生成失败，可重新提交 "
            "    # skipped：已跳过     # reset_required：需要重新填写"
        ),
    )
    op.alter_column(
        "profile_dialogue_sessions",
        "current_slot",
        existing_type=sa.String(length=50),
        server_default="basic_info",
        existing_nullable=False,
    )
    op.drop_index("ix_student_learning_contexts_status", table_name="student_learning_contexts")
    op.drop_index("ix_student_learning_contexts_course_id", table_name="student_learning_contexts")
    op.drop_index("ix_student_learning_contexts_student_id", table_name="student_learning_contexts")
    op.drop_index("ix_student_learning_contexts_id", table_name="student_learning_contexts")
    op.drop_table("student_learning_contexts")
    op.drop_index("ix_student_domain_competencies_student_id", table_name="student_domain_competencies")
    op.drop_index("ix_student_domain_competencies_id", table_name="student_domain_competencies")
    op.drop_table("student_domain_competencies")
    op.drop_index("ix_student_learning_profiles_student_id", table_name="student_learning_profiles")
    op.drop_index("ix_student_learning_profiles_id", table_name="student_learning_profiles")
    op.drop_table("student_learning_profiles")
