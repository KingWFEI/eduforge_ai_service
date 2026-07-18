from __future__ import annotations

from typing import Any, TypedDict


class ResourceGenerationState(TypedDict, total=False):
    task_id: str
    agent_task_id: str
    student_id: str
    course_id: str
    chapter_id: str | None
    section_id: str | None
    knowledge_point_ids: list[str]
    requested_resource_type: str
    requested_resource_types: list[str]
    generation_scope: str
    user_request: str
    difficulty: str
    goal: str
    student_profile: dict[str, Any]
    learning_state: dict[str, Any]
    course_structure: dict[str, Any]
    current_chapter_context: dict[str, Any]
    current_section_context: dict[str, Any]
    current_chapter_knowledge_points: list[dict[str, Any]]
    cross_chapter_context: list[dict[str, Any]]
    target_knowledge_points: list[dict[str, Any]]
    retrieval_plan: dict[str, Any]
    retrieved_chunks: list[dict[str, Any]]
    source_references: list[dict[str, Any]]
    resource_plan: dict[str, Any]
    resource_plans: dict[str, dict[str, Any]]
    external_candidates: list[dict[str, Any]]
    draft_resource: dict[str, Any]
    generated_resources: list[dict[str, Any]]
    final_resource: dict[str, Any]
    final_resources: list[dict[str, Any]]
    generation_artifacts: dict[str, Any]
    review_result: dict[str, Any]
    review_results: list[dict[str, Any]]
    quality_metrics: dict[str, Any]
    current_step: str
    progress: int
    status: str
    errors: list[dict[str, Any]]
    retry_count: int
    needs_retry: bool
    resource_ids: list[str]
