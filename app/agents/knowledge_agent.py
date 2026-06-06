from typing import Any, Dict, List

from sqlalchemy import or_

from app.agents.base import BaseAgent
from app.models.course_structure import KnowledgeChunk, KnowledgePoint


class KnowledgeAgent(BaseAgent):
    """
    知识检索智能体。

    作用：
    根据 course_id 和 knowledge_point 从 knowledge_chunks 中取相关知识块。
    如果暂时没有知识块，则返回兜底知识。
    """

    name = "Knowledge Agent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        db = input_data["db"]
        course_id = input_data["course_id"]
        knowledge_point = input_data.get("knowledge_point") or ""

        kp = (
            db.query(KnowledgePoint)
            .filter(
                KnowledgePoint.course_id == course_id,
                KnowledgePoint.name == knowledge_point,
            )
            .first()
        )

        query = db.query(KnowledgeChunk).filter(
            KnowledgeChunk.course_id == course_id,
            KnowledgeChunk.deleted.is_(False),
        )

        if kp:
            query = query.filter(KnowledgeChunk.knowledge_point_id == kp.id)
        elif knowledge_point:
            query = query.filter(
                or_(
                    KnowledgeChunk.content.contains(knowledge_point),
                    KnowledgeChunk.section.contains(knowledge_point),
                )
            )

        chunks = (
            query
            .order_by(KnowledgeChunk.chunk_index.asc())
            .limit(5)
            .all()
        )

        knowledge_chunks: List[Dict[str, Any]] = []

        for chunk in chunks:
            knowledge_chunks.append({
                "chunk_id": chunk.id,
                "content": chunk.content,
                "section": chunk.section,
                "page_no": chunk.page_no,
                "knowledge_point_id": chunk.knowledge_point_id,
            })

        if not knowledge_chunks:
            knowledge_chunks = [
                {
                    "chunk_id": "fallback_001",
                    "content": f"{knowledge_point} 是当前学习主题。系统会结合学生画像，用更适合初学者的方式生成图解、练习、导图和代码案例。",
                    "section": "系统兜底知识",
                    "page_no": None,
                    "knowledge_point_id": kp.id if kp else None,
                }
            ]

        return {
            "knowledge_point_id": kp.id if kp else None,
            "knowledge_chunks": knowledge_chunks,
            "summary": f"已检索到 {len(knowledge_chunks)} 个知识片段"
        }
