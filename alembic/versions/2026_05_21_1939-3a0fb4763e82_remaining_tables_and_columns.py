"""remaining_tables_and_columns

Revision ID: 3a0fb4763e82
Revises: 62ceb21df093
Create Date: 2026-05-21 19:39:44.333020

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '3a0fb4763e82'
down_revision: Union[str, Sequence[str], None] = '62ceb21df093'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ── 已有表新增字段（安全的 add_column + drop_column 操作） ──
    op.add_column('onboarding_options', sa.Column('profile_mapping_json', sa.JSON(), nullable=True))
    op.drop_column('onboarding_options', 'profile_mapping')
    op.add_column('onboarding_questions', sa.Column('config_json', sa.JSON(), nullable=True))
    op.drop_column('onboarding_questions', 'matrix_items')
    op.add_column('onboarding_submissions', sa.Column('status', sa.String(length=30), nullable=True))
    op.alter_column('onboarding_submissions', 'answers_json',
               existing_type=mysql.JSON(),
               nullable=True)
    op.create_index(op.f('ix_onboarding_submissions_status'), 'onboarding_submissions', ['status'], unique=False)
    op.create_index(op.f('ix_profile_analyses_status'), 'profile_analyses', ['status'], unique=False)
    op.add_column('student_profiles', sa.Column('target_course_id', sa.String(length=64), nullable=True))
    op.drop_index(op.f('ix_student_profiles_student_id'), table_name='student_profiles')
    op.create_index(op.f('ix_student_profiles_student_id'), 'student_profiles', ['student_id'], unique=True)
    op.add_column('users', sa.Column('status', sa.String(length=30), nullable=True))
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True))
    op.create_index(op.f('ix_users_role'), 'users', ['role'], unique=False)
    op.create_index(op.f('ix_users_status'), 'users', ['status'], unique=False)
    op.add_column('verification_codes', sa.Column('scene', sa.String(length=30), nullable=True))
    op.add_column('verification_codes', sa.Column('used_at', sa.DateTime(timezone=True), nullable=True))
    op.alter_column('verification_codes', 'code',
               existing_type=mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=6),
               type_=sa.String(length=10),
               existing_nullable=False)
    op.execute("UPDATE users SET status = 'normal' WHERE status IS NULL")

    # ── 新建表（courses.course_id 已在第1次迁移中添加） ──
    op.create_table('course_chapters',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('course_id', sa.String(length=64), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('sort_order', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['course_id'], ['courses.course_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_course_chapters_course_id'), 'course_chapters', ['course_id'], unique=False)
    op.create_index(op.f('ix_course_chapters_id'), 'course_chapters', ['id'], unique=False)
    op.create_table('exercise_sets',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('resource_id', sa.String(length=64), nullable=True),
    sa.Column('course_id', sa.String(length=64), nullable=False),
    sa.Column('knowledge_point_id', sa.String(length=64), nullable=True),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('difficulty', sa.String(length=30), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['course_id'], ['courses.course_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_exercise_sets_course_id'), 'exercise_sets', ['course_id'], unique=False)
    op.create_index(op.f('ix_exercise_sets_id'), 'exercise_sets', ['id'], unique=False)
    op.create_index(op.f('ix_exercise_sets_resource_id'), 'exercise_sets', ['resource_id'], unique=False)
    op.create_table('learning_paths',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('student_id', sa.String(length=64), nullable=False),
    sa.Column('course_id', sa.String(length=64), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('goal', sa.Text(), nullable=True),
    sa.Column('duration_days', sa.Integer(), nullable=True),
    sa.Column('daily_minutes', sa.Integer(), nullable=True),
    sa.Column('progress', sa.Float(), nullable=True),
    sa.Column('status', sa.String(length=30), nullable=True),
    sa.Column('plan_json', sa.JSON(), nullable=True),
    sa.Column('created_by_task_id', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['course_id'], ['courses.course_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_learning_paths_course_id'), 'learning_paths', ['course_id'], unique=False)
    op.create_index(op.f('ix_learning_paths_id'), 'learning_paths', ['id'], unique=False)
    op.create_index(op.f('ix_learning_paths_status'), 'learning_paths', ['status'], unique=False)
    op.create_index(op.f('ix_learning_paths_student_id'), 'learning_paths', ['student_id'], unique=False)
    op.create_table('mastery_records',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('student_id', sa.String(length=64), nullable=False),
    sa.Column('course_id', sa.String(length=64), nullable=False),
    sa.Column('knowledge_point_id', sa.String(length=64), nullable=True),
    sa.Column('knowledge_point', sa.String(length=100), nullable=False),
    sa.Column('score', sa.Float(), nullable=False),
    sa.Column('source', sa.String(length=50), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['course_id'], ['courses.course_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_mastery_records_course_id'), 'mastery_records', ['course_id'], unique=False)
    op.create_index(op.f('ix_mastery_records_id'), 'mastery_records', ['id'], unique=False)
    op.create_index(op.f('ix_mastery_records_student_id'), 'mastery_records', ['student_id'], unique=False)
    op.create_table('onboarding_answers',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('submission_id', sa.String(length=64), nullable=False),
    sa.Column('question_id', sa.String(length=64), nullable=False),
    sa.Column('answer_json', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['question_id'], ['onboarding_questions.question_id'], ),
    sa.ForeignKeyConstraint(['submission_id'], ['onboarding_submissions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_onboarding_answers_id'), 'onboarding_answers', ['id'], unique=False)
    op.create_index(op.f('ix_onboarding_answers_question_id'), 'onboarding_answers', ['question_id'], unique=False)
    op.create_index(op.f('ix_onboarding_answers_submission_id'), 'onboarding_answers', ['submission_id'], unique=False)
    op.create_table('resource_generation_tasks',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('student_id', sa.String(length=64), nullable=False),
    sa.Column('course_id', sa.String(length=64), nullable=False),
    sa.Column('knowledge_point', sa.String(length=100), nullable=True),
    sa.Column('goal', sa.Text(), nullable=True),
    sa.Column('resource_types_json', sa.JSON(), nullable=False),
    sa.Column('difficulty', sa.String(length=30), nullable=True),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('progress', sa.Integer(), nullable=True),
    sa.Column('current_step', sa.String(length=200), nullable=True),
    sa.Column('result_resource_ids_json', sa.JSON(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['course_id'], ['courses.course_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_resource_generation_tasks_course_id'), 'resource_generation_tasks', ['course_id'], unique=False)
    op.create_index(op.f('ix_resource_generation_tasks_id'), 'resource_generation_tasks', ['id'], unique=False)
    op.create_index(op.f('ix_resource_generation_tasks_status'), 'resource_generation_tasks', ['status'], unique=False)
    op.create_index(op.f('ix_resource_generation_tasks_student_id'), 'resource_generation_tasks', ['student_id'], unique=False)
    op.create_table('course_documents',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('course_id', sa.String(length=64), nullable=False),
    sa.Column('chapter_id', sa.String(length=64), nullable=True),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('file_path', sa.String(length=500), nullable=False),
    sa.Column('file_type', sa.String(length=50), nullable=True),
    sa.Column('file_size', sa.Integer(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('parse_status', sa.String(length=30), nullable=True),
    sa.Column('index_status', sa.String(length=30), nullable=True),
    sa.Column('chunk_count', sa.Integer(), nullable=True),
    sa.Column('uploaded_by', sa.String(length=64), nullable=True),
    sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['chapter_id'], ['course_chapters.id'], ),
    sa.ForeignKeyConstraint(['course_id'], ['courses.course_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_course_documents_chapter_id'), 'course_documents', ['chapter_id'], unique=False)
    op.create_index(op.f('ix_course_documents_course_id'), 'course_documents', ['course_id'], unique=False)
    op.create_index(op.f('ix_course_documents_id'), 'course_documents', ['id'], unique=False)
    op.create_index(op.f('ix_course_documents_index_status'), 'course_documents', ['index_status'], unique=False)
    op.create_index(op.f('ix_course_documents_parse_status'), 'course_documents', ['parse_status'], unique=False)
    op.create_table('exercise_questions',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('exercise_set_id', sa.String(length=64), nullable=False),
    sa.Column('type', sa.String(length=30), nullable=False),
    sa.Column('question', sa.Text(), nullable=False),
    sa.Column('options_json', sa.JSON(), nullable=True),
    sa.Column('correct_answer_json', sa.JSON(), nullable=True),
    sa.Column('explanation', sa.Text(), nullable=True),
    sa.Column('related_knowledge', sa.String(length=100), nullable=True),
    sa.Column('sort_order', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['exercise_set_id'], ['exercise_sets.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_exercise_questions_exercise_set_id'), 'exercise_questions', ['exercise_set_id'], unique=False)
    op.create_index(op.f('ix_exercise_questions_id'), 'exercise_questions', ['id'], unique=False)
    op.create_table('exercise_submissions',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('exercise_set_id', sa.String(length=64), nullable=False),
    sa.Column('resource_id', sa.String(length=64), nullable=True),
    sa.Column('student_id', sa.String(length=64), nullable=False),
    sa.Column('score', sa.Float(), nullable=True),
    sa.Column('accuracy', sa.Float(), nullable=True),
    sa.Column('correct_count', sa.Integer(), nullable=True),
    sa.Column('total_count', sa.Integer(), nullable=True),
    sa.Column('duration_seconds', sa.Integer(), nullable=True),
    sa.Column('weak_points_json', sa.JSON(), nullable=True),
    sa.Column('analysis_json', sa.JSON(), nullable=True),
    sa.Column('submitted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['exercise_set_id'], ['exercise_sets.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_exercise_submissions_exercise_set_id'), 'exercise_submissions', ['exercise_set_id'], unique=False)
    op.create_index(op.f('ix_exercise_submissions_id'), 'exercise_submissions', ['id'], unique=False)
    op.create_index(op.f('ix_exercise_submissions_student_id'), 'exercise_submissions', ['student_id'], unique=False)
    op.create_table('knowledge_points',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('course_id', sa.String(length=64), nullable=False),
    sa.Column('chapter_id', sa.String(length=64), nullable=True),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('difficulty', sa.String(length=30), nullable=True),
    sa.Column('prerequisites_json', sa.JSON(), nullable=True),
    sa.Column('sort_order', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['chapter_id'], ['course_chapters.id'], ),
    sa.ForeignKeyConstraint(['course_id'], ['courses.course_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_knowledge_points_chapter_id'), 'knowledge_points', ['chapter_id'], unique=False)
    op.create_index(op.f('ix_knowledge_points_course_id'), 'knowledge_points', ['course_id'], unique=False)
    op.create_index(op.f('ix_knowledge_points_id'), 'knowledge_points', ['id'], unique=False)
    op.create_table('learning_path_tasks',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('path_id', sa.String(length=64), nullable=False),
    sa.Column('day_no', sa.Integer(), nullable=False),
    sa.Column('topic', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('estimated_minutes', sa.Integer(), nullable=True),
    sa.Column('resource_ids_json', sa.JSON(), nullable=True),
    sa.Column('status', sa.String(length=30), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['path_id'], ['learning_paths.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_learning_path_tasks_id'), 'learning_path_tasks', ['id'], unique=False)
    op.create_index(op.f('ix_learning_path_tasks_path_id'), 'learning_path_tasks', ['path_id'], unique=False)
    op.create_index(op.f('ix_learning_path_tasks_status'), 'learning_path_tasks', ['status'], unique=False)
    op.create_table('exercise_answers',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('submission_id', sa.String(length=64), nullable=False),
    sa.Column('question_id', sa.String(length=64), nullable=False),
    sa.Column('student_answer_json', sa.JSON(), nullable=True),
    sa.Column('is_correct', sa.Integer(), nullable=True),
    sa.Column('explanation', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['question_id'], ['exercise_questions.id'], ),
    sa.ForeignKeyConstraint(['submission_id'], ['exercise_submissions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_exercise_answers_id'), 'exercise_answers', ['id'], unique=False)
    op.create_index(op.f('ix_exercise_answers_question_id'), 'exercise_answers', ['question_id'], unique=False)
    op.create_index(op.f('ix_exercise_answers_submission_id'), 'exercise_answers', ['submission_id'], unique=False)
    op.create_table('knowledge_chunks',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('course_id', sa.String(length=64), nullable=False),
    sa.Column('document_id', sa.String(length=64), nullable=False),
    sa.Column('chapter_id', sa.String(length=64), nullable=True),
    sa.Column('knowledge_point_id', sa.String(length=64), nullable=True),
    sa.Column('section', sa.String(length=200), nullable=True),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('keywords_json', sa.JSON(), nullable=True),
    sa.Column('page_no', sa.Integer(), nullable=True),
    sa.Column('chunk_index', sa.Integer(), nullable=False),
    sa.Column('vector_id', sa.String(length=100), nullable=True),
    sa.Column('indexed', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['chapter_id'], ['course_chapters.id'], ),
    sa.ForeignKeyConstraint(['course_id'], ['courses.course_id'], ),
    sa.ForeignKeyConstraint(['document_id'], ['course_documents.id'], ),
    sa.ForeignKeyConstraint(['knowledge_point_id'], ['knowledge_points.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_knowledge_chunks_chapter_id'), 'knowledge_chunks', ['chapter_id'], unique=False)
    op.create_index(op.f('ix_knowledge_chunks_course_id'), 'knowledge_chunks', ['course_id'], unique=False)
    op.create_index(op.f('ix_knowledge_chunks_document_id'), 'knowledge_chunks', ['document_id'], unique=False)
    op.create_index(op.f('ix_knowledge_chunks_id'), 'knowledge_chunks', ['id'], unique=False)
    op.create_index(op.f('ix_knowledge_chunks_knowledge_point_id'), 'knowledge_chunks', ['knowledge_point_id'], unique=False)
    op.create_table('learning_resources',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('student_id', sa.String(length=64), nullable=True),
    sa.Column('course_id', sa.String(length=64), nullable=False),
    sa.Column('knowledge_point_id', sa.String(length=64), nullable=True),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('type', sa.String(length=50), nullable=False),
    sa.Column('difficulty', sa.String(length=30), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('content_text', sa.Text(), nullable=True),
    sa.Column('content_json', sa.JSON(), nullable=True),
    sa.Column('source', sa.String(length=255), nullable=True),
    sa.Column('review_status', sa.String(length=30), nullable=True),
    sa.Column('safety_score', sa.Float(), nullable=True),
    sa.Column('hallucination_risk', sa.String(length=30), nullable=True),
    sa.Column('generated_by_task_id', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['course_id'], ['courses.course_id'], ),
    sa.ForeignKeyConstraint(['knowledge_point_id'], ['knowledge_points.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_learning_resources_course_id'), 'learning_resources', ['course_id'], unique=False)
    op.create_index(op.f('ix_learning_resources_id'), 'learning_resources', ['id'], unique=False)
    op.create_index(op.f('ix_learning_resources_knowledge_point_id'), 'learning_resources', ['knowledge_point_id'], unique=False)
    op.create_index(op.f('ix_learning_resources_review_status'), 'learning_resources', ['review_status'], unique=False)
    op.create_index(op.f('ix_learning_resources_student_id'), 'learning_resources', ['student_id'], unique=False)
    op.create_index(op.f('ix_learning_resources_type'), 'learning_resources', ['type'], unique=False)
    op.create_table('vector_index_records',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('course_id', sa.String(length=64), nullable=False),
    sa.Column('document_id', sa.String(length=64), nullable=True),
    sa.Column('vector_store', sa.String(length=50), nullable=False),
    sa.Column('collection_name', sa.String(length=100), nullable=False),
    sa.Column('chunk_count', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['course_id'], ['courses.course_id'], ),
    sa.ForeignKeyConstraint(['document_id'], ['course_documents.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_vector_index_records_course_id'), 'vector_index_records', ['course_id'], unique=False)
    op.create_index(op.f('ix_vector_index_records_document_id'), 'vector_index_records', ['document_id'], unique=False)
    op.create_index(op.f('ix_vector_index_records_id'), 'vector_index_records', ['id'], unique=False)
    op.create_index(op.f('ix_vector_index_records_status'), 'vector_index_records', ['status'], unique=False)
    op.create_table('wrong_questions',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('student_id', sa.String(length=64), nullable=False),
    sa.Column('question_id', sa.String(length=64), nullable=False),
    sa.Column('knowledge_point', sa.String(length=100), nullable=True),
    sa.Column('wrong_count', sa.Integer(), nullable=True),
    sa.Column('last_wrong_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('mastered', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['question_id'], ['exercise_questions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_wrong_questions_id'), 'wrong_questions', ['id'], unique=False)
    op.create_index(op.f('ix_wrong_questions_question_id'), 'wrong_questions', ['question_id'], unique=False)
    op.create_index(op.f('ix_wrong_questions_student_id'), 'wrong_questions', ['student_id'], unique=False)
    op.create_table('chat_message_sources',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('message_id', sa.String(length=64), nullable=False),
    sa.Column('chunk_id', sa.String(length=64), nullable=False),
    sa.Column('source_title', sa.String(length=255), nullable=True),
    sa.Column('source_page', sa.Integer(), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['chunk_id'], ['knowledge_chunks.id'], ),
    sa.ForeignKeyConstraint(['message_id'], ['chat_messages.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_message_sources_chunk_id'), 'chat_message_sources', ['chunk_id'], unique=False)
    op.create_index(op.f('ix_chat_message_sources_id'), 'chat_message_sources', ['id'], unique=False)
    op.create_index(op.f('ix_chat_message_sources_message_id'), 'chat_message_sources', ['message_id'], unique=False)
    op.create_table('resource_favorites',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('resource_id', sa.String(length=64), nullable=False),
    sa.Column('student_id', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['resource_id'], ['learning_resources.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_resource_favorites_id'), 'resource_favorites', ['id'], unique=False)
    op.create_index(op.f('ix_resource_favorites_resource_id'), 'resource_favorites', ['resource_id'], unique=False)
    op.create_index(op.f('ix_resource_favorites_student_id'), 'resource_favorites', ['student_id'], unique=False)
    op.create_table('resource_feedback',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('resource_id', sa.String(length=64), nullable=False),
    sa.Column('student_id', sa.String(length=64), nullable=False),
    sa.Column('liked', sa.Integer(), nullable=True),
    sa.Column('favorite', sa.Integer(), nullable=True),
    sa.Column('difficulty_feedback', sa.String(length=30), nullable=True),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['resource_id'], ['learning_resources.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_resource_feedback_id'), 'resource_feedback', ['id'], unique=False)
    op.create_index(op.f('ix_resource_feedback_resource_id'), 'resource_feedback', ['resource_id'], unique=False)
    op.create_index(op.f('ix_resource_feedback_student_id'), 'resource_feedback', ['student_id'], unique=False)
    op.create_table('resource_references',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('resource_id', sa.String(length=64), nullable=False),
    sa.Column('chunk_id', sa.String(length=64), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['chunk_id'], ['knowledge_chunks.id'], ),
    sa.ForeignKeyConstraint(['resource_id'], ['learning_resources.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_resource_references_chunk_id'), 'resource_references', ['chunk_id'], unique=False)
    op.create_index(op.f('ix_resource_references_id'), 'resource_references', ['id'], unique=False)
    op.create_index(op.f('ix_resource_references_resource_id'), 'resource_references', ['resource_id'], unique=False)
    op.create_table('resource_reviews',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('resource_id', sa.String(length=64), nullable=False),
    sa.Column('reviewer_id', sa.String(length=64), nullable=False),
    sa.Column('action', sa.String(length=30), nullable=False),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['resource_id'], ['learning_resources.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_resource_reviews_id'), 'resource_reviews', ['id'], unique=False)
    op.create_index(op.f('ix_resource_reviews_resource_id'), 'resource_reviews', ['resource_id'], unique=False)
    op.create_index(op.f('ix_resource_reviews_reviewer_id'), 'resource_reviews', ['reviewer_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # ── 删除新建表（反向顺序避免 FK 约束） ──
    op.drop_table('resource_reviews')
    op.drop_table('resource_references')
    op.drop_table('resource_feedback')
    op.drop_table('resource_favorites')
    op.drop_table('chat_message_sources')
    op.drop_table('wrong_questions')
    op.drop_table('vector_index_records')
    op.drop_table('learning_resources')
    op.drop_table('knowledge_chunks')
    op.drop_table('exercise_answers')
    op.drop_table('learning_path_tasks')
    op.drop_table('knowledge_points')
    op.drop_table('exercise_submissions')
    op.drop_table('exercise_questions')
    op.drop_table('course_documents')
    op.drop_table('resource_generation_tasks')
    op.drop_table('onboarding_answers')
    op.drop_table('mastery_records')
    op.drop_table('learning_paths')
    op.drop_table('exercise_sets')
    op.drop_table('course_chapters')

    # ── 回滚已有表变更 ──
    op.alter_column('verification_codes', 'code',
               existing_type=sa.String(length=10),
               type_=mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=6),
               existing_nullable=False)
    op.drop_column('verification_codes', 'used_at')
    op.drop_column('verification_codes', 'scene')
    op.drop_index(op.f('ix_users_status'), table_name='users')
    op.drop_index(op.f('ix_users_role'), table_name='users')
    op.drop_column('users', 'updated_at')
    op.drop_column('users', 'last_login_at')
    op.drop_column('users', 'status')
    op.drop_index(op.f('ix_student_profiles_student_id'), table_name='student_profiles')
    op.create_index(op.f('ix_student_profiles_student_id'), 'student_profiles', ['student_id'], unique=False)
    op.drop_column('student_profiles', 'target_course_id')
    op.drop_index(op.f('ix_profile_analyses_status'), table_name='profile_analyses')
    op.drop_index(op.f('ix_onboarding_submissions_status'), table_name='onboarding_submissions')
    op.alter_column('onboarding_submissions', 'answers_json',
               existing_type=mysql.JSON(),
               nullable=False)
    op.drop_column('onboarding_submissions', 'status')
    op.add_column('onboarding_questions', sa.Column('matrix_items', mysql.JSON(), nullable=True))
    op.drop_column('onboarding_questions', 'config_json')
    op.add_column('onboarding_options', sa.Column('profile_mapping', mysql.JSON(), nullable=True))
    op.drop_column('onboarding_options', 'profile_mapping_json')
