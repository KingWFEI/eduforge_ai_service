from typing import Any, Dict

from app.agents.base import BaseAgent


class ExerciseAgent(BaseAgent):
    name = "Exercise Agent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        if "exercise" not in input_data.get("resource_types", []):
            return {"generated_resources": input_data.get("generated_resources", []), "summary": "跳过练习题生成"}

        kp = input_data.get("knowledge_point", "知识点")
        difficulty = input_data.get("difficulty", "基础")
        plan = self._find_plan(input_data, "exercise")

        questions = [
            {
                "question_id": "q1",
                "type": "single_choice",
                "question": f"学习 {kp} 时，初学者最应该先关注什么？",
                "options": [
                    {"key": "A", "value": "直接背复杂公式"},
                    {"key": "B", "value": "先理解概念含义和应用场景"},
                    {"key": "C", "value": "跳过基础概念"},
                    {"key": "D", "value": "只看代码不看原理"},
                ],
                "answer": "B",
                "analysis": "初学者应先理解概念含义和应用场景，再逐步进入公式、练习和代码。"
            },
            {
                "question_id": "q2",
                "type": "short_answer",
                "question": f"请用自己的话解释 {kp} 的作用。",
                "answer": "能说出核心作用即可。",
                "analysis": "本题用于检测你是否真正理解该知识点，而不是只记住名词。"
            }
        ]

        resources = input_data.get("generated_resources", [])
        resources.append({
            "type": "exercise",
            "title": f"{kp} 基础练习题",
            "difficulty": difficulty,
            "description": f"围绕 {kp} 生成的基础练习与解析。",
            "reason": plan.get("reason"),
            "content_text": None,
            "content_json": {"questions": questions},
            "source": "课程知识库 + 学生画像",
        })
        return {"generated_resources": resources, "summary": "生成练习题 1 份"}

    def _find_plan(self, input_data, resource_type):
        for item in input_data.get("resource_plan", []):
            if item.get("resource_type") == resource_type:
                return item
        return {}
