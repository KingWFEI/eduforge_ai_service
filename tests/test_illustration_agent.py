import unittest

from app.agents.illustration_agent import IllustrationAgent, validate_visualization_python


class _FakeLlmService:
    def __init__(self, responses):
        self.responses = list(responses)
        self.call_count = 0

    async def generate_json(self, **kwargs):
        self.call_count += 1
        return self.responses.pop(0)


class IllustrationAgentTests(unittest.IsolatedAsyncioTestCase):
    def test_generation_prompt_requires_chinese_output(self):
        agent = IllustrationAgent(_FakeLlmService([]))
        prompt = agent._build_generation_prompt({}, {"should_generate": True})
        self.assertIn("必须使用简体中文", prompt)
        self.assertIn("图表标题、坐标轴、图例、标注", prompt)

    async def test_skips_generation_when_chapter_and_profile_do_not_fit(self):
        llm = _FakeLlmService(
            [
                {
                    "should_generate": False,
                    "reason": "纯文本定义无需图解",
                    "suitability_score": 0.2,
                    "profile_fit_score": 0.3,
                    "visualization_kind": "concept_diagram",
                }
            ]
        )

        result = await IllustrationAgent(llm).run({"knowledge_point": "术语定义"})

        self.assertFalse(result["should_generate"])
        self.assertIsNone(result["resource"])
        self.assertEqual(llm.call_count, 1)

    async def test_generates_python_visualization_for_clustering(self):
        llm = _FakeLlmService(
            [
                {
                    "should_generate": True,
                    "reason": "聚类结果适合使用散点图展示",
                    "suitability_score": 0.95,
                    "profile_fit_score": 0.85,
                    "visualization_kind": "scatter_plot",
                },
                {
                    "title": "K-Means clustering",
                    "description": "Cluster visualization",
                    "overview": "Points are colored by cluster.",
                    "scenes": [],
                    "key_takeaways": ["Nearby points form a cluster"],
                    "python_code": (
                        "import numpy as np\n"
                        "import matplotlib.pyplot as plt\n"
                        "points = np.array([[0, 0], [1, 1], [5, 5]])\n"
                        "fig, ax = plt.subplots()\n"
                        "ax.scatter(points[:, 0], points[:, 1])\n"
                    ),
                },
            ]
        )

        result = await IllustrationAgent(llm).run(
            {
                "knowledge_point": "K-Means",
                "profile": {"learning_preferences": ["图解"]},
                "knowledge_chunks": [],
            }
        )

        self.assertTrue(result["should_generate"])
        self.assertIn("matplotlib.pyplot", result["resource"]["_python_code"])
        self.assertNotIn("visualization", result["resource"]["content_json"])
        self.assertEqual(llm.call_count, 2)

    def test_rejects_unsafe_python(self):
        with self.assertRaises(RuntimeError):
            validate_visualization_python("import os\nfig = os.system('whoami')")
        with self.assertRaises(RuntimeError):
            validate_visualization_python(
                "import matplotlib.pyplot as plt\nfig = plt.figure()\nfig.savefig('x.png')"
            )


if __name__ == "__main__":
    unittest.main()
