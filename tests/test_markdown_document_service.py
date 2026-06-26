import unittest

from app.services.document_asset_service import append_source_images, extract_image_urls
from app.services.markdown_document_service import (
    StructuredChunk,
    build_structure_context,
    extract_markdown_outline,
    match_chunk_to_structure,
    normalize_markdown_headings,
    parse_markdown_sections,
    split_markdown_into_chunks,
)


SAMPLE_MARKDOWN = """决策树原理

1 决策树基础
1.1 决策树是如何工作的
1.2 构建决策树
1.2.1 ID3算法构建决策树

1 决策树基础

1.1 决策树是如何工作的

决策树用于分类和回归。

1.2 构建决策树

构建过程需要选择最佳分枝。

1.2.1 ID3算法构建决策树

ID3使用信息增益选择特征。

# random_state=420

这是一行代码注释，不是课程标题。
"""


class MarkdownDocumentServiceTests(unittest.TestCase):
    def test_normalizes_numbered_headings_and_removes_leading_toc(self):
        normalized = normalize_markdown_headings(SAMPLE_MARKDOWN)

        self.assertEqual(normalized.count("## 1.1 决策树是如何工作的"), 1)
        self.assertEqual(normalized.count("## 1.2 构建决策树"), 1)
        self.assertEqual(normalized.count("### 1.2.1 ID3算法构建决策树"), 1)
        self.assertEqual(normalized.count("# 1 决策树基础"), 1)

    def test_parses_heading_paths(self):
        sections = parse_markdown_sections(SAMPLE_MARKDOWN)

        self.assertEqual(len(sections), 3)
        self.assertEqual(
            sections[-1].heading_path,
            ("1 决策树基础", "1.2 构建决策树", "1.2.1 ID3算法构建决策树"),
        )
        self.assertIn("# random_state=420", sections[-1].content)

    def test_splits_only_inside_each_section(self):
        chunks = split_markdown_into_chunks(
            SAMPLE_MARKDOWN,
            chunk_size=40,
            overlap=5,
        )

        self.assertGreaterEqual(len(chunks), 3)
        self.assertTrue(all(chunk.heading_title for chunk in chunks))
        self.assertTrue(
            any(chunk.section.endswith("1.2.1 ID3算法构建决策树") for chunk in chunks)
        )

    def test_matches_confirmed_section_before_llm_classification(self):
        chunk = StructuredChunk(
            content="### 1.2.1 ID3算法构建决策树\n\nID3使用信息增益。",
            section="1.2 构建决策树 > 1.2.1 ID3算法构建决策树",
            heading_path=("1.2 构建决策树", "1.2.1 ID3算法构建决策树"),
            heading_title="1.2.1 ID3算法构建决策树",
            heading_level=3,
        )
        structure = [
            {
                "chapter_id": "ch_1",
                "chapter_title": "构建决策树",
                "section_id": "sec_id3",
                "section_title": "ID3算法构建决策树",
                "knowledge_point_id": "kp_gain",
                "knowledge_point_name": "信息增益",
            }
        ]

        chapter_id, knowledge_point_id, keywords = match_chunk_to_structure(
            chunk,
            structure,
        )

        self.assertEqual(chapter_id, "sec_id3")
        self.assertEqual(knowledge_point_id, "kp_gain")
        self.assertIn("ID3算法构建决策树", keywords)

    def test_builds_complete_outline_first_structure_context(self):
        outline = extract_markdown_outline(SAMPLE_MARKDOWN)
        context = build_structure_context(SAMPLE_MARKDOWN)

        self.assertIn((1, "1 决策树基础"), outline)
        self.assertNotIn((1, "random_state=420"), outline)
        self.assertIn("【文档完整目录】", context)
        self.assertIn("- 1 决策树基础", context)
        self.assertIn("    - 1.2.1 ID3算法构建决策树", context)

    def test_extracts_and_appends_public_source_images(self):
        url = "/uploads/course_documents/course/doc/assets/image.png"
        chunk = {"content": f"正文\n\n![插图]({url})"}

        self.assertEqual(extract_image_urls(chunk["content"]), [url])
        enriched = append_source_images("# 小节内容", [chunk])
        self.assertIn("## 来源插图", enriched)
        self.assertIn(url, enriched)


if __name__ == "__main__":
    unittest.main()
