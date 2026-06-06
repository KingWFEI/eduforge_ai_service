from typing import Any, Dict

from app.agents.base import BaseAgent


class DocAgent(BaseAgent):
    name = "Doc Agent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        if "document" not in input_data.get("resource_types", []):
            return {"generated_resources": input_data.get("generated_resources", []), "summary": "跳过讲解文档生成"}

        kp = input_data.get("knowledge_point", "知识点")
        difficulty = input_data.get("difficulty", "基础")
        profile = input_data.get("profile", {})
        chunks = input_data.get("knowledge_chunks", [])
        plan = self._find_plan(input_data, "document")

        references = "\n".join([f"- {c.get('content', '')[:160]}" for c in chunks[:3]])
        preferences = "、".join(profile.get("learning_preferences", []) or ["图解讲解"])
        weaknesses = "、".join(profile.get("weaknesses", []) or [kp])

        markdown = f"""# {kp} 个性化讲解文档

## 1. 本次学习目标
本资源面向当前学生画像生成，难度为：{difficulty}。你可以先建立直观理解，再进入例题和实践。

## 2. 为什么这样学
你的学习偏好包括：{preferences}。当前需要重点关注：{weaknesses}。因此本文会尽量减少一上来的抽象推导，先用图解思路和生活化解释帮助理解。

## 3. 核心知识
{references or f'{kp} 是当前需要学习和巩固的核心知识点。'}

## 4. 学习建议
先读概念，再看例子，最后配合练习题和代码案例巩固。遇到公式时，先理解它在解决什么问题，再记忆计算过程。
"""

        resources = input_data.get("generated_resources", [])
        resources.append({
            "type": "document",
            "title": f"{kp} 图解讲解文档",
            "difficulty": difficulty,
            "description": f"用图解和案例解释 {kp} 的基础概念。",
            "reason": plan.get("reason"),
            "content_text": markdown,
            "content_json": {"markdown": markdown},
            "source": "课程知识库 + 学生画像",
        })

        return {"generated_resources": resources, "summary": "生成讲解文档 1 份"}

    def _find_plan(self, input_data, resource_type):
        for item in input_data.get("resource_plan", []):
            if item.get("resource_type") == resource_type:
                return item
        return {}
