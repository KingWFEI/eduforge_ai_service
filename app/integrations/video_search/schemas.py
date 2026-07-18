from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class VideoCandidate(BaseModel):
    provider: str
    external_id: str
    title: str
    description: str = ""
    author: str = ""
    duration_seconds: int | None = None
    cover_url: str | None = None
    target_url: str
    tags: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    view_count: int | None = None
    danmaku_count: int | None = None
    raw_metadata: dict[str, Any] = Field(default_factory=dict, exclude=True)
    match_score: float = Field(default=0.0, ge=0.0, le=1.0)
    match_reason: str = ""

    @field_validator("external_id")
    @classmethod
    def valid_bvid(cls, value: str) -> str:
        if not value.startswith("BV") or not value[2:].isalnum() or len(value) < 10:
            raise ValueError("非法 BV 号")
        return value

    @field_validator("target_url")
    @classmethod
    def valid_target(cls, value: str) -> str:
        if not value.startswith("https://www.bilibili.com/video/BV"):
            raise ValueError("只允许 Bilibili 公开视频页面 URL")
        return value


class VideoSearchResult(BaseModel):
    status: str
    queries: list[str]
    primary_video: VideoCandidate | None = None
    alternatives: list[VideoCandidate] = Field(default_factory=list, max_length=3)
    reason: str | None = None
