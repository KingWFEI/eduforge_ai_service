from __future__ import annotations

import json
from collections import defaultdict

from app.agents.resource_generation.mind_map.schemas import (
    CrossChapterRelation,
    IntraChapterRelation,
    MindMapNode,
    RelatedChapter,
)
from app.core.config import settings


RELATION_LABELS = {
    "prerequisite": "前置知识",
    "foundation_for": "作为基础",
    "derived_from": "推导自",
    "used_by": "被用于",
    "contrasts_with": "形成对比",
    "similar_to": "概念相似",
    "extends": "进一步扩展",
    "solves_problem_of": "解决其问题",
    "implementation_of": "具体实现",
    "example_of": "作为示例",
    "calculation_basis": "计算基础",
    "evaluation_of": "用于评估",
}


class CourseRelationMindMapService:
    def generate(self, state: dict) -> dict:
        structure = state.get("course_structure") or {}
        chapters = structure.get("chapters") or []
        current_chapter_id = str(state.get("chapter_id") or (state.get("current_chapter_context") or {}).get("id") or "")
        current = next((chapter for chapter in chapters if str(chapter.get("id")) == current_chapter_id), None)
        if current is None:
            raise ValueError("当前章节不在课程结构中")
        chapter_nodes = self._chapter_nodes(current, chapters)
        current_points = self._points_for_chapter(current, chapters)
        other_points = [
            (chapter, point)
            for chapter in chapters
            if str(chapter.get("id")) != current_chapter_id and not self._is_child(chapter, current_chapter_id)
            for point in chapter.get("knowledge_points") or []
        ]
        evidence = self._evidence_by_point(state.get("retrieved_chunks") or [])
        intra = self._intra_relations(current_points, evidence)
        cross = self._cross_relations(current, current_points, other_points, evidence)
        related = self._related_chapters(cross)
        tree = MindMapNode(title=str(current.get("title") or "当前章节"), children=chapter_nodes)
        course = structure.get("course") or {}
        section = state.get("current_section_context") or {}
        takeaways = [relation.reason for relation in [*intra[:2], *cross[:2]]]
        if not takeaways:
            takeaways = [f"掌握{current.get('title') or '当前章节'}的知识层级"]
        content = {
            "overview": f"以{current.get('title')}章节为核心，展示章节知识结构、章内关系和跨章节关系",
            "key_takeaways": takeaways,
            "scope": {
                "course_id": state.get("course_id"),
                "course_title": course.get("name"),
                "current_chapter_id": current_chapter_id,
                "current_chapter_title": current.get("title"),
                "current_section_id": state.get("section_id"),
                "current_section_title": section.get("title"),
            },
            "current_chapter_tree": tree.model_dump(exclude_none=True),
            "intra_chapter_relations": [item.model_dump() for item in intra],
            "cross_chapter_relations": [item.model_dump() for item in cross],
            "related_chapters": [item.model_dump() for item in related],
            "visualization": None,
        }
        # Compatibility is derived, never persisted independently by a second generator.
        content["tree"] = content["current_chapter_tree"]
        return {
            "type": "mind_map",
            "title": f"{current.get('title')}课程关系导图",
            "overview": content["overview"],
            "content_text": content["overview"],
            "content_json": content,
            "source": "课程结构 + 分层课程知识检索",
            "source_type": "generated",
            "generation_mode": "course_relation_map",
            "source_references": [item for values in evidence.values() for item in values],
            "status": "completed",
        }

    def _chapter_nodes(self, current: dict, chapters: list[dict]) -> list[MindMapNode]:
        children = [item for item in chapters if str(item.get("parent_id") or "") == str(current.get("id"))]
        if not children:
            return [
                MindMapNode(title=str(point.get("name")), knowledge_point_id=str(point.get("id")))
                for point in (current.get("knowledge_points") or [])[: settings.MIND_MAP_MAX_CHILDREN]
            ]
        result: list[MindMapNode] = []
        for child in children[: settings.MIND_MAP_MAX_CHILDREN]:
            points = [
                MindMapNode(title=str(point.get("name")), knowledge_point_id=str(point.get("id")))
                for point in (child.get("knowledge_points") or [])[: settings.MIND_MAP_MAX_CHILDREN]
            ]
            result.append(MindMapNode(title=str(child.get("title")), children=points))
        return result

    def _points_for_chapter(self, current: dict, chapters: list[dict]) -> list[dict]:
        points = list(current.get("knowledge_points") or [])
        for chapter in chapters:
            if self._is_child(chapter, str(current.get("id"))):
                points.extend(chapter.get("knowledge_points") or [])
        return points

    @staticmethod
    def _is_child(chapter: dict, parent_id: str) -> bool:
        return str(chapter.get("parent_id") or "") == str(parent_id)

    @staticmethod
    def _evidence_by_point(chunks: list[dict]) -> dict[str, list[str]]:
        evidence: dict[str, list[str]] = defaultdict(list)
        for chunk in chunks:
            point_id = str(chunk.get("knowledge_point_id") or "")
            chunk_id = str(chunk.get("chunk_id") or "")
            if point_id and chunk_id and chunk_id not in evidence[point_id]:
                evidence[point_id].append(chunk_id)
        return evidence

    def _intra_relations(self, points: list[dict], evidence: dict[str, list[str]]) -> list[IntraChapterRelation]:
        by_id = {str(point.get("id")): point for point in points if point.get("id")}
        relations: list[IntraChapterRelation] = []
        seen: set[tuple[str, str, str]] = set()
        for target in points:
            target_id = str(target.get("id") or "")
            prerequisites = target.get("prerequisites_json") or []
            if isinstance(prerequisites, str):
                try:
                    prerequisites = json.loads(prerequisites)
                except json.JSONDecodeError:
                    prerequisites = []
            for source_id in prerequisites:
                source_id = str(source_id)
                if source_id not in by_id or source_id == target_id:
                    continue
                chunk_ids = list(dict.fromkeys(evidence.get(source_id, []) + evidence.get(target_id, [])))
                if not chunk_ids:
                    continue
                key = (source_id, target_id, "prerequisite")
                if key in seen:
                    continue
                seen.add(key)
                source = by_id[source_id]
                relations.append(IntraChapterRelation(
                    source_knowledge_point_id=source_id,
                    source_title=str(source.get("name")),
                    target_knowledge_point_id=target_id,
                    target_title=str(target.get("name")),
                    relation_type="prerequisite",
                    relation_label=RELATION_LABELS["prerequisite"],
                    reason=f"{source.get('name')}是理解{target.get('name')}的前置知识",
                    strength=0.9,
                    source_chunk_ids=chunk_ids[:5],
                ))
        return [item for item in relations if item.strength >= settings.MIND_MAP_MIN_RELATION_STRENGTH][: settings.MIND_MAP_MAX_INTRA_RELATIONS]

    def _cross_relations(self, current: dict, current_points: list[dict], other_points: list[tuple[dict, dict]], evidence: dict[str, list[str]]) -> list[CrossChapterRelation]:
        relations: list[CrossChapterRelation] = []
        for source in current_points:
            source_id = str(source.get("id") or "")
            source_name = str(source.get("name") or "")
            for chapter, target in other_points:
                target_id = str(target.get("id") or "")
                target_name = str(target.get("name") or "")
                combined = source_name + str(current.get("title") or "") + target_name
                if "决策树" in combined and any(word in target_name + str(chapter.get("title") or "") for word in ("随机森林", "集成学习")):
                    relation_type, strength = "foundation_for", 0.88
                elif source_name and source_name in target_name or target_name and target_name in source_name:
                    relation_type, strength = "extends", 0.72
                else:
                    continue
                chunk_ids = list(dict.fromkeys(evidence.get(source_id, []) + evidence.get(target_id, [])))
                if not chunk_ids:
                    continue
                relations.append(CrossChapterRelation(
                    source_knowledge_point_id=source_id,
                    source_title=source_name,
                    target_chapter_id=str(chapter.get("id")),
                    target_chapter_title=str(chapter.get("title")),
                    target_knowledge_point_id=target_id,
                    target_title=target_name,
                    relation_type=relation_type,
                    relation_label=RELATION_LABELS[relation_type],
                    reason=f"{source_name}与{target_name}构成跨章节的{RELATION_LABELS[relation_type]}关系",
                    strength=strength,
                    source_chunk_ids=chunk_ids[:6],
                ))
        unique: dict[tuple[str, str, str], CrossChapterRelation] = {}
        for item in relations:
            key = (item.source_knowledge_point_id, item.target_knowledge_point_id, item.relation_type)
            if item.strength >= settings.MIND_MAP_MIN_RELATION_STRENGTH:
                unique[key] = item
        return sorted(unique.values(), key=lambda item: item.strength, reverse=True)[: settings.MIND_MAP_MAX_CROSS_RELATIONS]

    def _related_chapters(self, relations: list[CrossChapterRelation]) -> list[RelatedChapter]:
        grouped: dict[str, list[CrossChapterRelation]] = defaultdict(list)
        for relation in relations:
            grouped[relation.target_chapter_id].append(relation)
        result = [
            RelatedChapter(
                chapter_id=chapter_id,
                chapter_title=items[0].target_chapter_title,
                relation_summary="；".join(item.reason for item in items[:2]),
                relevance_score=max(item.strength for item in items),
            )
            for chapter_id, items in grouped.items()
        ]
        return sorted(result, key=lambda item: item.relevance_score, reverse=True)[: settings.MIND_MAP_MAX_RELATED_CHAPTERS]
