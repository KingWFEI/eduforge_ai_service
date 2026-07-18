import json
from typing import Any, Dict

from app.agents.base import BaseAgent
from app.agents.student_learning_content_agent import StudentLearningContentAgent


from app.constants.resource_generation import SUPPORTED_SECTION_RESOURCE_TYPES


ALLOWED_SECTION_RESOURCE_TYPES = {item.value for item in SUPPORTED_SECTION_RESOURCE_TYPES}


class SectionResourceRecommendationAgent(BaseAgent):
    """Select resource shells from section content and the learner profile."""

    name = "Section Resource Recommendation Agent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = await self.llm_service.generate_json(
                prompt=self._build_prompt(input_data),
                max_tokens=1800,
                temperature=0.2,
            )
            resources = self._normalize_resources(result.get("resources"), input_data)
            suggestion = str(result.get("suggestion") or "").strip()
            if resources and suggestion:
                return {"suggestion": suggestion[:200], "resources": resources}
        except Exception:
            pass
        return self.fallback(input_data)

    @staticmethod
    def _normalize_resources(
        raw_resources: Any,
        input_data: Dict[str, Any],
    ) -> list[dict[str, str]]:
        if not isinstance(raw_resources, list):
            return []
        section = input_data.get("section") or {}
        section_id = str(section.get("section_id") or "section")
        section_title = str(section.get("section_title") or "本节内容")
        resources = []
        seen = set()
        for raw in raw_resources:
            if not isinstance(raw, dict):
                continue
            resource_type = str(raw.get("type") or "").strip()
            if resource_type not in ALLOWED_SECTION_RESOURCE_TYPES or resource_type in seen:
                continue
            seen.add(resource_type)
            resources.append(
                {
                    "id": StudentLearningContentAgent.build_resource_shell_id(
                        section_id, resource_type
                    ),
                    "title": str(
                        raw.get("title")
                        or StudentLearningContentAgent.default_resource_title(
                            section_title, resource_type
                        )
                    ),
                    "subtitle": str(
                        raw.get("subtitle")
                        or StudentLearningContentAgent.default_resource_subtitle(resource_type)
                    ),
                    "type": resource_type,
                    "reason": str(raw.get("reason") or "适合当前学习内容和学习画像"),
                }
            )
        return resources[:4]

    @classmethod
    def fallback(cls, input_data: Dict[str, Any]) -> Dict[str, Any]:
        section = input_data.get("section") or {}
        profile = input_data.get("profile") or {}
        progress = input_data.get("progress") or {}
        learning_content = input_data.get("learning_content") or {}
        text = " ".join(
            [
                str(section.get("section_title") or ""),
                str(section.get("section_description") or ""),
                str(learning_content.get("content_markdown") or "")[:6000],
                json.dumps(learning_content.get("content_json") or {}, ensure_ascii=False)[:4000],
            ]
        ).lower()
        preferences = " ".join(str(item) for item in profile.get("learning_preferences") or [])
        selected = []
        visual_content = any(
            word in text for word in ("算法", "流程", "结构", "分布", "聚类", "关系")
        )
        visual_preference = any(word in preferences for word in ("图", "视觉", "可视化"))
        if visual_content and (
            visual_preference or profile.get("course_level") in {None, "入门", "基础"}
        ):
            selected.append("illustration")
        if any(word in text for word in ("代码", "编程", "python", "java", "c++", "函数", "指针")):
            selected.append("code_case")
        current_progress = (progress.get("current_section") or {}).get("progress") or 0
        if current_progress < 1 or profile.get("weaknesses"):
            selected.append("exercise")
        if len(text) > 1200 or len(section.get("knowledge_points") or []) >= 3:
            selected.append("mind_map")
        if not selected:
            selected.append("exercise")

        raw_resources = [
            {
                "type": resource_type,
                "reason": cls._fallback_reason(resource_type, profile, progress),
            }
            for resource_type in dict.fromkeys(selected)
        ]
        resources = cls._normalize_resources(raw_resources, input_data)
        labels = "、".join(item["title"] for item in resources)
        return {
            "suggestion": f"结合本节学习内容和你的学习画像，建议使用{labels}。",
            "resources": resources,
        }

    @staticmethod
    def _fallback_reason(
        resource_type: str,
        profile: dict[str, Any],
        progress: dict[str, Any],
    ) -> str:
        content_reason = {
            "illustration": "当前内容包含适合可视化呈现的过程、结构或关系",
            "code_case": "当前内容包含需要通过代码实践理解的知识点",
            "exercise": "用于检测并巩固当前小节的掌握情况",
            "mind_map": "当前内容知识点较多，适合进行结构化梳理",
        }[resource_type]
        preferences = "、".join(str(item) for item in profile.get("learning_preferences") or [])
        learner_reason = (
            f"你的学习偏好为{preferences}"
            if preferences
            else f"当前课程水平为{profile.get('course_level') or '入门'}"
        )
        current_progress = (progress.get("current_section") or {}).get("progress") or 0
        return f"{content_reason}；{learner_reason}，当前小节进度为{float(current_progress):.0%}"

    @staticmethod
    def _build_prompt(input_data: Dict[str, Any]) -> str:
        learning_content = input_data.get("learning_content") or {}
        payload = {
            "section": input_data.get("section") or {},
            "learning_content": {
                "title": learning_content.get("title"),
                "content_markdown": str(learning_content.get("content_markdown") or "")[:8000],
                "content_json": learning_content.get("content_json") or {},
            },
            "profile": input_data.get("profile") or {},
            "progress": input_data.get("progress") or {},
        }
        return f"""
你是 EduForge AI 的个性化学习资源入口规划智能体。
请根据当前章节/小节的实际学习内容、知识点、学生画像和学习进度，决定该用户现在可以生成哪些资源壳子。

输入：
{json.dumps(payload, ensure_ascii=False, indent=2)}

要求：
1. 只能从 illustration、code_case、exercise、mind_map 中选择，返回 1 到 4 种，不要固定返回全部类型。
2. illustration 仅用于适合可视化的算法过程、数据分布、结构关系、状态变化或流程。
3. code_case 仅用于包含编程、代码实现或操作实践的内容，并结合学生编程水平判断。
4. exercise 用于巩固薄弱点、检查掌握程度或学习进度尚未完成的情况。
5. mind_map 用于知识点较多、层次或关系复杂、需要整体梳理的内容。
6. 每个资源的 reason 必须同时说明学习内容依据和用户画像依据。
7. 标题、说明、推荐理由和 suggestion 必须使用简体中文。
8. 严格输出 JSON，不输出 Markdown。

JSON 格式：
{{
  "suggestion": "",
  "resources": [
    {{
      "type": "illustration",
      "title": "",
      "subtitle": "",
      "reason": ""
    }}
  ]
}}
"""
