from sqlalchemy.orm import Session

from app.services.rag_service import search_knowledge_chunks


class TutorRetrievalService:
    """Adapter from tutor terminology to the project's Chroma RAG service."""

    def __init__(self, db: Session):
        self.db = db

    async def search(
        self,
        course_id: str,
        section_id: str | None,
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        result = search_knowledge_chunks(
            db=self.db,
            course_id=course_id,
            query=query,
            top_k=top_k,
            chapter_id=section_id,
        )
        return result.get("items", [])

    @staticmethod
    def format_context(chunks: list[dict]) -> str:
        parts = []
        for index, chunk in enumerate(chunks, start=1):
            source = chunk.get("section") or "课程资料"
            content = chunk.get("content") or ""
            parts.append(f"【知识片段 {index}】\n来源：{source}\n{content}")
        return "\n\n".join(parts)
