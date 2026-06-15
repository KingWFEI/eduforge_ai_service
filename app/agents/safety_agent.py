import json
from typing import Any, Dict, Optional

from app.agents.base import BaseAgent


class SafetyAgent(BaseAgent):
    """Review generated learning resources with DeepSeek."""

    name = "Safety Agent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        resources = input_data.get("generated_resources", [])
        if not resources:
            return {"reviewed_resources": [], "summary": "没有需要审核的资源"}

        result = await self.llm_service.generate_json(
            prompt=self._build_prompt(input_data),
            max_tokens=3000,
            temperature=0.1,
        )

        reviews = result.get("reviews", [])
        if not isinstance(reviews, list):
            raise RuntimeError("DeepSeek returned invalid resource safety reviews")

        reviewed = []
        for index, item in enumerate(resources):
            review = self._find_review(reviews, index, item.get("type"))
            item["review_status"] = review.get("review_status") or "reviewed"
            item["safety_score"] = float(review.get("safety_score", 0.9))
            item["hallucination_risk"] = review.get("hallucination_risk") or "medium"
            item["safety_issues"] = review.get("issues", [])
            item["safety_suggestions"] = review.get("suggestions", [])
            reviewed.append(item)

        return {
            "reviewed_resources": reviewed,
            "summary": f"DeepSeek 已完成 {len(reviewed)} 份资源的安全与幻觉风险审核",
        }

    def _build_prompt(self, input_data: Dict[str, Any]) -> str:
        resources = []
        for index, item in enumerate(input_data.get("generated_resources", [])):
            resources.append({
                "index": index,
                "type": item.get("type"),
                "title": item.get("title"),
                "description": item.get("description"),
                "content_text": item.get("content_text"),
                "content_json": item.get("content_json"),
                "source": item.get("source"),
            })

        payload = {
            "knowledge_point": input_data.get("knowledge_point", ""),
            "goal": input_data.get("goal", ""),
            "difficulty": input_data.get("difficulty", "基础"),
            "knowledge_chunks": input_data.get("knowledge_chunks", []),
            "resources": resources,
        }
        return f"""
你是 EduForge AI 的学习资源安全审核智能体。

请审核生成的学习资源是否适合学生使用，重点检查安全性、教学准确性、是否可能幻觉、是否偏离知识点。

输入：
{json.dumps(payload, ensure_ascii=False, indent=2)}

要求：
1. 每个资源都必须返回一条 review，index 与输入资源 index 对应。
2. review_status 可取 auto_passed、needs_revision、rejected。
3. safety_score 为 0 到 1 的数字。
4. hallucination_risk 可取 low、medium、high。
5. 只输出 JSON 对象。

JSON 格式：
{{
  "reviews": [
    {{
      "index": 0,
      "type": "document",
      "review_status": "auto_passed",
      "safety_score": 0.95,
      "hallucination_risk": "low",
      "issues": [],
      "suggestions": []
    }}
  ]
}}
"""

    def _find_review(self, reviews: list[dict], index: int, resource_type: Optional[str]) -> dict:
        for review in reviews:
            if review.get("index") == index:
                return review
        for review in reviews:
            if review.get("type") == resource_type:
                return review
        return {}
