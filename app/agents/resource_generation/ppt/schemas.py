from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class PptRequirement(BaseModel):
    purpose: str
    audience: str
    scope: Literal["section", "chapter", "course"]
    difficulty: str
    slide_count: int = Field(ge=3, le=20)
    density_mode: Literal["reading_first", "balanced", "presenter_first"] = "reading_first"
    focus_knowledge_points: list[str] = Field(default_factory=list)
    needs_visuals: bool = True
    needs_code: bool = False
    needs_examples: bool = True


class ContentBlock(BaseModel):
    type: Literal["paragraph", "bullets", "formula", "code", "callout", "table"] = "paragraph"
    title: str | None = None
    text: str | None = None
    items: list[str] = Field(default_factory=list, max_length=8)
    language: str | None = None

    @field_validator("text")
    @classmethod
    def limit_text(cls, value: str | None) -> str | None:
        if value and len(value) > 900:
            return value[:897] + "..."
        return value


class VisualSpec(BaseModel):
    type: str = "none"
    description: str = ""
    image_url: str | None = None


class PptSlide(BaseModel):
    slide_no: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=120)
    subtitle: str = Field(default="", max_length=180)
    layout: str = "content"
    learning_goal: str = Field(default="", max_length=240)
    content_blocks: list[ContentBlock] = Field(default_factory=list, max_length=6)
    visual_spec: VisualSpec = Field(default_factory=VisualSpec)
    notes: str = Field(default="", max_length=500)
    source_chunk_ids: list[str] = Field(default_factory=list)


class PptDeck(BaseModel):
    overview: str
    key_takeaways: list[str] = Field(min_length=1, max_length=8)
    slides: list[PptSlide] = Field(min_length=3, max_length=20)

    @model_validator(mode="after")
    def continuous_slide_numbers(self):
        expected = list(range(1, len(self.slides) + 1))
        actual = [slide.slide_no for slide in self.slides]
        if actual != expected:
            raise ValueError("slide_no 必须从 1 开始连续编号")
        return self


class StyleSelection(BaseModel):
    style_id: str
    style_name: str
    selection_reason: str
    design_path: str | None = None


class HtmlQualityResult(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)


class PptArtifacts(BaseModel):
    html_path: str
    cover_path: str
    thumbnail_paths: list[str] = Field(default_factory=list)
    quality: HtmlQualityResult
