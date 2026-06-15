import json
from typing import Any, Dict

from app.agents.base import BaseAgent


class VideoAgent(BaseAgent):
    name = "Video Agent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        if "video_script" not in input_data.get("resource_types", []):
            return {
                "generated_resources": input_data.get("generated_resources", []),
                "summary": "跳过视频脚本生成",
            }

        result = await self.llm_service.generate_json(
            prompt=self._build_prompt(input_data),
            max_tokens=3000,
            temperature=0.3,
        )

        kp = input_data.get("knowledge_point", "知识点")
        difficulty = input_data.get("difficulty", "基础")
        plan = self._find_plan(input_data, "video_script")
        shots = result.get("shots")
        if not isinstance(shots, list) or not shots:
            raise RuntimeError("DeepSeek did not return video shots")

        resources = input_data.get("generated_resources", [])
        resources.append({
            "type": "video_script",
            "title": result.get("title") or f"{kp} 可视化讲解视频脚本",
            "difficulty": result.get("difficulty") or difficulty,
            "description": result.get("description") or f"适合短视频讲解的 {kp} 分镜脚本",
            "reason": result.get("reason") or plan.get("reason"),
            "content_text": result.get("script_text"),
            "content_json": {"shots": shots, "script_text": result.get("script_text")},
            "source": "DeepSeek + 课程知识库 + 学生画像",
        })
        return {"generated_resources": resources, "summary": "DeepSeek 生成视频脚本 1 份"}

    def _build_prompt(self, input_data: Dict[str, Any]) -> str:
        payload = self._payload(input_data, "video_script")
        return f"""
你是 EduForge AI 的教学短视频脚本生成智能体。

请基于输入生成一个适合 1 到 3 分钟短视频的分镜脚本。

输入：
{json.dumps(payload, ensure_ascii=False, indent=2)}

要求：
1. shots 生成 4 到 7 个分镜。
2. 每个分镜包含 shot_no、visual、voice、subtitle、duration。
3. voice 要自然口语化，适合学生理解。
4. visual 要描述可执行的画面，不要空泛。
5. script_text 汇总完整旁白。
6. 严格输出 JSON 对象。

JSON 格式：
{{
  "title": "",
  "difficulty": "",
  "description": "",
  "reason": "",
  "script_text": "",
  "shots": []
}}
"""

    def _payload(self, input_data: Dict[str, Any], resource_type: str) -> Dict[str, Any]:
        return {
            "knowledge_point": input_data.get("knowledge_point", ""),
            "difficulty": input_data.get("difficulty", "基础"),
            "goal": input_data.get("goal", ""),
            "profile": input_data.get("profile", {}),
            "knowledge_chunks": input_data.get("knowledge_chunks", []),
            "resource_plan": self._find_plan(input_data, resource_type),
        }

    def _find_plan(self, input_data: Dict[str, Any], resource_type: str) -> Dict[str, Any]:
        for item in input_data.get("resource_plan", []):
            if item.get("resource_type") == resource_type:
                return item
        return {}
