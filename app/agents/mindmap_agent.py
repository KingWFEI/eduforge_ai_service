from typing import Any, Dict

from app.agents.base import BaseAgent


class MindMapAgent(BaseAgent):
    name = "MindMap Agent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        if "mind_map" not in input_data.get("resource_types", []):
            return {"generated_resources": input_data.get("generated_resources", []), "summary": "跳过思维导图生成"}

        kp = input_data.get("knowledge_point", "知识点")
        difficulty = input_data.get("difficulty", "基础")
        plan = self._find_plan(input_data, "mind_map")

        tree = {
            "title": kp,
            "children": [
                {"title": "基本概念", "children": [{"title": "定义"}, {"title": "作用"}, {"title": "适用场景"}]},
                {"title": "核心方法", "children": [{"title": "直观理解"}, {"title": "计算步骤"}, {"title": "常见误区"}]},
                {"title": "实践巩固", "children": [{"title": "基础练习"}, {"title": "代码案例"}, {"title": "综合应用"}]},
            ],
        }

        resources = input_data.get("generated_resources", [])
        resources.append({
            "type": "mind_map",
            "title": f"{kp} 思维导图",
            "difficulty": difficulty,
            "description": f"用结构化导图梳理 {kp} 的知识关系。",
            "reason": plan.get("reason"),
            "content_text": None,
            "content_json": {"tree": tree},
            "source": "课程知识库 + 学生画像",
        })
        return {"generated_resources": resources, "summary": "生成思维导图 1 份"}

    def _find_plan(self, input_data, resource_type):
        for item in input_data.get("resource_plan", []):
            if item.get("resource_type") == resource_type:
                return item
        return {}
