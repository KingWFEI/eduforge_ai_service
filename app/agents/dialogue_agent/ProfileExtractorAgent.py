# app/agents/profile_extractor_agent.py

from typing import Any, Dict

from app.agents.base import BaseAgent
from app.constants.profile_dialogue import PROFILE_SLOT_CONFIG


class ProfileExtractorAgent(BaseAgent):
    name = "ProfileExtractorAgent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        prompt = self._build_prompt(input_data)
        return await self.llm_service.generate_json(prompt, temperature=0.0)

    def _build_prompt(self, input_data: Dict[str, Any]) -> str:
        return f"""
你是 EduForge AI 的全局学习画像字段抽取智能体。

你的任务：
从学生本轮回答中抽取全部五个画像维度中的有效信息，不限于当前维度。

当前对话重点维度：
{input_data["current_slot"]}

全部维度字段配置：
{PROFILE_SLOT_CONFIG}

当前已有画像字段：
{input_data["existing_fields"]}

学生本轮回答：
{input_data["user_message"]}

要求：
1. 只抽取学生明确表达或可以合理推断的信息。
2. 不要编造。
3. 字段值不确定时不要写入，不要为了填满字段进行推断。
4. 一次回答包含多个维度时必须全部抽取。
5. 当前维度只影响相关性判断，不限制抽取范围。

请严格输出 JSON：
{{
  "slot_updates": {{}},
  "current_slot_relevant": true,
  "has_any_useful_information": true,
  "confidence": 0.0
}}
"""
