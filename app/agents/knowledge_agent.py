from typing import Any, Dict, List

from sqlalchemy import or_

from app.agents.base import BaseAgent
from app.models.course_structure import KnowledgeChunk, KnowledgePoint


class KnowledgeAgent(BaseAgent):
    """Retrieve real course chunks for resource generation."""

    name = "Knowledge Agent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        db = input_data["db"]
        course_id = input_data["course_id"]
        knowledge_point = input_data.get("knowledge_point") or ""

        kp = self._find_knowledge_point(db, course_id, knowledge_point)
        chunks = self._load_chunks(db, course_id, knowledge_point, kp)

        knowledge_chunks: List[Dict[str, Any]] = []
        for chunk in chunks:
            knowledge_chunks.append({
                "chunk_id": chunk.id,
                "content": chunk.content,
                "section": chunk.section,
                "page_no": chunk.page_no,
                "chapter_id": chunk.chapter_id,
                "knowledge_point_id": chunk.knowledge_point_id,
            })

        if not knowledge_chunks:
            raise RuntimeError(
                "未找到真实课程知识块，请先上传课程资料，确认 AI 识别出的章节和知识点，并重建索引后再生成学习资源。"
            )

        return {
            "knowledge_point_id": kp.id if kp else None,
            "knowledge_chunks": knowledge_chunks,
            "summary": f"已检索到 {len(knowledge_chunks)} 个真实知识片段",
        }

    def _find_knowledge_point(self, db, course_id: str, knowledge_point: str):
        if not knowledge_point:
            return None

        exact = (
            db.query(KnowledgePoint)
            .filter(
                KnowledgePoint.course_id == course_id,
                KnowledgePoint.name == knowledge_point,
            )
            .first()
        )
        if exact is not None:
            return exact

        return (
            db.query(KnowledgePoint)
            .filter(
                KnowledgePoint.course_id == course_id,
                KnowledgePoint.name.contains(knowledge_point),
            )
            .first()
        )

    def _load_chunks(
        self,
        db,
        course_id: str,
        knowledge_point: str,
        kp,
    ) -> list[KnowledgeChunk]:
        base_query = db.query(KnowledgeChunk).filter(
            KnowledgeChunk.course_id == course_id,
            KnowledgeChunk.deleted.is_(False),
        )

        if kp:
            chunks = self._limit(
                base_query.filter(KnowledgeChunk.knowledge_point_id == kp.id)
            )
            if chunks:
                return chunks

            chunks = self._limit(
                base_query.filter(
                    or_(
                        KnowledgeChunk.content.contains(kp.name),
                        KnowledgeChunk.section.contains(kp.name),
                    )
                )
            )
            if chunks:
                return chunks

            if kp.chapter_id:
                chunks = self._limit(
                    base_query.filter(KnowledgeChunk.chapter_id == kp.chapter_id)
                )
                if chunks:
                    return chunks

        if knowledge_point:
            chunks = self._limit(
                base_query.filter(
                    or_(
                        KnowledgeChunk.content.contains(knowledge_point),
                        KnowledgeChunk.section.contains(knowledge_point),
                    )
                )
            )
            if chunks:
                return chunks

        return self._limit(base_query)

    def _limit(self, query) -> list[KnowledgeChunk]:
        return (
            query
            .order_by(KnowledgeChunk.chunk_index.asc())
            .limit(5)
            .all()
        )
