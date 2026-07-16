from typing import Any

from pydantic import BaseModel, Field


class DashboardSummaryResponse(BaseModel):
    student_count: int = 0
    course_count: int = 0
    document_count: int = 0
    knowledge_chunk_count: int = 0
    generated_resource_count: int = 0
    today_generation_count: int = 0
    today_generated_count: int = 0
    average_accuracy: float = 0
    learning_path_completion_rate: float = 0
    agent_task_success_rate: float = 0


class ResourceStatsResponse(BaseModel):
    type_distribution: list[dict[str, Any]] = Field(default_factory=list)
    daily_trend: list[dict[str, Any]] = Field(default_factory=list)


class LearningStatsResponse(BaseModel):
    completion_rate: float = 0
    average_accuracy: float = 0
    weak_point_rank: list[dict[str, Any]] = Field(default_factory=list)
    course_progress: list[dict[str, Any]] = Field(default_factory=list)


class AgentStatsResponse(BaseModel):
    total_tasks: int = 0
    success_rate: float = 0
    average_duration_seconds: float = 0
    status_distribution: list[dict[str, Any]] = Field(default_factory=list)
    agent_duration_rank: list[dict[str, Any]] = Field(default_factory=list)
