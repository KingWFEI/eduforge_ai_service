from __future__ import annotations

from pathlib import Path

from app.core.config import settings


class PptThumbnailRenderer:
    def render_cover(self, html_path: Path, output_path: Path, title: str) -> str:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1920, "height": 1080})
                page.goto(html_path.resolve().as_uri(), wait_until="load", timeout=settings.PPT_PLAYWRIGHT_TIMEOUT_SECONDS * 1000)
                page.screenshot(path=str(output_path), animations="disabled")
                browser.close()
        except Exception:
            import matplotlib
            matplotlib.use("Agg")
            from matplotlib import pyplot as plt
            from matplotlib.font_manager import FontProperties

            fig = plt.figure(figsize=(16, 9), dpi=120, facecolor="#f7f3e8")
            font = self._cjk_font(FontProperties)
            fig.text(0.08, 0.66, title[:40], fontsize=34, color="#0b3b8f", weight="bold", fontproperties=font)
            fig.text(0.08, 0.56, "EduForge AI 互动教学课件", fontsize=18, color="#486581", fontproperties=font)
            fig.savefig(output_path, pad_inches=0, facecolor=fig.get_facecolor())
            plt.close(fig)
        return str(output_path)

    @staticmethod
    def _cjk_font(font_properties_class):
        candidates = (
            Path("C:/Windows/Fonts/msyh.ttc"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/System/Library/Fonts/PingFang.ttc"),
        )
        path = next((item for item in candidates if item.is_file()), None)
        return font_properties_class(fname=str(path)) if path else font_properties_class()
