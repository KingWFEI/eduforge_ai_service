import json
from typing import Any, Dict

from app.agents.base import BaseAgent


class CodeAgent(BaseAgent):
    name = "Code Agent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        if "code_case" not in input_data.get("resource_types", []):
            return {
                "generated_resources": input_data.get("generated_resources", []),
                "summary": "跳过代码案例生成",
            }

        result = await self.llm_service.generate_json(
            prompt=self._build_prompt(input_data),
            max_tokens=3500,
            temperature=0.25,
        )

        kp = input_data.get("knowledge_point", "知识点")
        difficulty = input_data.get("difficulty", "基础")
        plan = self._find_plan(input_data, "code_case")
        code = result.get("code")
        if not isinstance(code, str) or not code.strip():
            raise RuntimeError("DeepSeek did not return code case")

        content = {
            "goal": result.get("goal") or input_data.get("goal", ""),
            "language": result.get("language") or "Python",
            "steps": result.get("steps", []),
            "code": code,
            "explanation": result.get("explanation", ""),
            "common_errors": result.get("common_errors", []),
            "extension_tasks": result.get("extension_tasks", []),
        }

        resources = input_data.get("generated_resources", [])
        resources.append({
            "type": "code_case",
            "title": result.get("title") or f"{kp} Python 代码案例",
            "difficulty": result.get("difficulty") or difficulty,
            "description": result.get("description") or f"用代码案例帮助理解 {kp}",
            "reason": result.get("reason") or plan.get("reason"),
            "content_text": code,
            "content_json": content,
            "source": "DeepSeek + 课程知识库 + 学生画像",
        })
        return {"generated_resources": resources, "summary": "DeepSeek 生成代码案例 1 份"}

    def _build_prompt(self, input_data: Dict[str, Any]) -> str:
        payload = self._payload(input_data, "code_case")
        return f"""
你是 EduForge AI 的代码案例生成智能体。

请基于输入生成一个可读、可运行、适合教学的代码案例。

输入：
{json.dumps(payload, ensure_ascii=False, indent=2)}

要求：
0. 除编程语言名称、代码、变量名和必要的专业缩写外，标题、描述、步骤、解释、常见错误和扩展任务必须使用简体中文。
1. 默认使用 Python，除非知识点明显需要其他语言。
2. 代码必须完整、可运行，并包含适量注释。
3. explanation 要解释代码如何体现 knowledge_point。
4. common_errors 写出学习者容易犯的错误。
5. 严格输出 JSON 对象，不要输出 Markdown 代码块。

JSON 格式：
{{
  "title": "",
  "difficulty": "",
  "description": "",
  "reason": "",
  "goal": "",
  "language": "Python",
  "steps": [],
  "code": "",
  "explanation": "",
  "common_errors": [],
  "extension_tasks": []
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
