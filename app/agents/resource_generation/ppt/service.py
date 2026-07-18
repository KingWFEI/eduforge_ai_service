from __future__ import annotations

import re
from pathlib import Path

from app.agents.resource_generation.ppt.content_agent import PptContentAgent
from app.agents.resource_generation.ppt.html_quality_checker import PptHtmlQualityChecker
from app.agents.resource_generation.ppt.html_renderer import PptHtmlRenderer
from app.agents.resource_generation.ppt.outline_agent import PptOutlineAgent
from app.agents.resource_generation.ppt.requirement_agent import PptRequirementAgent
from app.agents.resource_generation.ppt.style_selector import PptStyleSelector
from app.agents.resource_generation.ppt.thumbnail_renderer import PptThumbnailRenderer
from app.core.config import settings


class PptGenerationService:
    def __init__(self):
        self.requirements = PptRequirementAgent()
        self.outline = PptOutlineAgent()
        self.content = PptContentAgent()
        self.styles = PptStyleSelector()
        self.renderer = PptHtmlRenderer()
        self.quality = PptHtmlQualityChecker()
        self.thumbnails = PptThumbnailRenderer()

    def generate(self, state: dict) -> dict:
        task_dir = self._task_dir(str(state["task_id"]))
        task_dir.mkdir(parents=True, exist_ok=True)
        requirement = self.requirements.build(state)
        outline = self.outline.build(requirement, state)
        deck = self.content.build(outline, requirement, state)
        style = self.styles.select(requirement, state)
        html = self.renderer.render(deck, style)
        quality = self.quality.check(html, len(deck.slides))
        if not quality.passed:
            raise ValueError("HTML 课件质量检查失败：" + "；".join(quality.issues))
        html_path = task_dir / "index.html"
        html_path.write_text(html, encoding="utf-8")
        browser_quality = self.quality.check_file_with_playwright(
            html_path,
            settings.PPT_PLAYWRIGHT_TIMEOUT_SECONDS,
        )
        if not browser_quality.passed:
            raise ValueError("浏览器布局检查失败：" + "；".join(browser_quality.issues))
        quality.metrics.update(browser_quality.metrics)
        cover_path = task_dir / "cover.png"
        self.thumbnails.render_cover(html_path, cover_path, deck.slides[0].title)
        resource_id = str(state.get("resource_id") or "pending")
        html_entry = f"/api/resources/{resource_id}/html-entry"
        preview_entry = f"/api/resources/{resource_id}/preview"
        sources = [
            {
                "chunk_id": item.get("chunk_id"),
                "document_id": item.get("document_id"),
                "chapter_id": item.get("chapter_id"),
                "section_id": item.get("section_id"),
            }
            for item in (state.get("retrieved_chunks") or [])
            if item.get("chunk_id")
        ]
        return {
            "type": "ppt",
            "title": deck.slides[0].title,
            "overview": deck.overview,
            "content_text": deck.overview,
            "content_json": {
                "overview": deck.overview,
                "key_takeaways": deck.key_takeaways,
                "resource_mode": "interactive_html_slides",
                "scope": {
                    "course_id": state.get("course_id"),
                    "chapter_id": state.get("chapter_id"),
                    "section_id": state.get("section_id"),
                    "knowledge_point_ids": state.get("knowledge_point_ids") or [],
                },
                "style": style.model_dump(exclude={"design_path"}),
                "density_mode": requirement.density_mode,
                "slides": [slide.model_dump() for slide in deck.slides],
                "visualization": {
                    "renderer": "frontend_slides_html",
                    "html_url": html_entry,
                    "cover_url": preview_entry,
                    "thumbnail_urls": [],
                    "slide_count": len(deck.slides),
                    "aspect_ratio": "16:9",
                    "stage_width": 1920,
                    "stage_height": 1080,
                    "supports_animation": True,
                    "supports_swipe": True,
                    "supports_fullscreen": True,
                },
                "sources": sources,
            },
            "source": "课程知识库 + 学生画像",
            "source_type": "generated",
            "generation_mode": "interactive_html_slides",
            "file_url": html_entry,
            "preview_url": preview_entry,
            "source_references": sources,
            "artifacts": {"html_path": str(html_path), "cover_path": str(cover_path)},
            "quality_metrics": quality.metrics,
        }

    @staticmethod
    def _task_dir(task_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", task_id):
            raise ValueError("非法 task_id")
        base = (settings.GENERATED_RESOURCE_DIR / "ppts").resolve()
        target = (base / task_id).resolve()
        if base not in target.parents:
            raise ValueError("生成目录越界")
        return target
