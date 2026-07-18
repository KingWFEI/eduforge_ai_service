from __future__ import annotations


class VideoQueryBuilder:
    def build(self, state: dict) -> list[str]:
        course = (state.get("course_structure") or {}).get("course", {})
        chapter = state.get("current_chapter_context") or {}
        section = state.get("current_section_context") or {}
        points = [
            str(item.get("name") or item.get("title"))
            for item in (state.get("target_knowledge_points") or [])
            if isinstance(item, dict) and (item.get("name") or item.get("title"))
        ]
        topic = " ".join(filter(None, [course.get("name"), chapter.get("title"), section.get("title")])).strip()
        queries = [f"{topic} 初学者讲解".strip()]
        queries.extend(f"{point} 计算例题" for point in points[:2])
        if points:
            queries.append(f"{points[0]} 可视化 原理")
        user_request = str(state.get("user_request") or "").strip()
        if user_request:
            queries.append(f"{topic} {user_request[:40]}".strip())
        result: list[str] = []
        for query in queries:
            normalized = " ".join(query.split())
            if normalized and normalized not in result:
                result.append(normalized)
        return result[:5]
