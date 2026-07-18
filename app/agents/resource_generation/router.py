from __future__ import annotations

import asyncio
import uuid

from app.agents.resource_generation.mind_map.service import CourseRelationMindMapService
from app.agents.resource_generation.ppt.service import PptGenerationService
from app.agents.resource_generation.video.service import ExternalVideoGenerationService


class ResourceGeneratorRouter:
    def __init__(self, video_service: ExternalVideoGenerationService | None = None):
        self.ppt = PptGenerationService()
        self.video = video_service or ExternalVideoGenerationService()
        self.mind_map = CourseRelationMindMapService()

    def generate(self, resource_type: str, state: dict) -> dict:
        local_state = dict(state)
        local_state["requested_resource_type"] = resource_type
        local_state["resource_id"] = "res_" + uuid.uuid4().hex[:20]
        plan = (state.get("resource_plans") or {}).get(resource_type) or state.get("resource_plan") or {}
        local_state["resource_plan"] = plan
        if resource_type == "ppt":
            resource = self.ppt.generate(local_state)
        elif resource_type == "video":
            resource = asyncio.run(self.video.generate(local_state))
        elif resource_type == "mind_map":
            resource = self.mind_map.generate(local_state)
        else:
            resource = self._generate_with_legacy_agent(resource_type, local_state)
        resource["resource_id"] = local_state["resource_id"]
        return self._normalize(resource, local_state)

    @staticmethod
    def _generate_with_legacy_agent(resource_type: str, state: dict) -> dict:
        from app.agents.code_agent import CodeAgent
        from app.agents.doc_agent import DocAgent
        from app.agents.exercise_agent import ExerciseAgent
        from app.agents.illustration_agent import IllustrationAgent
        from app.services.llm_service import DeepSeekService

        agent_classes = {
            "illustration": IllustrationAgent,
            "document": DocAgent,
            "exercise": ExerciseAgent,
            "code_case": CodeAgent,
        }
        try:
            agent = agent_classes[resource_type](DeepSeekService())
        except KeyError as exc:
            raise ValueError(f"不支持的资源类型：{resource_type}") from exc
        legacy_state = {
            **state,
            "profile": state.get("student_profile") or {},
            "knowledge_chunks": state.get("retrieved_chunks") or [],
            "resource_types": [resource_type],
            "generated_resources": [],
        }
        result = asyncio.run(agent.run(legacy_state))
        if resource_type == "illustration" and result.get("resource"):
            return result["resource"]
        resources = result.get("generated_resources") or []
        if not resources:
            raise RuntimeError(f"{resource_type} 生成器未返回资源")
        return resources[-1]

    @staticmethod
    def _normalize(resource: dict, state: dict) -> dict:
        if resource.get("status") == "no_suitable_result":
            return resource
        content = resource.get("content_json")
        if not isinstance(content, dict):
            content = {"value": content}
        overview = str(content.get("overview") or resource.get("overview") or resource.get("description") or resource.get("title") or "学习资源")
        content["overview"] = overview
        content.setdefault("key_takeaways", [])
        content.setdefault("visualization", None)
        resource["content_json"] = content
        resource.setdefault("overview", overview)
        resource.setdefault("source_type", "generated")
        resource.setdefault("generation_mode", "ai_generated")
        resource.setdefault("status", "completed")
        resource.setdefault("source_references", state.get("source_references") or [])
        return resource
