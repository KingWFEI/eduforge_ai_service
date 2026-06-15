# app/agents/onboarding_profile_agent.py

from app.agents.base import BaseAgent
from app.skills.profile_generation_skill import ProfileGenerationSkill


class OnboardingProfileAgent(BaseAgent):
    """
    问卷画像智能体。

    现在它不直接写大量规则和 Prompt。
    它只负责调度 ProfileGenerationSkill。
    """

    name = "Onboarding Profile Agent"

    def __init__(self, llm_service=None):
        super().__init__(llm_service)

    def run(self, context):
        """同步执行 Agent（内部 DeepSeek 调用是同步的）"""
        student_id = context.get("student_id", "u_demo")
        answers = context.get("answers", {})

        skill = ProfileGenerationSkill(self.llm_service)

        result = skill.generate_profile(
            student_id=student_id,
            answers=answers
        )

        return result
