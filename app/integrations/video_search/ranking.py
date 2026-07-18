from __future__ import annotations

import math
import re
from datetime import datetime, timezone

from app.integrations.video_search.schemas import VideoCandidate


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{2,}", text)}


class VideoRanker:
    def rank(self, candidates: list[VideoCandidate], queries: list[str], state: dict) -> list[VideoCandidate]:
        query_tokens = _tokens(" ".join(queries))
        profile = state.get("student_profile") or {}
        preferences = str(profile.get("learning_preferences_json") or "")
        for candidate in candidates:
            candidate_tokens = _tokens(" ".join([candidate.title, candidate.description, *candidate.tags]))
            overlap = len(query_tokens & candidate_tokens) / max(len(query_tokens), 1)
            semantic_relevance = min(1.0, overlap * 2.4)
            coverage = min(1.0, overlap * 2.0)
            difficulty_fit = 0.8 if any(word in candidate.title for word in ("入门", "基础", "初学", "详解")) else 0.6
            profile_fit = 0.8 if any(word in candidate.title for word in ("动画", "可视化", "案例", "实战", "Python")) and preferences else 0.6
            teaching_quality = min(1.0, 0.45 + math.log10(max(candidate.view_count or 0, 1)) / 12)
            freshness = self._freshness(candidate)
            score = (
                semantic_relevance * 0.40 + coverage * 0.20 + difficulty_fit * 0.15
                + profile_fit * 0.10 + teaching_quality * 0.10 + freshness * 0.05
            )
            candidate.match_score = round(min(max(score, 0.0), 1.0), 4)
            candidate.match_reason = "标题、简介与当前知识点匹配，且难度和教学形式适合当前画像"
        return sorted(candidates, key=lambda item: item.match_score, reverse=True)

    @staticmethod
    def _freshness(candidate: VideoCandidate) -> float:
        if candidate.published_at is None:
            return 0.5
        published = candidate.published_at
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        years = max((datetime.now(timezone.utc) - published).days / 365.0, 0.0)
        return max(0.2, 1.0 - years / 10.0)


class CandidateSelectionGuard:
    """Rehydrates an agent selection from provider data so immutable metadata cannot be forged."""

    def select(self, candidate_ids: list[str], candidates: list[VideoCandidate]) -> list[VideoCandidate]:
        source = {item.external_id: item for item in candidates}
        if any(candidate_id not in source for candidate_id in candidate_ids):
            raise ValueError("智能体选择了候选列表之外的视频")
        return [source[candidate_id] for candidate_id in candidate_ids]
