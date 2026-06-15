from typing import Any, Dict

from app.agents.base import BaseAgent


class EvaluationAgent(BaseAgent):
    name = "Evaluation Agent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        score = float(input_data.get("score") or 0)
        weak_points = input_data.get("weak_points") or []
        return {
            "agent": self.name,
            "level": "good" if score >= 80 else "needs_practice" if score < 60 else "normal",
            "weak_points": weak_points,
            "summary": "练习结果已完成评估",
        }
