from typing import Any, Dict

from app.agents.base import BaseAgent


class CodeAgent(BaseAgent):
    name = "Code Agent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        if "code_case" not in input_data.get("resource_types", []):
            return {"generated_resources": input_data.get("generated_resources", []), "summary": "跳过代码案例生成"}

        kp = input_data.get("knowledge_point", "知识点")
        difficulty = input_data.get("difficulty", "基础")
        plan = self._find_plan(input_data, "code_case")

        code = (
            f"# {kp} 代码案例\n"
            "# 这是一个教学示例，用于帮助你把概念落到实践中。\n\n"
            "def explain():\n"
            f"    print('当前学习主题：{kp}')\n"
            "    print('建议：先理解概念，再运行代码，再完成练习。')\n\n"
            "if __name__ == '__main__':\n"
            "    explain()\n"
        )

        content = {
            "goal": f"通过 Python 小案例理解 {kp}",
            "steps": ["阅读概念", "运行代码", "观察输出", "结合练习巩固"],
            "code": code,
            "common_errors": ["只复制代码不理解含义", "没有结合概念解释代码输出"],
        }

        resources = input_data.get("generated_resources", [])
        resources.append({
            "type": "code_case",
            "title": f"{kp} Python 代码案例",
            "difficulty": difficulty,
            "description": f"用 Python 示例帮助理解 {kp}。",
            "reason": plan.get("reason"),
            "content_text": code,
            "content_json": content,
            "source": "课程知识库 + 学生画像",
        })
        return {"generated_resources": resources, "summary": "生成代码案例 1 份"}

    def _find_plan(self, input_data, resource_type):
        for item in input_data.get("resource_plan", []):
            if item.get("resource_type") == resource_type:
                return item
        return {}
