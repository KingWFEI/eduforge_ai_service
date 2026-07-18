from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.constants.resource_generation import GenerationScope, ResourceType


class TargetKnowledgePoint(BaseModel):
    knowledge_point_id: str
    name: str


class PersonalizationPlan(BaseModel):
    knowledge_level: str = "beginner"
    preferred_learning_styles: list[str] = Field(default_factory=list)
    difficulty: str = "easy_to_medium"
    common_weaknesses: list[str] = Field(default_factory=list)


class RetrievalPlan(BaseModel):
    current_section_top_k: int = Field(default=8, ge=0, le=30)
    current_chapter_top_k: int = Field(default=6, ge=0, le=30)
    cross_chapter_top_k: int = Field(default=5, ge=0, le=30)
    requires_course_structure: bool = True
    requires_external_search: bool = False


class ResourcePlan(BaseModel):
    resource_type: ResourceType
    generation_scope: GenerationScope
    goal: str
    target_knowledge_points: list[TargetKnowledgePoint] = Field(default_factory=list)
    personalization: PersonalizationPlan
    retrieval_plan: RetrievalPlan
    generation_strategy: dict[str, Any] = Field(default_factory=dict)
    review_criteria: list[str] = Field(default_factory=list)
    output_files: list[str] = Field(default_factory=list)
