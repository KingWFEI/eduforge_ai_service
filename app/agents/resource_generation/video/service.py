from __future__ import annotations

from datetime import datetime, timezone

from app.integrations.video_search.service import VideoSearchService


class ExternalVideoGenerationService:
    def __init__(self, search_service: VideoSearchService | None = None):
        self.search_service = search_service or VideoSearchService()

    async def generate(self, state: dict) -> dict:
        result = await self.search_service.search_for_state(state)
        if result.status != "completed" or result.primary_video is None:
            return {"type": "video", "status": "no_suitable_result", "reason": result.reason, "queries": result.queries}
        primary = result.primary_video.model_dump(mode="json", exclude={"raw_metadata"})
        alternatives = [item.model_dump(mode="json", exclude={"raw_metadata"}) for item in result.alternatives]
        points = [item.get("name") for item in (state.get("target_knowledge_points") or []) if item.get("name")]
        overview = "精选教学视频帮助学生理解" + ("、".join(points) if points else "当前课程内容")
        content_json = {
            "overview": overview,
            "key_takeaways": points[:5] or ["通过公开视频巩固当前知识点"],
            "video_mode": "external_video",
            "provider": "bilibili",
            "primary_video": primary,
            "alternatives": alternatives,
            "search_context": {
                "queries": result.queries,
                "course_id": state.get("course_id"),
                "chapter_id": state.get("chapter_id"),
                "section_id": state.get("section_id"),
                "knowledge_point_ids": state.get("knowledge_point_ids") or [],
                "searched_at": datetime.now(timezone.utc).isoformat(),
            },
            "visualization": {
                "renderer": "external_link",
                "video_url": primary["target_url"],
                "thumbnail_url": primary.get("cover_url"),
                "mime_type": "text/html",
            },
        }
        return {
            "type": "video",
            "title": primary["title"],
            "overview": overview,
            "content_text": primary.get("description"),
            "content_json": content_json,
            "source": primary["target_url"],
            "source_type": "external",
            "generation_mode": "external_video",
            "external_provider": "bilibili",
            "external_id": primary["external_id"],
            "preview_url": primary.get("cover_url"),
            "status": "completed",
        }
