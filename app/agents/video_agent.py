from typing import Any, Dict

from app.agents.base import BaseAgent


class VideoAgent(BaseAgent):
    name = "Video Agent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        if "video_script" not in input_data.get("resource_types", []):
            return {"generated_resources": input_data.get("generated_resources", []), "summary": "跳过视频脚本生成"}

        kp = input_data.get("knowledge_point", "知识点")
        difficulty = input_data.get("difficulty", "基础")
        plan = self._find_plan(input_data, "video_script")

        shots = [
            {
                "shot_no": 1,
                "visual": f"画面展示学生看到“{kp}”概念时有些困惑",
                "voice": f"很多同学第一次学习 {kp} 时，会觉得它比较抽象。",
                "subtitle": f"{kp}：先建立直观理解",
                "duration": "8s",
            },
            {
                "shot_no": 2,
                "visual": "画面切换为生活化例子和简单图示",
                "voice": "我们先用例子理解它在解决什么问题，再进入计算和代码。",
                "subtitle": "先看例子，再看公式",
                "duration": "10s",
            },
            {
                "shot_no": 3,
                "visual": "展示图解、练习题和代码案例的学习顺序",
                "voice": "建议按照图解、例题、代码案例和基础练习的顺序学习。",
                "subtitle": "图解 → 例题 → 代码 → 练习",
                "duration": "12s",
            },
        ]

        resources = input_data.get("generated_resources", [])
        resources.append({
            "type": "video_script",
            "title": f"{kp} 可视化讲解视频脚本",
            "difficulty": difficulty,
            "description": f"适合短视频讲解的 {kp} 分镜脚本。",
            "reason": plan.get("reason"),
            "content_text": None,
            "content_json": {"shots": shots},
            "source": "课程知识库 + 学生画像",
        })
        return {"generated_resources": resources, "summary": "生成视频脚本 1 份"}

    def _find_plan(self, input_data, resource_type):
        for item in input_data.get("resource_plan", []):
            if item.get("resource_type") == resource_type:
                return item
        return {}
