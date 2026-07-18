from __future__ import annotations

import json
from pathlib import Path

from app.agents.resource_generation.ppt.schemas import PptRequirement, StyleSelection
from app.core.config import settings


class PptStyleSelector:
    def __init__(self, vendor_dir: Path | None = None):
        self.vendor_dir = (vendor_dir or settings.FRONTEND_SLIDES_VENDOR_DIR).resolve()

    def select(self, requirement: PptRequirement, state: dict) -> StyleSelection:
        index_path = self.vendor_dir / "bold-template-pack" / "selection-index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        templates = index.get("templates") or []
        preferred = settings.PPT_DEFAULT_STYLE
        chosen = next((item for item in templates if item.get("slug") == preferred), None)
        if chosen is None:
            chosen = next(
                (item for item in templates if item.get("scheme") == "light" and item.get("formality") in {"high", "medium-high"}),
                templates[0],
            )
        design_relative = str(chosen.get("design_md") or "")
        design_path = (self.vendor_dir / design_relative).resolve()
        if self.vendor_dir not in design_path.parents or not design_path.is_file():
            raise ValueError("模板 design.md 路径无效")
        # Progressive disclosure: only the selected design is loaded.
        design_path.read_text(encoding="utf-8")
        return StyleSelection(
            style_id=str(chosen["slug"]),
            style_name=str(chosen["name"]),
            selection_reason="浅色、高对比度、专业风格适合自主学习和公式讲解",
            design_path=str(design_path.relative_to(self.vendor_dir)).replace("\\", "/"),
        )
