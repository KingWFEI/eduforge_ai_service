from typing import Any, Dict

from app.agents.base import BaseAgent

# 负责判断：用户这句话有没有回答当前 slot 的问题
class RelevanceJudgeAgent(BaseAgent):
    name = "RelevanceJudgeAgent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        prompt = self._build_prompt(input_data)
        return await self.llm_service.generate_json(prompt, temperature=0.0)

    def _build_prompt(self, input_data: Dict[str, Any]) -> str:
        return f"""
你是 EduForge AI 的画像对话相关性判断智能体。

你的任务：
判断学生本轮回答是否回答了当前画像采集维度的问题。

当前画像维度：
{input_data["current_slot"]}

该维度需要采集的信息：
{input_data["slot_requirements"]}

历史对话摘要：
{input_data["history_summary"]}

学生本轮回答：
{input_data["user_message"]}

请严格输出 JSON，不要输出多余文字：
{{
  "is_relevant": true,
  "relevance_score": 0.0,
  "reason": "",
  "suggested_strategy": "advance | follow_up | acknowledge_and_redirect"
}}
"""
