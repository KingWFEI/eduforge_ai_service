import json
from typing import Any, Dict

from app.agents.base import BaseAgent


class ResourceDesignerAgent(BaseAgent):
    """Design the generation plan for requested learning resources."""

    name = "Resource Designer Agent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        prompt = self._build_prompt(input_data)
        result = await self.llm_service.generate_json(
            prompt=prompt,
            max_tokens=1800,
            temperature=0.2,
        )

        resource_plan = result.get("resource_plan", [])
        if not isinstance(resource_plan, list):
            raise RuntimeError("DeepSeek returned invalid resource_plan")

        requested_types = input_data.get("resource_types", [])
        normalized_plan = []
        for resource_type in requested_types:
            plan_item = self._find_plan(resource_plan, resource_type)
            normalized_plan.append({
                "resource_type": resource_type,
                "knowledge_point": input_data.get("knowledge_point", ""),
                "difficulty": input_data.get("difficulty", "基础"),
                "focus": plan_item.get("focus") or "",
                "reason": plan_item.get("reason") or "",
                "requirements": plan_item.get("requirements") or [],
            })

        return {
            "resource_plan": normalized_plan,
            "summary": f"DeepSeek 已完成 {len(normalized_plan)} 类资源的生成规划",
        }

    def _build_prompt(self, input_data: Dict[str, Any]) -> str:
        payload = {
            "profile": input_data.get("profile", {}),
            "resource_types": input_data.get("resource_types", []),
            "knowledge_point": input_data.get("knowledge_point", ""),
            "difficulty": input_data.get("difficulty", "基础"),
            "goal": input_data.get("goal", ""),
            "knowledge_chunks": input_data.get("knowledge_chunks", []),
        }
        return f"""
你是 EduForge AI 的学习资源设计智能体。

请根据学生画像、知识点、学习目标和知识库片段，为每一种 requested resource type 设计生成重点。

输入：
{json.dumps(payload, ensure_ascii=False, indent=2)}

要求：
1. 只为输入中的 resource_types 生成规划。
2. reason 要解释为什么这种资源适合当前学生和目标。
3. requirements 写清楚后续资源生成必须覆盖的内容。
4. 严格输出 JSON 对象，不要输出 Markdown。

JSON 格式：
{{
  "resource_plan": [
    {{
      "resource_type": "document",
      "focus": "",
      "reason": "",
      "requirements": []
    }}
  ]
}}
"""

    def _find_plan(self, resource_plan: list[dict], resource_type: str) -> dict:
        for item in resource_plan:
            if item.get("resource_type") == resource_type:
                return item
        return {}
