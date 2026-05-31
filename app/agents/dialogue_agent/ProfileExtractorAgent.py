# app/agents/profile_extractor_agent.py

from typing import Any, Dict

from app.agents.base import BaseAgent


class ProfileExtractorAgent(BaseAgent):
    name = "ProfileExtractorAgent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        prompt = self._build_prompt(input_data)
        return await self.llm_service.generate_json(prompt)

    def _build_prompt(self, input_data: Dict[str, Any]) -> str:
        return f"""
你是 EduForge AI 的学习画像字段抽取智能体。

你的任务：
从学生本轮回答中抽取与当前画像维度相关的信息。

当前画像维度：
{input_data["current_slot"]}

该维度需要的字段：
{input_data["slot_requirements"]}

当前已有画像字段：
{input_data["existing_fields"]}

学生本轮回答：
{input_data["user_message"]}

要求：
1. 只抽取学生明确表达或可以合理推断的信息。
2. 不要编造。
3. 如果信息不完整，返回 missing_fields。
4. confidence 表示本轮抽取置信度。

请严格输出 JSON：
{{
  "extracted_fields": {{}},
  "missing_fields": [],
  "slot_completed": false,
  "confidence": 0.0
}}
"""