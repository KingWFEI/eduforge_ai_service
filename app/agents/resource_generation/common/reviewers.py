from __future__ import annotations

from pydantic import BaseModel, Field


class ReviewResult(BaseModel):
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    dimension_scores: dict[str, float] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)
    retry_instruction: str | None = None


class BaseResourceReviewer:
    def review(self, resource: dict, state: dict) -> ReviewResult:
        content = resource.get("content_json") or {}
        issues = [field for field in ("overview", "key_takeaways", "visualization") if field not in content]
        return self._result(issues)

    @staticmethod
    def _result(issues: list[str], dimensions: dict[str, float] | None = None) -> ReviewResult:
        score = max(0.0, 1.0 - len(issues) * 0.18)
        return ReviewResult(
            passed=not issues,
            score=score,
            dimension_scores=dimensions or {
                "correctness": score,
                "completeness": score,
                "personalization": score,
                "source_grounding": score,
                "render_quality": score,
            },
            issues=issues,
            retry_instruction="；".join(issues) if issues else None,
        )


class IllustrationReviewer(BaseResourceReviewer):
    pass


class DocumentReviewer(BaseResourceReviewer):
    pass


class ExerciseReviewer(BaseResourceReviewer):
    pass


class CodeCaseReviewer(BaseResourceReviewer):
    pass


class PptReviewer(BaseResourceReviewer):
    def review(self, resource: dict, state: dict) -> ReviewResult:
        content = resource.get("content_json") or {}
        visualization = content.get("visualization") or {}
        issues: list[str] = []
        if visualization.get("renderer") != "frontend_slides_html":
            issues.append("PPT renderer 必须为 frontend_slides_html")
        if visualization.get("aspect_ratio") != "16:9":
            issues.append("PPT 必须保持 16:9")
        if not visualization.get("html_url"):
            issues.append("缺少 html_url")
        if not visualization.get("cover_url"):
            issues.append("缺少 cover_url")
        if not content.get("slides"):
            issues.append("课件无页面")
        sourced_slides = [slide for slide in content.get("slides") or [] if slide.get("source_chunk_ids")]
        if not sourced_slides:
            issues.append("课件缺少课程资料来源")
        return self._result(issues)


class VideoReviewer(BaseResourceReviewer):
    def review(self, resource: dict, state: dict) -> ReviewResult:
        if resource.get("status") == "no_suitable_result":
            return ReviewResult(passed=True, score=1.0, dimension_scores={}, issues=[])
        content = resource.get("content_json") or {}
        primary = content.get("primary_video") or {}
        issues: list[str] = []
        external_id = str(primary.get("external_id") or "")
        target_url = str(primary.get("target_url") or "")
        if not external_id.startswith("BV"):
            issues.append("非法 BV 号")
        if target_url != f"https://www.bilibili.com/video/{external_id}":
            issues.append("视频 URL 与候选 BV 号不一致")
        if content.get("visualization", {}).get("video_url") != target_url:
            issues.append("兼容 video_url 与 Provider URL 不一致")
        return self._result(issues)


class MindMapReviewer(BaseResourceReviewer):
    def review(self, resource: dict, state: dict) -> ReviewResult:
        content = resource.get("content_json") or {}
        issues: list[str] = []
        if content.get("tree") != content.get("current_chapter_tree"):
            issues.append("tree 兼容字段必须派生自 current_chapter_tree")
        current_ids = {
            str(point.get("id")) for point in (state.get("current_chapter_knowledge_points") or []) if point.get("id")
        }
        for relation in content.get("intra_chapter_relations") or []:
            if current_ids and ({str(relation.get("source_knowledge_point_id")), str(relation.get("target_knowledge_point_id"))} - current_ids):
                issues.append("章内关系包含其他章节知识点")
            if relation.get("source_knowledge_point_id") == relation.get("target_knowledge_point_id"):
                issues.append("章内关系存在自环")
            if not relation.get("source_chunk_ids"):
                issues.append("章内关系缺少来源")
        for relation in content.get("cross_chapter_relations") or []:
            if current_ids and str(relation.get("target_knowledge_point_id")) in current_ids:
                issues.append("跨章关系目标仍在当前章节")
            if not relation.get("source_chunk_ids"):
                issues.append("跨章关系缺少来源")
        return self._result(list(dict.fromkeys(issues)))


REVIEWERS = {
    "illustration": IllustrationReviewer,
    "document": DocumentReviewer,
    "mind_map": MindMapReviewer,
    "exercise": ExerciseReviewer,
    "code_case": CodeCaseReviewer,
    "video": VideoReviewer,
    "ppt": PptReviewer,
}


def reviewer_for(resource_type: str) -> BaseResourceReviewer:
    try:
        return REVIEWERS[resource_type]()
    except KeyError as exc:
        raise ValueError(f"不支持的资源审核类型：{resource_type}") from exc
