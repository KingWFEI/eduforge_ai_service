from __future__ import annotations

from app.agents.resource_generation.planner.schemas import (
    PersonalizationPlan,
    ResourcePlan,
    RetrievalPlan,
    TargetKnowledgePoint,
)
from app.constants.resource_generation import ResourceType
from app.core.config import settings


class ResourcePlanner:
    """Strict, deterministic baseline planner; any future LLM output must validate through ResourcePlan."""

    def plan(self, state: dict) -> ResourcePlan:
        resource_type = ResourceType(str(state["requested_resource_type"]))
        profile = state.get("student_profile") or {}
        preferences = profile.get("learning_preferences_json") or []
        if isinstance(preferences, dict):
            preferences = [str(value) for value in preferences.values()]
        weaknesses = profile.get("weaknesses_json") or []
        if isinstance(weaknesses, dict):
            weaknesses = [str(value) for value in weaknesses.values()]
        targets = [
            TargetKnowledgePoint(
                knowledge_point_id=str(point["id"]),
                name=str(point.get("name") or point.get("title") or point["id"]),
            )
            for point in (state.get("target_knowledge_points") or [])
            if point.get("id")
        ]
        requires_external = resource_type == ResourceType.VIDEO
        strategy: dict = {"density_mode": settings.PPT_DEFAULT_DENSITY_MODE}
        output_files: list[str] = []
        if resource_type == ResourceType.PPT:
            strategy.update(
                slide_count=settings.PPT_DEFAULT_SLIDE_COUNT,
                style_preference=settings.PPT_DEFAULT_STYLE,
            )
            output_files = ["index.html", "cover.png"]
        return ResourcePlan(
            resource_type=resource_type,
            generation_scope=str(state.get("generation_scope") or "section"),
            goal=str(state.get("user_request") or state.get("goal") or "巩固当前课程知识"),
            target_knowledge_points=targets,
            personalization=PersonalizationPlan(
                knowledge_level=str(profile.get("course_level") or "beginner"),
                preferred_learning_styles=[str(item) for item in preferences],
                difficulty=str(state.get("difficulty") or "easy_to_medium"),
                common_weaknesses=[str(item) for item in weaknesses],
            ),
            retrieval_plan=RetrievalPlan(
                requires_course_structure=resource_type in {ResourceType.PPT, ResourceType.MIND_MAP},
                requires_external_search=requires_external,
            ),
            generation_strategy=strategy,
            review_criteria=[
                "内容必须来自课程资料或已验证的 Provider 候选",
                "难度适合当前学生",
                "保留来源并通过类型安全检查",
            ],
            output_files=output_files,
        )
