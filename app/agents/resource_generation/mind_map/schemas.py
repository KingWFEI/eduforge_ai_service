from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


RelationType = Literal[
    "prerequisite", "foundation_for", "derived_from", "used_by", "contrasts_with",
    "similar_to", "extends", "solves_problem_of", "implementation_of", "example_of",
    "calculation_basis", "evaluation_of",
]


class MindMapNode(BaseModel):
    title: str
    knowledge_point_id: str | None = None
    children: list["MindMapNode"] = Field(default_factory=list)


class IntraChapterRelation(BaseModel):
    source_knowledge_point_id: str
    source_title: str
    target_knowledge_point_id: str
    target_title: str
    relation_type: RelationType
    relation_label: str
    direction: Literal["source_to_target", "target_to_source", "bidirectional"] = "source_to_target"
    reason: str
    strength: float = Field(ge=0.0, le=1.0)
    source_chunk_ids: list[str] = Field(default_factory=list)


class CrossChapterRelation(BaseModel):
    source_knowledge_point_id: str
    source_title: str
    target_chapter_id: str
    target_chapter_title: str
    target_knowledge_point_id: str
    target_title: str
    relation_type: RelationType
    relation_label: str
    direction: Literal["source_to_target", "target_to_source", "bidirectional"] = "source_to_target"
    reason: str
    strength: float = Field(ge=0.0, le=1.0)
    source_chunk_ids: list[str] = Field(default_factory=list)


class RelatedChapter(BaseModel):
    chapter_id: str
    chapter_title: str
    relation_summary: str
    relevance_score: float = Field(ge=0.0, le=1.0)
