import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.agents.resource_generation.ppt.html_renderer import PptHtmlRenderer
from app.agents.resource_generation.ppt.html_sanitizer import HtmlSanitizer
from app.agents.resource_generation.ppt.service import PptGenerationService
from app.agents.resource_generation.ppt.style_selector import PptStyleSelector
from app.core.config import settings


class PptGenerationTests(unittest.TestCase):
    def setUp(self):
        self.state = {
            "task_id": "task-test-001",
            "resource_id": "res_test_001",
            "course_id": "course_ml",
            "chapter_id": "chapter_tree",
            "section_id": "section_entropy",
            "knowledge_point_ids": ["kp_entropy"],
            "generation_scope": "section",
            "user_request": "生成适合初学者的互动课件",
            "difficulty": "基础",
            "student_profile": {"learning_preferences_json": ["visual", "practice_based"]},
            "target_knowledge_points": [{"id": "kp_entropy", "name": "信息熵"}],
            "current_chapter_context": {"id": "chapter_tree", "title": "决策树"},
            "current_section_context": {"id": "section_entropy", "title": "信息熵与信息增益"},
            "resource_plan": {"generation_strategy": {"slide_count": 5, "density_mode": "reading_first"}},
            "retrieved_chunks": [
                {
                    "chunk_id": "chunk_001",
                    "document_id": "doc_1",
                    "chapter_id": "section_entropy",
                    "knowledge_point_id": "kp_entropy",
                    "content": "信息熵用于衡量随机变量的不确定性，概率越均匀，不确定性越高。",
                }
            ],
        }

    def test_style_selector_reads_index_and_only_selected_design(self):
        selector = PptStyleSelector()
        original = Path.read_text
        reads = []

        def tracked(path, *args, **kwargs):
            reads.append(str(path).replace("\\", "/"))
            return original(path, *args, **kwargs)

        with patch.object(Path, "read_text", tracked):
            selection = selector.select(PptGenerationService().requirements.build(self.state), self.state)
        self.assertEqual(selection.style_id, "blue-professional")
        design_reads = [item for item in reads if item.endswith("/design.md")]
        self.assertEqual(len(design_reads), 1)
        self.assertIn("blue-professional", design_reads[0])

    def test_html_is_fixed_safe_and_escapes_ai_content(self):
        malicious = dict(self.state)
        malicious["retrieved_chunks"] = [{"chunk_id": "chunk_001", "content": '<script>alert("x")</script>'}]
        service = PptGenerationService()
        requirement = service.requirements.build(malicious)
        deck = service.content.build(service.outline.build(requirement, malicious), requirement, malicious)
        html = PptHtmlRenderer().render(deck, service.styles.select(requirement, malicious))
        self.assertIn("width:1920px", html)
        self.assertIn("height:1080px", html)
        self.assertIn('class="slide active visible"', html)
        self.assertNotIn('<script>alert("x")</script>', html)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<iframe", html.lower())
        self.assertNotIn("object-fit:cover", html.replace(" ", "").lower())
        self.assertIn("object-fit:contain", html.replace(" ", "").lower())
        self.assertNotIn("fetch(", html)
        HtmlSanitizer.assert_safe_document(html)

    def test_five_slide_integration_writes_html_and_cover(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            settings, "GENERATED_RESOURCE_DIR", Path(temp_dir)
        ):
            result = PptGenerationService().generate(self.state)
            html_path = Path(result["artifacts"]["html_path"])
            cover_path = Path(result["artifacts"]["cover_path"])
            html = html_path.read_text(encoding="utf-8")
            self.assertTrue(html_path.is_file())
            self.assertTrue(cover_path.is_file())
            self.assertEqual(html.count('data-slide-no="'), 5)
            visualization = result["content_json"]["visualization"]
            self.assertEqual(visualization["renderer"], "frontend_slides_html")
            self.assertEqual(visualization["aspect_ratio"], "16:9")
            self.assertTrue(visualization["html_url"])
            self.assertEqual(result["file_url"], visualization["html_url"])


if __name__ == "__main__":
    unittest.main()
