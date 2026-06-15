from typing import Any, Optional

from pydantic import BaseModel, Field


class AdminStudentUserInfo(BaseModel):
    student_id: str
    username: str
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    status: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None
    last_login_at: Optional[str] = None


class AdminStudentProfileInfo(BaseModel):
    profile_id: Optional[str] = None
    learning_preferences: list[Any] = Field(default_factory=list)
    cognitive_traits: list[Any] = Field(default_factory=list)
    learning_habits: list[Any] = Field(default_factory=list)
    motivation_factors: list[Any] = Field(default_factory=list)
    general_strengths: list[Any] = Field(default_factory=list)
    general_challenges: list[Any] = Field(default_factory=list)
    preferred_pace: Optional[str] = None
    available_time: dict[str, Any] = Field(default_factory=dict)
    summary: Optional[str] = None
    profile_dimensions: dict[str, Any] = Field(default_factory=dict)
    evidence: list[Any] = Field(default_factory=list)
    confidence: dict[str, Any] = Field(default_factory=dict)
    version: Optional[int] = None
    source: Optional[str] = None
    last_updated: Optional[str] = None


class AdminStudentLearningData(BaseModel):
    student: AdminStudentUserInfo
    profile: Optional[AdminStudentProfileInfo] = None
    domain_competencies: list[dict[str, Any]] = Field(default_factory=list)
    learning_contexts: list[dict[str, Any]] = Field(default_factory=list)
    weak_points: list[dict[str, Any]] = Field(default_factory=list)
    mastery_records: list[dict[str, Any]] = Field(default_factory=list)
    evaluation_reports: list[dict[str, Any]] = Field(default_factory=list)
    learning_paths: list[dict[str, Any]] = Field(default_factory=list)
    exercise_submissions: list[dict[str, Any]] = Field(default_factory=list)
    wrong_questions: list[dict[str, Any]] = Field(default_factory=list)
    study_records: list[dict[str, Any]] = Field(default_factory=list)
    resources: list[dict[str, Any]] = Field(default_factory=list)
    resource_generation_tasks: list[dict[str, Any]] = Field(default_factory=list)
