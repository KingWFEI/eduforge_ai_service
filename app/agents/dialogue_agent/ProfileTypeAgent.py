# app/agents/profile_type_agent.py

from typing import Any, Dict

from app.agents.base import BaseAgent

# 当所有 slot 基本完成后，用它生成画像类型
class ProfileTypeAgent(BaseAgent):
    name = "ProfileTypeAgent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        prompt = self._build_prompt(input_data)
        return await self.llm_service.generate_json(prompt)

    def _build_prompt(self, input_data: Dict[str, Any]) -> str:
        return f"""
你是 EduForge AI 的学习画像类型判断智能体。

请根据学生画像字段，生成一个学习画像类型。

可选画像类型：
1. visual_explorer：图解探索者
2. code_practitioner：代码实践者
3. exam_sprinter：考试冲刺者
4. project_challenger：项目挑战者
5. foundation_builder：慢热筑基者
6. deep_researcher：深度钻研者
7. fragmented_learner：碎片学习者
8. mistake_fixer：错题修复者
9. case_learner：案例理解者
10. balanced_grower：综合成长者

学生画像字段：
{input_data["extracted_fields"]}

请严格输出 JSON：
{{
  "profile_type": "",
  "profile_type_name": "",
  "summary": "",
  "tags": [],
  "reason": "",
  "confidence": 0.0
}}
"""