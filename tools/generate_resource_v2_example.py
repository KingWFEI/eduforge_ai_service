"""Generate the deterministic validation deck used by the resource-generation v2 handoff."""

from __future__ import annotations

import json

from app.agents.resource_generation.mind_map.service import CourseRelationMindMapService
from app.agents.resource_generation.ppt.service import PptGenerationService
from app.core.config import settings


def validation_state() -> dict:
    return {
        "task_id": "example-decision-tree-20260718",
        "resource_id": "res_example_decision_tree",
        "course_id": "course_machine_learning",
        "chapter_id": "chapter_decision_tree",
        "section_id": "section_entropy_gain",
        "knowledge_point_ids": ["kp_entropy", "kp_gain", "kp_id3", "kp_split"],
        "generation_scope": "section",
        "user_request": "面向数学基础较弱、偏好图解和代码的学生生成互动课件",
        "difficulty": "基础到中等",
        "student_profile": {
            "course_level": "一般",
            "math_level": "较弱",
            "learning_preferences_json": ["visual", "code", "example_based"],
            "weaknesses_json": ["信息熵计算"],
        },
        "target_knowledge_points": [
            {"id": "kp_entropy", "name": "信息熵"},
            {"id": "kp_gain", "name": "信息增益"},
            {"id": "kp_id3", "name": "ID3"},
            {"id": "kp_split", "name": "决策树分裂"},
        ],
        "current_chapter_context": {"id": "chapter_decision_tree", "title": "决策树"},
        "current_section_context": {"id": "section_entropy_gain", "title": "信息熵与信息增益"},
        "resource_plan": {"generation_strategy": {"slide_count": 7, "density_mode": "reading_first"}},
        "course_structure": {
            "course": {"id": "course_machine_learning", "name": "机器学习"},
            "chapters": [
                {"id": "chapter_decision_tree", "parent_id": None, "level": 1, "title": "决策树", "knowledge_points": []},
                {
                    "id": "section_entropy_gain", "parent_id": "chapter_decision_tree", "level": 2,
                    "title": "信息熵与信息增益",
                    "knowledge_points": [
                        {"id": "kp_entropy", "name": "信息熵", "prerequisites_json": []},
                        {"id": "kp_gain", "name": "信息增益", "prerequisites_json": ["kp_entropy"]},
                        {"id": "kp_id3", "name": "ID3", "prerequisites_json": ["kp_gain"]},
                        {"id": "kp_split", "name": "决策树分裂", "prerequisites_json": ["kp_gain"]},
                    ],
                },
                {
                    "id": "chapter_ensemble", "parent_id": None, "level": 1, "title": "集成学习",
                    "knowledge_points": [{"id": "kp_forest", "name": "随机森林", "prerequisites_json": []}],
                },
            ],
        },
        "retrieved_chunks": [
            {
                "chunk_id": "chunk_entropy", "document_id": "doc_ml", "chapter_id": "section_entropy_gain",
                "knowledge_point_id": "kp_entropy", "content": "信息熵 H(D)=-Σ p_k log2(p_k)，用于衡量样本集合的不确定性。"
            },
            {
                "chunk_id": "chunk_gain", "document_id": "doc_ml", "chapter_id": "section_entropy_gain",
                "knowledge_point_id": "kp_gain", "content": "信息增益等于划分前的信息熵减去按子集占比加权后的条件熵。"
            },
            {
                "chunk_id": "chunk_id3", "document_id": "doc_ml", "chapter_id": "section_entropy_gain",
                "knowledge_point_id": "kp_id3", "content": "ID3 在每个节点选择信息增益最大的特征完成数据划分。"
            },
            {
                "chunk_id": "chunk_split", "document_id": "doc_ml", "chapter_id": "section_entropy_gain",
                "knowledge_point_id": "kp_split", "content": "计算示例：比较多个候选特征的条件熵，选择信息增益最大的特征作为分裂条件。"
            },
            {
                "chunk_id": "chunk_forest", "document_id": "doc_ml", "chapter_id": "chapter_ensemble",
                "knowledge_point_id": "kp_forest", "content": "随机森林以决策树为基础学习器，通过多棵树投票缓解决策树过拟合。"
            },
        ],
        "current_chapter_knowledge_points": [
            {"id": "kp_entropy", "name": "信息熵"}, {"id": "kp_gain", "name": "信息增益"},
            {"id": "kp_id3", "name": "ID3"}, {"id": "kp_split", "name": "决策树分裂"},
        ],
    }


def main() -> None:
    state = validation_state()
    deck = PptGenerationService().generate(state)
    mind_map = CourseRelationMindMapService().generate(state)
    output = settings.GENERATED_RESOURCE_DIR / "examples" / "decision-tree-validation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "ppt": {
                    "title": deck["title"],
                    "artifacts": deck["artifacts"],
                    "visualization": deck["content_json"]["visualization"],
                    "quality_metrics": deck["quality_metrics"],
                },
                "mind_map": mind_map["content_json"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(output.resolve())
    print(deck["artifacts"]["html_path"])
    print(deck["artifacts"]["cover_path"])
    print(len(deck["content_json"]["slides"]))
    print(len(mind_map["content_json"]["intra_chapter_relations"]))
    print(len(mind_map["content_json"]["cross_chapter_relations"]))


if __name__ == "__main__":
    main()
