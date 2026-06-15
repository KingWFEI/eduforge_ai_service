from typing import Any, Optional

from pydantic import BaseModel, Field


class StudentListItem(BaseModel):
    student_id: str
    name: Optional[str] = None
    major: Optional[str] = None
    grade: Optional[str] = None
    target_course: Optional[str] = None
    completion_rate: float = 0
    accuracy_rate: float = 0
    weak_points: list[str] = Field(default_factory=list)


class StudentListResponse(BaseModel):
    items: list[StudentListItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 10


class StudentProfileResponse(BaseModel):
    student_id: str
    name: Optional[str] = None
    major: Optional[str] = None
    grade: Optional[str] = None
    learning_preferences: list[Any] = Field(default_factory=list)
    weaknesses: list[Any] = Field(default_factory=list)
    mastery: list[dict[str, Any]] = Field(default_factory=list)
    profile: dict[str, Any] = Field(default_factory=dict)


class StudentLearningPathResponse(BaseModel):
    student_id: str
    paths: list[dict[str, Any]] = Field(default_factory=list)


class StudentEvaluationResponse(BaseModel):
    student_id: str
    completion_rate: float = 0
    accuracy_rate: float = 0
    study_hours: float = 0
    weak_points: list[dict[str, Any]] = Field(default_factory=list)
    mastery: list[dict[str, Any]] = Field(default_factory=list)
    reports: list[dict[str, Any]] = Field(default_factory=list)
