from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.knowledge import KnowledgeSearchRequest, KnowledgeSearchResponse, KnowledgeAskRequest, KnowledgeAskResponse
from app.services.rag_service import (
    search_knowledge_chunks,
    ask_knowledge_base,
)
from app.utils.response import ApiResponse, success

router = APIRouter(prefix="/knowledge", tags=["RAG知识库"])


@router.post("/search", response_model=ApiResponse[KnowledgeSearchResponse])
def search_knowledge(
    payload: KnowledgeSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    向量检索课程知识库。

    支持按 course_id / chapter_id / knowledge_point_id 过滤。
    """
    data = search_knowledge_chunks(
        db=db,
        course_id=payload.course_id,
        query=payload.query,
        top_k=payload.top_k,
        chapter_id=payload.chapter_id,
        knowledge_point_id=payload.knowledge_point_id,
    )
    return success(data)


@router.post("/ask", response_model=ApiResponse[KnowledgeAskResponse])
def ask_knowledge(
    payload: KnowledgeAskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    RAG 知识库问答。

    使用流程：
    1. 先从 Chroma 检索相关知识块
    2. 再把知识块作为上下文交给 DeepSeek
    3. 返回自然语言回答和引用来源
    """
    data = ask_knowledge_base(
        db=db,
        course_id=payload.course_id,
        question=payload.question,
        top_k=payload.top_k,
        chapter_id=payload.chapter_id,
        knowledge_point_id=payload.knowledge_point_id,
    )
    return success(data)
