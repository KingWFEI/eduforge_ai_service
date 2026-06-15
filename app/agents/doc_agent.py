import json
from typing import Any, Dict

from app.agents.base import BaseAgent


class DocAgent(BaseAgent):
    name = "Doc Agent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        if "document" not in input_data.get("resource_types", []):
            return {
                "generated_resources": input_data.get("generated_resources", []),
                "summary": "跳过讲解文档生成",
            }

        markdown = await self.llm_service.generate_text(
            prompt=self._build_prompt(input_data),
            system_prompt=(
                "你是 EduForge AI 的个性化讲解文档生成智能体。"
                "你只输出 Markdown 正文，不输出 JSON，不输出代码块包裹。"
            ),
            max_tokens=3500,
            temperature=0.3,
        )
        if not markdown.strip():
            raise RuntimeError("DeepSeek did not return document markdown")

        kp = input_data.get("knowledge_point", "知识点")
        difficulty = input_data.get("difficulty", "基础")
        plan = self._find_plan(input_data, "document")

        resources = input_data.get("generated_resources", [])
        resources.append({
            "type": "document",
            "title": f"{kp} 个性化讲解文档",
            "difficulty": difficulty,
            "description": f"围绕 {kp} 生成的个性化讲解文档",
            "reason": plan.get("reason"),
            "content_text": markdown,
            "content_json": {
                "markdown": markdown,
                "format": "markdown",
            },
            "source": "DeepSeek + 课程知识库 + 学生画像",
        })
        return {"generated_resources": resources, "summary": "DeepSeek 生成讲解文档 1 份"}

    def _build_prompt(self, input_data: Dict[str, Any]) -> str:
        payload = self._payload(input_data, "document")
        return f"""
请基于输入生成一份适合学生学习的 Markdown 讲解文档。

输入：
{json.dumps(payload, ensure_ascii=False, indent=2)}

要求：
1. 内容必须围绕 knowledge_point 和 goal。
2. 优先使用 knowledge_chunks 中的真实课程信息，不要编造不存在的课程事实。
3. 根据 profile 调整讲解方式、节奏和例子。
4. 文档必须包含：学习目标、核心概念、应用场景、案例解释、常见误区、练习建议。
5. 只输出 Markdown 正文，不要输出 JSON，不要输出 ```markdown 代码块。
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
