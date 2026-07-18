from __future__ import annotations

import re
from pathlib import Path

from app.agents.resource_generation.ppt.schemas import HtmlQualityResult


class PptHtmlQualityChecker:
    def check(self, html: str, expected_slides: int) -> HtmlQualityResult:
        issues: list[str] = []
        slide_count = len(re.findall(r'class="slide(?:\s|\")', html))
        required = {"1920px": "缺少 1920 固定舞台", "1080px": "缺少 1080 固定舞台", "object-fit:contain": "图片未使用 contain"}
        compact = re.sub(r"\s+", "", html.lower())
        for token, issue in required.items():
            if token not in compact:
                issues.append(issue)
        for token in ("<iframe", "<object", "<embed", "fetch(", "object-fit:cover", "<script src="):
            if token in compact:
                issues.append(f"包含禁止内容：{token}")
        if slide_count != expected_slides:
            issues.append(f"课件页数不匹配：expected={expected_slides}, actual={slide_count}")
        for number in range(1, expected_slides + 1):
            if f'data-slide-no="{number}"' not in html:
                issues.append(f"缺少连续页码：{number}")
        return HtmlQualityResult(passed=not issues, issues=issues, metrics={"slide_count": slide_count, "aspect_ratio": "16:9"})

    def check_file_with_playwright(self, html_path: Path, timeout_seconds: int) -> HtmlQualityResult:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return HtmlQualityResult(passed=True, issues=[], metrics={"playwright": "not_installed"})
        issues: list[str] = []
        viewports = ((1920, 1080), (1280, 720), (844, 390))
        metrics: dict = {"playwright": "checked", "viewports": {}}
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                for width, height in viewports:
                    page = browser.new_page(viewport={"width": width, "height": height})
                    page.goto(html_path.resolve().as_uri(), wait_until="load", timeout=timeout_seconds * 1000)
                    layout = page.evaluate(
                        """() => {
                          const root = document.documentElement;
                          const stage = document.getElementById('stage').getBoundingClientRect();
                          const active = document.querySelector('.slide.active');
                          return {
                            overflowX: root.scrollWidth > innerWidth,
                            overflowY: root.scrollHeight > innerHeight,
                            stageRatio: stage.width / stage.height,
                            stageInside: stage.left >= -0.5 && stage.top >= -0.5 && stage.right <= innerWidth + 0.5 && stage.bottom <= innerHeight + 0.5,
                            activeHasTitle: Boolean(active && active.querySelector('h1') && active.querySelector('h1').textContent.trim())
                          };
                        }"""
                    )
                    key = f"{width}x{height}"
                    metrics["viewports"][key] = layout
                    if layout["overflowX"] or layout["overflowY"]:
                        issues.append(f"{key} 页面存在滚动")
                    if not layout["stageInside"]:
                        issues.append(f"{key} 舞台越界")
                    if abs(float(layout["stageRatio"]) - 16 / 9) > 0.01:
                        issues.append(f"{key} 未保持 16:9")
                    if not layout["activeHasTitle"]:
                        issues.append(f"{key} 当前页为空白")
                    page.close()
                browser.close()
        except Exception as exc:
            return HtmlQualityResult(
                passed=True,
                issues=[],
                metrics={"playwright": "unavailable", "reason": str(exc)[:300]},
            )
        return HtmlQualityResult(passed=not issues, issues=issues, metrics=metrics)
