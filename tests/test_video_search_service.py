import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.core.config import settings
from app.integrations.video_search.ranking import CandidateSelectionGuard
from app.integrations.video_search.schemas import VideoCandidate
from app.integrations.video_search.service import VideoSearchService


def candidate(bvid: str, title: str) -> VideoCandidate:
    return VideoCandidate(
        provider="bilibili",
        external_id=bvid,
        title=title,
        description="信息熵 信息增益 决策树 初学者讲解",
        author="公开课程作者",
        duration_seconds=600,
        cover_url="https://i0.hdslb.com/example.jpg",
        target_url=f"https://www.bilibili.com/video/{bvid}",
        tags=["机器学习", "决策树"],
        published_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        view_count=10000,
    )


class MockVideoProvider:
    def __init__(self, results):
        self.results = results
        self.calls = 0

    async def search(self, query: str, *, page: int = 1, page_size: int = 20):
        self.calls += 1
        return [item.model_copy(deep=True) for item in self.results]


class VideoSearchTests(unittest.IsolatedAsyncioTestCase):
    async def test_multi_query_dedup_ranking_and_cache(self):
        provider = MockVideoProvider([
            candidate("BV1AA411C7AA", "信息熵与决策树入门详解"),
            candidate("BV1AA411C7AA", "重复候选"),
            candidate("BV1BB411C7BB", "信息增益计算例题"),
        ])
        service = VideoSearchService(provider)
        state = {
            "course_structure": {"course": {"name": "机器学习"}},
            "current_chapter_context": {"title": "决策树"},
            "current_section_context": {"title": "信息熵与信息增益"},
            "target_knowledge_points": [{"name": "信息熵"}],
            "student_profile": {"learning_preferences_json": ["visual"]},
        }
        with patch.object(settings, "VIDEO_MIN_MATCH_SCORE", 0.0), patch.object(settings, "VIDEO_SEARCH_RATE_LIMIT", 0.0):
            first = await service.search_for_state(state)
            calls_after_first = provider.calls
            second = await service.search_for_state(state)
        self.assertEqual(first.status, "completed")
        selected = [first.primary_video.external_id, *[item.external_id for item in first.alternatives]]
        self.assertEqual(len(selected), len(set(selected)))
        self.assertEqual(provider.calls, calls_after_first)
        self.assertEqual(second.primary_video.external_id, first.primary_video.external_id)

    async def test_empty_results_never_fabricate_url(self):
        service = VideoSearchService(MockVideoProvider([]))
        with patch.object(settings, "VIDEO_SEARCH_RATE_LIMIT", 0.0):
            result = await service.search_for_state({"course_structure": {"course": {"name": "机器学习"}}})
        self.assertEqual(result.status, "no_suitable_result")
        self.assertIsNone(result.primary_video)

    def test_selection_guard_rejects_non_candidate(self):
        with self.assertRaises(ValueError):
            CandidateSelectionGuard().select(["BV1ZZ411C7ZZ"], [candidate("BV1AA411C7AA", "候选")])


if __name__ == "__main__":
    unittest.main()
