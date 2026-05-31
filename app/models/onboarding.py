from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.constants.role import Role
from app.db.base import Base


class OnboardingSurvey(Base):
    """引导问卷主体表"""
    __tablename__ = "onboarding_surveys"

    id = Column(Integer, primary_key=True, index=True)
    survey_id = Column(String(64), unique=True, index=True, nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(Integer, default=1, nullable=False)
    status = Column(String(30), default="draft", index=True, nullable=False)
    target_role = Column(String(30), default=Role.STUDENT.value, index=True, nullable=False)
    target_course_id = Column(String(64), nullable=True)
    submit_count = Column(Integer, default=0, nullable=False)
    created_by = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class OnboardingQuestion(Base):
    """问卷问题表"""
    __tablename__ = "onboarding_questions"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(String(64), unique=True, index=True, nullable=False)
    survey_id = Column(String(64), ForeignKey("onboarding_surveys.survey_id"), index=True, nullable=False)
    step = Column(Integer, nullable=False)
    title = Column(String(300), nullable=False)
    subtitle = Column(String(500), nullable=True)
    type = Column(String(30), nullable=False)
    required = Column(Boolean, default=True, nullable=False)
    config_json = Column(JSON, nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class OnboardingOption(Base):
    """问卷选项表"""
    __tablename__ = "onboarding_options"

    id = Column(Integer, primary_key=True, index=True)
    option_id = Column(String(64), unique=True, index=True, nullable=False)
    question_id = Column(String(64), ForeignKey("onboarding_questions.question_id"), index=True, nullable=False)
    label = Column(String(200), nullable=False)
    value = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    icon = Column(String(100), nullable=True)
    color = Column(String(50), nullable=True)
    profile_mapping_json = Column(JSON, nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class OnboardingSubmission(Base):
    """问卷提交记录"""
    __tablename__ = "onboarding_submissions"

    id = Column(String(64), primary_key=True, index=True)
    survey_id = Column(String(64), index=True, nullable=False)
    student_id = Column(String(64), index=True, nullable=False)
    answers_json = Column(JSON, nullable=True)
    generated_profile_id = Column(String(64), nullable=True)
    status = Column(String(30), default="submitted", index=True)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())


class OnboardingAnswer(Base):
    """问卷答案明细表"""
    __tablename__ = "onboarding_answers"

    id = Column(String(64), primary_key=True, index=True)
    submission_id = Column(String(64), ForeignKey("onboarding_submissions.id"), index=True, nullable=False)
    question_id = Column(String(64), ForeignKey("onboarding_questions.question_id"), index=True, nullable=False)
    answer_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())