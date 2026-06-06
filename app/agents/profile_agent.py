from typing import Any, Dict

from app.agents.base import BaseAgent
from app.models.student_profile import StudentProfile


class ProfileAgent(BaseAgent):
    """
    学生画像智能体。

    作用：
    从 student_profiles 表读取当前学生画像，
    给后续资源生成智能体使用。
    """

    name = "Profile Agent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        db = input_data["db"]
        student_id = input_data["student_id"]

        profile = (
            db.query(StudentProfile)
            .filter(StudentProfile.student_id == student_id)
            .first()
        )

        if not profile:
            profile_data = {
                "student_id": student_id,
                "target_course": None,
                "learning_goals": [],
                "coding_level": "一般",
                "math_level": "一般",
                "course_level": "入门",
                "learning_preferences": ["图解讲解"],
                "weaknesses": [],
                "cognitive_style": [],
                "time_budget": "每天 30 分钟",
                "summary": "暂未生成学习画像，系统将使用默认初学者画像生成资源。"
            }
        else:
            profile_data = {
                "profile_id": profile.id,
                "student_id": profile.student_id,
                "target_course": profile.target_course,
                "learning_goals": profile.learning_goals_json or [],
                "coding_level": profile.coding_level,
                "math_level": profile.math_level,
                "course_level": profile.course_level,
                "learning_preferences": profile.learning_preferences_json or [],
                "weaknesses": profile.weaknesses_json or [],
                "cognitive_style": profile.cognitive_style_json or [],
                "time_budget": profile.time_budget,
                "summary": profile.summary,
                "confidence": profile.confidence,
            }

        return {
            "profile": profile_data,
            "summary": "已读取学生画像"
        }
