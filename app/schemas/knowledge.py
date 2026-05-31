from typing import List, Optional

from pydantic import BaseModel, Field


class KnowledgeUploadResponse(BaseModel):
    document_id: str = Field(..., description="文档ID")
    course_id: str = Field(..., description="课程ID")
    filename: str = Field(..., description="文件名")
    chunk_count: int = Field(..., description="知识块数量")
    parse_status: str = Field(..., description="解析状态")
    index_status: str = Field(..., description="索引状态")


class KnowledgeSearchRequest(BaseModel):
    course_id: str = Field(..., description="课程ID")
    query: str = Field(..., description="检索问题")
    top_k: int = Field(5, description="返回前K个知识块")
    chapter_id: str | None = Field(None, description="章节ID，可选")
    knowledge_point_id: str | None = Field(None, description="知识点ID，可选")


class KnowledgeSearchItem(BaseModel):
    chunk_id: str = Field(..., description="知识块ID")
    document_id: str = Field(..., description="文档ID")
    course_id: str = Field(..., description="课程ID")
    chapter_id: str | None = Field(None, description="章节ID")
    knowledge_point_id: str | None = Field(None, description="知识点ID")
    section: str | None = Field(None, description="章节/片段标题")
    content: str = Field(..., description="知识块内容")
    chunk_index: int = Field(..., description="知识块序号")
    score: float = Field(..., description="相似度分数")


class KnowledgeSearchResponse(BaseModel):
    course_id: str = Field(..., description="课程ID")
    query: str = Field(..., description="检索问题")
    total: int = Field(..., description="返回结果数量")
    items: List[KnowledgeSearchItem] = Field(default_factory=list, description="检索结果")


class KnowledgeChunkItem(BaseModel):
    chunk_id: str = Field(..., description="知识块ID")
    document_id: str = Field(..., description="文档ID")
    course_id: str = Field(..., description="课程ID")
    section: Optional[str] = Field(None, description="章节/片段标题")
    content: str = Field(..., description="知识块内容")
    chunk_index: int = Field(..., description="知识块序号")
    indexed: Optional[int] = Field(None, description="是否已索引")


class KnowledgeChunkListResponse(BaseModel):
    course_id: str = Field(..., description="课程ID")
    total: int = Field(..., description="知识块数量")
    items: List[KnowledgeChunkItem] = Field(default_factory=list, description="知识块列表")


class KnowledgeAskRequest(BaseModel):
    course_id: str = Field(..., description="课程ID")
    question: str = Field(..., description="用户问题")
    top_k: int = Field(5, description="检索前K个知识块")
    chapter_id: Optional[str] = Field(None, description="章节ID，可选")
    knowledge_point_id: Optional[str] = Field(None, description="知识点ID，可选")


class KnowledgeAskReference(BaseModel):
    chunk_id: str = Field(..., description="知识块ID")
    document_id: Optional[str] = Field(None, description="文档ID")
    course_id: Optional[str] = Field(None, description="课程ID")
    chapter_id: Optional[str] = Field(None, description="章节ID")
    knowledge_point_id: Optional[str] = Field(None, description="知识点ID")
    section: Optional[str] = Field(None, description="片段来源")
    score: float = Field(..., description="相似度分数")
    content_preview: str = Field(..., description="引用片段预览")


class KnowledgeAskResponse(BaseModel):
    course_id: str = Field(..., description="课程ID")
    chapter_id: Optional[str] = Field(None, description="章节ID")
    knowledge_point_id: Optional[str] = Field(None, description="知识点ID")
    question: str = Field(..., description="用户问题")
    answer: str = Field(..., description="RAG回答")
    references: List[KnowledgeAskReference] = Field(default_factory=list, description="引用来源")
    llm_used: bool = Field(..., description="是否调用大模型")
    provider: str = Field(..., description="大模型供应商")