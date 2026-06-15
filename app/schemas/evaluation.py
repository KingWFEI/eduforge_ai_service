from typing import Any, List, Optional

from pydantic import BaseModel, Field


class EvaluationReportResponse(BaseModel):
    range: str
    course_id: Optional[str] = None
    course_name: Optional[str] = None
    generated_at: Optional[str] = None
    completion_rate: float = 0
    accuracy_rate: float = 0
    study_hours: float = 0
    overview: dict[str, Any] = Field(default_factory=dict)
    learning_path: dict[str, Any] = Field(default_factory=dict)
    exercise_summary: dict[str, Any] = Field(default_factory=dict)
    mastery_distribution: dict[str, Any] = Field(default_factory=dict)
    recent_submissions: List[dict[str, Any]] = Field(default_factory=list)
    daily_activity: List[dict[str, Any]] = Field(default_factory=list)
    unfinished_tasks: List[dict[str, Any]] = Field(default_factory=list)
    mastery: List[dict[str, Any]] = Field(default_factory=list)
    good_points: List[dict[str, Any]] = Field(default_factory=list)
    weak_points: List[dict[str, Any]] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    next_suggestion: Optional[str] = None


class WeakPointItem(BaseModel):
    knowledge_point: str
    course_id: Optional[str] = None
    mastery_score: Optional[float] = None
    wrong_count: int = 0
    reason: Optional[str] = None
    suggested_action: Optional[str] = None
    source: Optional[str] = None
    updated_at: Optional[str] = None


class WeakPointListResponse(BaseModel):
    items: List[WeakPointItem] = Field(default_factory=list)
    total: int


class MasteryItem(BaseModel):
    knowledge_point: str
    score: float


class MasteryResponse(BaseModel):
    course: Optional[str] = None
    course_id: Optional[str] = None
    items: List[MasteryItem] = Field(default_factory=list)
