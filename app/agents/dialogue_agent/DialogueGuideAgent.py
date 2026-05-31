# app/agents/dialogue_guide_agent.py

from typing import Any, Dict, AsyncGenerator

from app.agents.base import BaseAgent

# 负责生成自然回复。
# 重点：它不能生硬地说“请回答问题”，而要根据相关性判断来生成不同风格回复
class DialogueGuideAgent(BaseAgent):
    name = "DialogueGuideAgent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        prompt = self._build_json_prompt(input_data)
        return await self.llm_service.generate_json(prompt)

    async def stream_reply(
            self,
            input_data: Dict[str, Any],
    ) -> AsyncGenerator[str, None]:
        prompt = self._build_stream_prompt(input_data)

        system_prompt = (
            "你是 EduForge AI 的学习画像对话助手。"
            "你要根据画像采集状态，生成自然、温和、有引导性的回复。"
            "不要输出 JSON，不要输出 Markdown 标题，只输出直接对学生说的话。"
        )

        async for delta in self.llm_service.stream_text(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.4,
                max_tokens=600,
        ):
            yield delta

    def _build_stream_prompt(self, input_data: Dict[str, Any]) -> str:
        return f"""
    当前画像对话状态如下：

    当前 slot：
    {input_data["current_slot"]}

    下一步 slot：
    {input_data.get("next_slot")}

    用户本轮回答：
    {input_data["user_message"]}

    相关性判断：
    {input_data["relevance_result"]}

    本轮抽取结果：
    {input_data["extract_result"]}

    当前已收集画像字段：
    {input_data["extracted_fields"]}

    缺失 slot：
    {input_data["missing_slots"]}

    画像预览：
    {input_data.get("profile_preview")}

    请生成一段自然、温和、有引导性的回复。

    规则：
    1. 如果用户回答有效：先简短总结用户信息，再自然进入下一个问题。
    2. 如果用户回答部分有效：肯定已获取的信息，再追问缺失部分。
    3. 如果用户回答无关：先承接用户话题，再温和拉回当前问题。
    4. 如果画像已完整：提示已经生成初步画像，让用户确认保存。
    5. 控制在 80 字左右。
    6. 不要输出 JSON。
    """

    def _build_json_prompt(self, input_data: Dict[str, Any]) -> str:
            return f"""
    你是 EduForge AI 的画像对话引导智能体。
    请根据输入生成结构化回复。

    输入：
    {input_data}

    请严格输出 JSON：
    {{
      "assistant_reply": "",
      "tone": "friendly",
      "next_question": ""
    }}
    """