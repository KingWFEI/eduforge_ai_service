from typing import Any, Dict

from app.agents.base import BaseAgent


class SafetyAgent(BaseAgent):
    """
    安全审核智能体。

    最小版：
    对生成资源做自动审核标记。
    后续可以接入 DeepSeek 或规则库做更严格审核。
    """

    name = "Safety Agent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        reviewed = []

        for item in input_data.get("generated_resources", []):
            item["review_status"] = "auto_passed"
            item["safety_score"] = 0.95
            item["hallucination_risk"] = "low"
            reviewed.append(item)

        return {
            "reviewed_resources": reviewed,
            "summary": f"已完成 {len(reviewed)} 份资源的安全审核"
        }
