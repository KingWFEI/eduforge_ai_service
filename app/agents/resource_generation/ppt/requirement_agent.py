from __future__ import annotations

from app.agents.resource_generation.ppt.schemas import PptRequirement
from app.core.config import settings


class PptRequirementAgent:
    def build(self, state: dict) -> PptRequirement:
        profile = state.get("student_profile") or state.get("profile") or {}
        plan = state.get("resource_plan") or {}
        strategy = plan.get("generation_strategy") if isinstance(plan, dict) else {}
        preferences = profile.get("learning_preferences_json") or profile.get("preferred_learning_styles") or []
        if isinstance(preferences, dict):
            preferences = list(preferences.values())
        focus = [
            str(item.get("name") or item.get("title"))
            for item in (state.get("target_knowledge_points") or [])
            if isinstance(item, dict) and (item.get("name") or item.get("title"))
        ]
        slide_count = int((strategy or {}).get("slide_count") or settings.PPT_DEFAULT_SLIDE_COUNT)
        slide_count = min(max(slide_count, 3), settings.PPT_MAX_SLIDE_COUNT)
        preference_text = " ".join(map(str, preferences)).lower()
        return PptRequirement(
            purpose=state.get("user_request") or state.get("goal") or "个性化课程复习",
            audience="当前学生",
            scope=str(state.get("generation_scope") or "section"),
            difficulty=str(profile.get("course_level") or state.get("difficulty") or "基础"),
            slide_count=slide_count,
            density_mode=(strategy or {}).get("density_mode") or settings.PPT_DEFAULT_DENSITY_MODE,
            focus_knowledge_points=focus,
            needs_visuals="visual" in preference_text or "图" in preference_text or not preferences,
            needs_code="code" in preference_text or "代码" in preference_text,
            needs_examples=True,
        )
