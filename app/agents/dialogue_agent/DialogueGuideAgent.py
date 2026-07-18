# app/agents/dialogue_guide_agent.py

import logging
import re
from typing import Any, Dict

from app.agents.base import BaseAgent


logger = logging.getLogger("app.agents.dialogue_guide_agent")

# 负责生成自然回复。
# 重点：它不能生硬地说“请回答问题”，而要根据相关性判断来生成不同风格回复
class DialogueGuideAgent(BaseAgent):
    name = "DialogueGuideAgent"

    FORBIDDEN_PHRASES = (
        "为了更好地了解你",
        "接下来我还想进一步了解",
    )

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return {"assistant_reply": await self.generate_reply(input_data)}

    async def generate_reply(self, input_data: Dict[str, Any]) -> str:
        action = input_data["dialogue_action"]
        if action.get("action") == "confirm_profile":
            return "画像已经生成，请查看预览并确认其中的信息是否准确。"

        prompt = self._build_action_prompt(action)
        try:
            reply = await self.llm_service.generate_text(
                prompt=prompt,
                system_prompt=(
                    "你是 EduForge AI 的学习画像对话助手。"
                    "只把后端给定的确定性对话动作转换成一句简短自然的中文回复。"
                    "你无权改变 Slot、问题字段或是否推进。"
                ),
                temperature=0.2,
                max_tokens=120,
            )
        except Exception as exc:
            logger.warning(
                "dialogue guide generation failed; using deterministic fallback | error=%s",
                exc,
            )
            return self._fallback_reply(action)
        return self._normalize_or_fallback(reply, action)

    def _build_action_prompt(self, action: dict) -> str:
        return f"""
确定性对话动作：{action}

硬性规则：
1. 每次回复最多提出一个问题。
2. 回复控制在 20～45 个中文字符，特殊情况不得超过 60 字。
3. 不解释画像构建流程。
4. 不使用“为了更好地了解你”或“接下来我还想进一步了解”。
5. 承接用户回答最多一句，不重复大段总结。
6. 只能询问 question_field 对应的 question_text，不得增加其他问题。
7. action=advance 时简短承接后询问下一 Slot 的问题。
8. action=follow_up 时只追问缺失的具体字段。
9. action=recover_from_irrelevant 时温和拉回 question_text。
10. 只输出直接给学生看的纯文本，不要 Markdown。
"""

    def _normalize_or_fallback(self, reply: str, action: dict) -> str:
        normalized = re.sub(r"\s+", "", (reply or "").strip())
        max_length = 60 if action.get("action") == "recover_from_irrelevant" else 45
        invalid = (
            not normalized
            or len(normalized) < 20
            or len(normalized) > max_length
            or normalized.count("？") + normalized.count("?") > 1
            or any(phrase in normalized for phrase in self.FORBIDDEN_PHRASES)
        )
        if invalid:
            return self._fallback_reply(action)
        return normalized

    @staticmethod
    def _fallback_reply(action: dict) -> str:
        if action.get("action") == "confirm_profile":
            return "画像已经生成，请查看预览并确认其中的信息是否准确。"
        question = action.get("question_text") or "你愿意再说一点吗？"
        if action.get("action") == "recover_from_irrelevant":
            return f"这个话题稍后也可以聊。{question}"
        if action.get("action") in {"advance", "skip_and_advance"}:
            return f"了解，已记录你提供的信息。{question}"
        return f"知道了，我们继续补充这一点。{question}"
