import unittest

from app.agents.resource_generation.common.reviewers import MindMapReviewer
from app.agents.resource_generation.mind_map.service import CourseRelationMindMapService


class CourseRelationMindMapTests(unittest.TestCase):
    def test_separates_intra_and_cross_chapter_relations(self):
        state = {
            "course_id": "course_ml",
            "chapter_id": "chapter_tree",
            "section_id": "section_entropy",
            "course_structure": {
                "course": {"id": "course_ml", "name": "机器学习"},
                "chapters": [
                    {"id": "chapter_tree", "parent_id": None, "level": 1, "title": "决策树", "knowledge_points": []},
                    {
                        "id": "section_entropy", "parent_id": "chapter_tree", "level": 2,
                        "title": "信息熵与信息增益",
                        "knowledge_points": [
                            {"id": "kp_entropy", "name": "信息熵", "prerequisites_json": []},
                            {"id": "kp_gain", "name": "信息增益", "prerequisites_json": ["kp_entropy"]},
                        ],
                    },
                    {
                        "id": "chapter_ensemble", "parent_id": None, "level": 1, "title": "集成学习",
                        "knowledge_points": [{"id": "kp_forest", "name": "随机森林", "prerequisites_json": []}],
                    },
                ],
            },
            "current_chapter_context": {"id": "chapter_tree", "title": "决策树"},
            "current_section_context": {"id": "section_entropy", "title": "信息熵与信息增益"},
            "retrieved_chunks": [
                {"chunk_id": "chunk_entropy", "knowledge_point_id": "kp_entropy"},
                {"chunk_id": "chunk_gain", "knowledge_point_id": "kp_gain"},
                {"chunk_id": "chunk_forest", "knowledge_point_id": "kp_forest"},
            ],
            "current_chapter_knowledge_points": [
                {"id": "kp_entropy", "name": "信息熵"}, {"id": "kp_gain", "name": "信息增益"}
            ],
        }
        resource = CourseRelationMindMapService().generate(state)
        content = resource["content_json"]
        self.assertEqual(content["tree"], content["current_chapter_tree"])
        self.assertEqual(content["intra_chapter_relations"][0]["source_knowledge_point_id"], "kp_entropy")
        self.assertEqual(content["intra_chapter_relations"][0]["target_knowledge_point_id"], "kp_gain")
        self.assertTrue(any(item["target_knowledge_point_id"] == "kp_forest" for item in content["cross_chapter_relations"]))
        self.assertTrue(all(item["source_chunk_ids"] for item in content["cross_chapter_relations"]))
        review = MindMapReviewer().review(resource, state)
        self.assertTrue(review.passed, review.issues)


if __name__ == "__main__":
    unittest.main()
