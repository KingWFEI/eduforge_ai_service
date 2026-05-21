from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class ExerciseSet(Base):
    """练习集合表"""
    __tablename__ = "exercise_sets"

    id = Column(String(64), primary_key=True, index=True)
    resource_id = Column(String(64), nullable=True, index=True)
    course_id = Column(String(64), ForeignKey("courses.course_id"), index=True, nullable=False)
    knowledge_point_id = Column(String(64), nullable=True)
    title = Column(String(255), nullable=False)
    difficulty = Column(String(30), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ExerciseQuestion(Base):
    """练习题表"""
    __tablename__ = "exercise_questions"

    id = Column(String(64), primary_key=True, index=True)
    exercise_set_id = Column(String(64), ForeignKey("exercise_sets.id"), index=True, nullable=False)
    type = Column(String(30), nullable=False)
    question = Column(Text, nullable=False)
    options_json = Column(JSON, nullable=True)
    correct_answer_json = Column(JSON, nullable=True)
    explanation = Column(Text, nullable=True)
    related_knowledge = Column(String(100), nullable=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ExerciseSubmission(Base):
    """练习提交表"""
    __tablename__ = "exercise_submissions"

    id = Column(String(64), primary_key=True, index=True)
    exercise_set_id = Column(String(64), ForeignKey("exercise_sets.id"), index=True, nullable=False)
    resource_id = Column(String(64), nullable=True)
    student_id = Column(String(64), index=True, nullable=False)
    score = Column(Float, nullable=True)
    accuracy = Column(Float, nullable=True)
    correct_count = Column(Integer, nullable=True)
    total_count = Column(Integer, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    weak_points_json = Column(JSON, nullable=True)
    analysis_json = Column(JSON, nullable=True)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())


class ExerciseAnswer(Base):
    """学生答题明细表"""
    __tablename__ = "exercise_answers"

    id = Column(String(64), primary_key=True, index=True)
    submission_id = Column(String(64), ForeignKey("exercise_submissions.id"), index=True, nullable=False)
    question_id = Column(String(64), ForeignKey("exercise_questions.id"), index=True, nullable=False)
    student_answer_json = Column(JSON, nullable=True)
    is_correct = Column(Integer, nullable=True)
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WrongQuestion(Base):
    """错题表"""
    __tablename__ = "wrong_questions"

    id = Column(String(64), primary_key=True, index=True)
    student_id = Column(String(64), index=True, nullable=False)
    question_id = Column(String(64), ForeignKey("exercise_questions.id"), index=True, nullable=False)
    knowledge_point = Column(String(100), nullable=True)
    wrong_count = Column(Integer, default=1)
    last_wrong_at = Column(DateTime(timezone=True), nullable=False)
    mastered = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
