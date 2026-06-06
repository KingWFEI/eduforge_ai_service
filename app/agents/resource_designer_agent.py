from typing import Any, Dict

from app.agents.base import BaseAgent


class ResourceDesignerAgent(BaseAgent):
    """
    资源设计智能体。

    作用：
    根据画像、知识点、目标和资源类型，设计每类资源的生成重点与推荐理由。
    """

    name = "Resource Designer Agent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        profile = input_data.get("profile", {})
        resource_types = input_data.get("resource_types", [])
        knowledge_point = input_data.get("knowledge_point", "")
        difficulty = input_data.get("difficulty", "基础")
        goal = input_data.get("goal", "")

        preferences = profile.get("learning_preferences", []) or []
        weaknesses = profile.get("weaknesses", []) or []

        plan = []
        for resource_type in resource_types:
            plan.append({
                "resource_type": resource_type,
                "knowledge_point": knowledge_point,
                "difficulty": difficulty,
                "focus": self._focus_for(resource_type),
                "reason": self._reason_for(
                    resource_type=resource_type,
                    preferences=preferences,
                    weaknesses=weaknesses,
                    goal=goal,
                ),
            })

        return {
            "resource_plan": plan,
            "summary": f"已完成 {len(plan)} 类资源的生成规划"
        }

    def _focus_for(self, resource_type: str) -> str:
        mapping = {
            "document": "用图解、案例和分步骤说明帮助学生理解概念",
            "mind_map": "用结构化导图梳理知识点层次关系",
            "exercise": "围绕薄弱点生成基础练习题和解析",
            "code_case": "用可运行代码把概念落到实践",
            "video_script": "生成适合短视频讲解的分镜脚本",
        }
        return mapping.get(resource_type, "生成个性化学习资源")

    def _reason_for(self, resource_type: str, preferences, weaknesses, goal: str) -> str:
        pref_text = "、".join(preferences) if preferences else "循序渐进学习"
        weak_text = "、".join(weaknesses) if weaknesses else "当前知识点"

        if resource_type == "document":
            return f"你偏好{pref_text}，适合先通过讲解文档建立直观理解。"
        if resource_type == "mind_map":
            return f"你需要梳理知识结构，导图可以帮助你把{weak_text}相关概念串起来。"
        if resource_type == "exercise":
            return f"你的薄弱点包含{weak_text}，需要通过练习题巩固。"
        if resource_type == "code_case":
            return f"你的学习目标是{goal or '提升实践能力'}，代码案例可以帮助你动手验证知识。"
        if resource_type == "video_script":
            return "视频脚本适合把抽象知识转化为更直观的讲解内容。"
        return "根据你的画像和学习目标进行个性化推荐。"
