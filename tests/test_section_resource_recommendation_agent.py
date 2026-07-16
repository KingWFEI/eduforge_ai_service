import unittest

from app.agents.section_resource_recommendation_agent import (
    SectionResourceRecommendationAgent,
)


class _FakeLlmService:
    def __init__(self, response):
        self.response = response

    async def generate_json(self, **kwargs):
        return self.response


class SectionResourceRecommendationAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_selects_only_resources_supported_by_content_and_profile(self):
        llm = _FakeLlmService(
            {
                "suggestion": "建议先观察聚类图，再通过练习检查掌握情况。",
                "resources": [
                    {
                        "type": "illustration",
                        "title": "聚类过程图解",
                        "subtitle": "观察样本和聚类中心",
                        "reason": "聚类包含数据分布，且学生偏好图解",
                    },
                    {
                        "type": "exercise",
                        "title": "聚类巩固练习",
                        "subtitle": "检查核心概念",
                        "reason": "当前进度未完成，需要练习巩固",
                    },
                ],
            }
        )
        agent = SectionResourceRecommendationAgent(llm)

        result = await agent.run(
            {
                "section": {"section_id": "sec-1", "section_title": "K-Means 聚类"},
                "learning_content": {"content_markdown": "聚类中心和数据分布"},
                "profile": {"learning_preferences": ["图解"]},
                "progress": {"current_section": {"progress": 0.5}},
            }
        )

        self.assertEqual(
            [item["type"] for item in result["resources"]],
            ["illustration", "exercise"],
        )
        self.assertEqual(result["resources"][0]["id"], "res_sec-1_illustration")
        self.assertTrue(result["resources"][0]["reason"])

    def test_fallback_does_not_always_return_all_resource_types(self):
        result = SectionResourceRecommendationAgent.fallback(
            {
                "section": {"section_id": "sec-1", "section_title": "基础术语"},
                "learning_content": {"content_markdown": "这是一个简短定义。"},
                "profile": {"learning_preferences": ["文字阅读"]},
                "progress": {"current_section": {"progress": 1}},
            }
        )

        self.assertEqual([item["type"] for item in result["resources"]], ["exercise"])

    def test_visual_preference_alone_does_not_force_illustration(self):
        result = SectionResourceRecommendationAgent.fallback(
            {
                "section": {"section_id": "sec-1", "section_title": "基础术语"},
                "learning_content": {"content_markdown": "这是一个简短定义。"},
                "profile": {
                    "learning_preferences": ["图解"],
                    "course_level": "入门",
                },
                "progress": {"current_section": {"progress": 0.5}},
            }
        )

        self.assertNotIn("illustration", [item["type"] for item in result["resources"]])


if __name__ == "__main__":
    unittest.main()
