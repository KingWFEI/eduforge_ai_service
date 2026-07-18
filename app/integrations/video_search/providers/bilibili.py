from __future__ import annotations

import asyncio
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from app.core.config import settings
from app.integrations.video_search.schemas import VideoCandidate


logger = logging.getLogger("app.integrations.video_search.bilibili")


class VideoProviderError(RuntimeError):
    pass


class BilibiliSearchProvider:
    SEARCH_URL = "https://api.bilibili.com/x/web-interface/search/type"

    async def search(self, query: str, *, page: int = 1, page_size: int = 20) -> list[VideoCandidate]:
        return await asyncio.to_thread(self._search_sync, query, page, min(page_size, 50))

    def _search_sync(self, query: str, page: int, page_size: int) -> list[VideoCandidate]:
        params = urllib.parse.urlencode(
            {"search_type": "video", "keyword": query, "page": page, "page_size": page_size}
        )
        request = urllib.request.Request(
            f"{self.SEARCH_URL}?{params}",
            headers={"User-Agent": "EduForgeAI/1.0 public-education-video-search"},
        )
        logger.info("video search provider request | provider=bilibili | query=%s", query)
        try:
            with urllib.request.urlopen(request, timeout=settings.VIDEO_SEARCH_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            logger.warning("bilibili search rejected | status=%s", exc.code)
            raise VideoProviderError(f"Bilibili 拒绝公开搜索请求：HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            logger.warning("bilibili search failed | error=%s", exc)
            raise VideoProviderError("Bilibili 公开搜索暂时不可用") from exc
        if payload.get("code") != 0:
            raise VideoProviderError(f"Bilibili 返回错误：{payload.get('message') or payload.get('code')}")
        results = ((payload.get("data") or {}).get("result") or [])
        candidates: list[VideoCandidate] = []
        for item in results:
            bvid = str(item.get("bvid") or "")
            if not re.fullmatch(r"BV[A-Za-z0-9]{8,20}", bvid):
                continue
            title = re.sub(r"<[^>]+>", "", str(item.get("title") or "")).strip()
            if not title:
                continue
            published = item.get("pubdate")
            candidates.append(
                VideoCandidate(
                    provider="bilibili",
                    external_id=bvid,
                    title=title,
                    description=re.sub(r"<[^>]+>", "", str(item.get("description") or ""))[:1000],
                    author=str(item.get("author") or ""),
                    duration_seconds=self._duration(item.get("duration")),
                    cover_url=self._https_url(item.get("pic")),
                    target_url=f"https://www.bilibili.com/video/{bvid}",
                    tags=[tag for tag in str(item.get("tag") or "").split(",") if tag],
                    published_at=datetime.fromtimestamp(int(published), tz=timezone.utc) if published else None,
                    view_count=self._integer(item.get("play")),
                    danmaku_count=self._integer(item.get("video_review")),
                    raw_metadata={"typeid": item.get("typeid"), "typename": item.get("typename")},
                )
            )
        return candidates

    @staticmethod
    def _duration(value) -> int | None:
        parts = str(value or "").split(":")
        if not all(part.isdigit() for part in parts):
            return None
        seconds = 0
        for part in parts:
            seconds = seconds * 60 + int(part)
        return seconds

    @staticmethod
    def _integer(value) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _https_url(value) -> str | None:
        url = str(value or "").strip()
        if url.startswith("//"):
            return "https:" + url
        return url if url.startswith("https://") else None
