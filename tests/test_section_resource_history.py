import unittest
from types import SimpleNamespace

from app.services.section_resource_generation_service import (
    _find_resource_shell,
    _save_section_learning_resource,
    get_generated_section_resource,
)


class _FakeSession:
    def __init__(self):
        self.added = []
        self.commit_count = 0

    def add(self, item):
        self.added.append(item)

    def commit(self):
        self.commit_count += 1

    def get(self, model, resource_id):
        return next((item for item in self.added if item.id == resource_id), None)


class SectionResourceHistoryTests(unittest.TestCase):
    def test_resource_detail_is_loaded_by_generated_resource_id(self):
        db = _FakeSession()
        current_user = SimpleNamespace(id="student-1")
        item = SimpleNamespace(
            id="slr-1",
            student_id="student-1",
            course_id="course-1",
            knowledge_point_id="kp-1",
            title="聚类图解",
            type="illustration",
            difficulty="easy",
            description="聚类结果",
            content_text="图解说明",
            content_json={
                "visualization": {"image_url": "/uploads/example.png"},
                "_metadata": {"section_id": "section-1"},
            },
            source="python_matplotlib",
            review_status="auto_passed",
            created_at=None,
            updated_at=None,
        )
        db.added.append(item)

        result = get_generated_section_resource(
            db=db,
            current_user=current_user,
            course_id="course-1",
            section_id="section-1",
            resource_id="slr-1",
        )

        self.assertEqual(result["resource_id"], "slr-1")
        self.assertEqual(result["image_url"], "/uploads/example.png")

    def test_subsequent_generation_can_resolve_shell_by_type(self):
        shells = [
            {
                "id": "res_section-1_code_case",
                "title": "Pointer example",
                "subtitle": "Practice pointers",
                "type": "code_case",
            }
        ]

        self.assertEqual(
            _find_resource_shell(shells, None, "code_case"),
            shells[0],
        )
        self.assertEqual(
            _find_resource_shell(shells, "slr_previous_resource", "code_case"),
            shells[0],
        )

    def test_repeated_generation_appends_instead_of_overwriting(self):
        db = _FakeSession()
        current_user = SimpleNamespace(id="student-1")
        section = {
            "section_id": "section-1",
            "section_title": "Pointers",
            "chapter_id": "chapter-1",
            "knowledge_point_id": "kp-1",
            "difficulty": "easy",
        }
        shell = {
            "id": "res_section-1_code_case",
            "title": "Pointer example",
            "subtitle": "Practice pointers",
            "type": "code_case",
        }

        first_id = _save_section_learning_resource(
            db=db,
            current_user=current_user,
            course_id="course-1",
            section=section,
            shell=shell,
            resource_type="code_case",
            resource={"title": "First", "content_json": {"code": "int *p;"}},
            content_id="content-1",
            chunks=[],
            generation_model="test-model",
        )
        second_id = _save_section_learning_resource(
            db=db,
            current_user=current_user,
            course_id="course-1",
            section=section,
            shell=shell,
            resource_type="code_case",
            resource={"title": "Second", "content_json": {"code": "char *p;"}},
            content_id="content-1",
            chunks=[],
            generation_model="test-model",
        )

        self.assertNotEqual(first_id, second_id)
        self.assertEqual(len(db.added), 2)
        self.assertEqual(db.added[0].title, "First")
        self.assertEqual(db.added[1].title, "Second")
        self.assertEqual(db.commit_count, 2)


if __name__ == "__main__":
    unittest.main()
