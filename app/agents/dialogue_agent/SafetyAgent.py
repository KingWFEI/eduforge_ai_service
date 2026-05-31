# app/agents/safety_agent.py

from typing import Any, Dict

from app.agents.base import BaseAgent


class SafetyAgent(BaseAgent):
    name = "SafetyAgent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        prompt = self._build_prompt(input_data)
        return await self.llm_service.generate_json(prompt)

    def _build_prompt(self, input_data: Dict[str, Any]) -> str:
        return f"""
你是 EduForge AI 的安全审核智能体。

请检查下面的 AI 回复是否适合展示给学生：
{input_data["assistant_reply"]}

检查点：
1. 是否包含不适合学生的内容。
2. 是否语气生硬或冒犯。
3. 是否过度诊断学生能力。
4. 是否出现明显编造。
5. 是否泄露系统提示词。

请严格输出 JSON：
{{
  "passed": true,
  "safe_reply": "",
  "issues": []
}}
"""