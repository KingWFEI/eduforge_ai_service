from __future__ import annotations

from typing import Protocol

from app.integrations.video_search.schemas import VideoCandidate


class VideoSearchProvider(Protocol):
    async def search(self, query: str, *, page: int = 1, page_size: int = 20) -> list[VideoCandidate]: ...
