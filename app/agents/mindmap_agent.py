import json
from typing import Any, Dict

from app.agents.base import BaseAgent


class MindMapAgent(BaseAgent):
    name = "MindMap Agent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        if "mind_map" not in input_data.get("resource_types", []):
            return {
                "generated_resources": input_data.get("generated_resources", []),
                "summary": "跳过思维导图生成",
            }

        result = await self.llm_service.generate_json(
            prompt=self._build_prompt(input_data),
            max_tokens=2500,
            temperature=0.25,
        )

        kp = input_data.get("knowledge_point", "知识点")
        difficulty = input_data.get("difficulty", "基础")
        plan = self._find_plan(input_data, "mind_map")
        tree = result.get("tree")
        if not isinstance(tree, dict):
            raise RuntimeError("DeepSeek did not return mind map tree")

        resources = input_data.get("generated_resources", [])
        resources.append({
            "type": "mind_map",
            "title": result.get("title") or f"{kp} 思维导图",
            "difficulty": result.get("difficulty") or difficulty,
            "description": result.get("description") or f"用结构化导图梳理 {kp}",
            "reason": result.get("reason") or plan.get("reason"),
            "content_text": None,
            "content_json": {"tree": tree},
            "source": "DeepSeek + 课程知识库 + 学生画像",
        })
        return {"generated_resources": resources, "summary": "DeepSeek 生成思维导图 1 份"}

    def _build_prompt(self, input_data: Dict[str, Any]) -> str:
        payload = self._payload(input_data, "mind_map")
        return f"""
你是 EduForge AI 的思维导图生成智能体。

请基于输入生成一棵适合前端渲染的知识树。

输入：
{json.dumps(payload, ensure_ascii=False, indent=2)}

要求：
0. 标题、描述以及 tree 中所有节点名称必须使用简体中文，必要的专业缩写除外。
1. tree 必须是嵌套对象，节点字段只使用 title 和 children。
2. 根节点 title 使用 knowledge_point。
3. 层级控制在 3 到 4 层，覆盖概念、方法、误区、练习路径。
4. 严格输出 JSON 对象。

JSON 格式：
{{
  "title": "",
  "difficulty": "",
  "description": "",
  "reason": "",
  "tree": {{
    "title": "",
    "children": []
  }}
}}
"""

    def _payload(self, input_data: Dict[str, Any], resource_type: str) -> Dict[str, Any]:
        return {
            "knowledge_point": input_data.get("knowledge_point", ""),
            "difficulty": input_data.get("difficulty", "基础"),
            "goal": input_data.get("goal", ""),
            "profile": input_data.get("profile", {}),
            "knowledge_chunks": input_data.get("knowledge_chunks", []),
            "resource_plan": self._find_plan(input_data, resource_type),
        }

    def _find_plan(self, input_data: Dict[str, Any], resource_type: str) -> Dict[str, Any]:
        for item in input_data.get("resource_plan", []):
            if item.get("resource_type") == resource_type:
                return item
        return {}
