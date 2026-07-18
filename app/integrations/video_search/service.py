from __future__ import annotations

import asyncio
import logging
import time

from app.core.config import settings
from app.integrations.video_search.base import VideoSearchProvider
from app.integrations.video_search.cache import TtlCache
from app.integrations.video_search.providers.bilibili import BilibiliSearchProvider, VideoProviderError
from app.integrations.video_search.query_builder import VideoQueryBuilder
from app.integrations.video_search.ranking import CandidateSelectionGuard, VideoRanker
from app.integrations.video_search.schemas import VideoCandidate, VideoSearchResult


logger = logging.getLogger("app.integrations.video_search")


class VideoSearchService:
    def __init__(self, provider: VideoSearchProvider | None = None):
        self.provider = provider or BilibiliSearchProvider()
        self.query_builder = VideoQueryBuilder()
        self.ranker = VideoRanker()
        self.guard = CandidateSelectionGuard()
        self.cache: TtlCache[list[VideoCandidate]] = TtlCache(settings.VIDEO_SEARCH_CACHE_TTL_SECONDS)
        self._last_request_at = 0.0
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0

    async def search_for_state(self, state: dict) -> VideoSearchResult:
        if not settings.VIDEO_SEARCH_ENABLED:
            return VideoSearchResult(status="no_suitable_result", queries=[], reason="视频搜索未启用")
        queries = self.query_builder.build(state)
        candidates: list[VideoCandidate] = []
        errors: list[str] = []
        for query in queries:
            try:
                candidates.extend(await self._search_query(query))
            except VideoProviderError as exc:
                errors.append(str(exc))
                break
        deduplicated = {item.external_id: item for item in candidates}
        ranked = self.ranker.rank(list(deduplicated.values()), queries, state)
        ranked = [item for item in ranked if item.match_score >= settings.VIDEO_MIN_MATCH_SCORE]
        if not ranked:
            return VideoSearchResult(
                status="no_suitable_result",
                queries=queries,
                reason="；".join(errors) or "没有找到达到匹配阈值的公开视频",
            )
        selected = self.guard.select([item.external_id for item in ranked[:4]], ranked)
        return VideoSearchResult(status="completed", queries=queries, primary_video=selected[0], alternatives=selected[1:4])

    async def _search_query(self, query: str) -> list[VideoCandidate]:
        cached = self.cache.get(query)
        if cached is not None:
            return [item.model_copy(deep=True) for item in cached]
        if time.monotonic() < self._circuit_open_until:
            raise VideoProviderError("视频 Provider 熔断中")
        delay = max(settings.VIDEO_SEARCH_RATE_LIMIT - (time.monotonic() - self._last_request_at), 0.0)
        if delay:
            await asyncio.sleep(delay)
        for attempt in range(settings.VIDEO_MAX_RETRIES + 1):
            try:
                self._last_request_at = time.monotonic()
                result = await asyncio.wait_for(
                    self.provider.search(query, page=1, page_size=settings.VIDEO_SEARCH_MAX_RESULTS),
                    timeout=settings.VIDEO_SEARCH_TIMEOUT_SECONDS + 1,
                )
                self._consecutive_failures = 0
                self.cache.set(query, [item.model_copy(deep=True) for item in result])
                return result
            except asyncio.TimeoutError:
                error = VideoProviderError("视频 Provider 请求超时")
            except VideoProviderError as exc:
                error = exc
                # Platform rejection should not be hammered with retries.
                if "拒绝" in str(exc):
                    raise
            except Exception:
                logger.exception("unexpected video provider failure")
                error = VideoProviderError("视频 Provider 异常")
            if attempt < settings.VIDEO_MAX_RETRIES:
                await asyncio.sleep(min(2 ** attempt, 4))
        self._consecutive_failures += 1
        if self._consecutive_failures >= 3:
            self._circuit_open_until = time.monotonic() + 60
        raise error
