from typing import Any, Dict

from app.agents.base import BaseAgent


class PlannerAgent(BaseAgent):
    name = "Planner Agent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        knowledge_points = input_data.get("knowledge_points") or []
        duration_days = int(input_data.get("duration_days") or 7)
        daily_minutes = int(input_data.get("daily_minutes") or 30)

        tasks = []
        for index in range(duration_days):
            point = knowledge_points[index % len(knowledge_points)] if knowledge_points else {}
            topic = point.get("name") if isinstance(point, dict) else str(point)
            tasks.append(
                {
                    "day_no": index + 1,
                    "topic": topic or input_data.get("course_name") or "课程学习",
                    "estimated_minutes": daily_minutes,
                }
            )

        return {
            "agent": self.name,
            "strategy": "priority_weak_points_then_course_order",
            "tasks": tasks,
        }
