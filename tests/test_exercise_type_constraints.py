import asyncio
import unittest

from app.agents.exercise_agent import ExerciseAgent
from app.agents.student_learning_content_agent import StudentLearningContentAgent


class FakeExerciseLLM:
    async def generate_json(self, **kwargs):
        return {
            "title": "C语言入门练习",
            "difficulty": "基础",
            "description": "检查 C 语言入门掌握情况",
            "reason": "巩固 main 和 printf",
            "questions": [
                {
                    "question_id": "q1",
                    "type": "single_choice",
                    "question": "哪项正确？",
                    "options": [{"key": "A", "value": "main 是入口函数"}, {"key": "B", "value": "printf 是入口函数"}],
                    "correct_answer": "A",
                }
            ],
        }


class ExerciseTypeConstraintTests(unittest.TestCase):
    def test_exercise_agent_rewrites_unsupported_question_types(self):
        agent = ExerciseAgent(llm_service=None)

        questions = agent._normalize_questions(
            [
                {
                    "question_id": "q1",
                    "type": "fill_blank",
                    "question": "C 程序入口函数是___。",
                    "blanks": [{"index": 0, "answer": "main"}],
                },
                {
                    "question_id": "q2",
                    "type": "single_choice",
                    "question": "哪项正确？",
                    "options": [{"key": "A", "value": "正确"}, {"key": "B", "value": "错误"}],
                    "correct_answer": "A",
                },
            ],
            "XGBoost",
        )

        self.assertEqual(questions[0]["type"], "fill_blank")
        self.assertIn("___", questions[0]["question"])
        self.assertEqual(questions[0]["blanks"][0]["answer"], "main")
        self.assertEqual(questions[1]["type"], "choice")

    def test_exercise_agent_resource_content_json_has_resource_fields(self):
        agent = ExerciseAgent(llm_service=FakeExerciseLLM())

        result = asyncio.run(
            agent.run(
                {
                    "resource_types": ["exercise"],
                    "knowledge_point": "C语言入门",
                    "difficulty": "基础",
                    "generated_resources": [],
                }
            )
        )
        content_json = result["generated_resources"][0]["content_json"]

        self.assertEqual(
            set(content_json.keys()),
            {"title", "difficulty", "description", "reason", "exercises"},
        )
        self.assertEqual(content_json["exercises"][0]["type"], "choice")
        self.assertEqual(content_json["exercises"][0]["options"][0]["text"], "main 是入口函数")

    def test_student_learning_content_keeps_exercises_in_required_schema(self):
        content = StudentLearningContentAgent.normalize_content_json(
            {
                "title": "小节",
                "exercises": [
                    {
                        "id": "ex_1",
                        "type": "choice",
                        "question": "以下哪个是入口函数？",
                        "options": [{"key": "A", "text": "main"}, {"key": "B", "text": "printf"}],
                        "correct_answer": "A",
                    },
                    {
                        "id": "ex_2",
                        "type": "fill_blank",
                        "question": "C 程序入口函数是___。",
                        "blanks": [{"index": 0, "answer": "main"}],
                    },
                ],
            }
        )

        self.assertEqual(content["exercises"][0]["type"], "choice")
        self.assertEqual(content["exercises"][0]["options"][0]["text"], "main")
        self.assertEqual(content["exercises"][1]["type"], "fill_blank")
        self.assertEqual(content["exercises"][1]["blanks"][0]["answer"], "main")

    def test_student_learning_content_strips_resource_recommendation_fields(self):
        content = StudentLearningContentAgent.normalize_content_json(
            {
                "title": "指针与内存管理",
                "resources": [
                    {
                        "id": "ai_generated_id",
                        "title": "自定义标题",
                        "subtitle": "自定义副标题",
                        "type": "exercise",
                        "content_json": {"questions": []},
                    }
                ],
                "supplement_suggestion": "建议补充资源",
            },
            section_id="sec_001",
        )

        self.assertNotIn("resources", content)
        self.assertNotIn("supplement_suggestion", content)

    def test_resource_shells_are_generated_separately(self):
        resources = StudentLearningContentAgent.normalize_resource_shells(
            None,
            section_id="sec_001",
            title="指针与内存管理",
        )
        self.assertEqual(
            [item["type"] for item in resources],
            ["illustration", "code_case", "exercise", "mind_map"],
        )
        self.assertEqual(resources[2]["id"], "res_sec_001_exercise")
        self.assertEqual(resources[2]["title"], "指针与内存管理巩固练习")
        self.assertNotIn("content_json", resources[2])


if __name__ == "__main__":
    unittest.main()
