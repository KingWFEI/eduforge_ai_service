from typing import Any, List, Optional

from pydantic import BaseModel, Field
from datetime import datetime

class CourseCreate(BaseModel):
    """创建课程请求"""
    course_id: str
    name: str
    description: Optional[str] = None


class CourseResponse(BaseModel):
    """课程信息响应"""
    id: int
    course_id: str
    name: str
    description: Optional[str] = None
    cover_url: Optional[str] = None
    semester: Optional[str] = None
    status: Optional[str] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CourseFileResponse(BaseModel):
    """课程文件响应"""
    id: str
    course_id: str
    filename: str
    file_path: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    parse_status: Optional[str] = None

    class Config:
        from_attributes = True


class CourseUploadResponse(BaseModel):
    document_id: str = Field(..., description="文档ID")
    course_id: str = Field(..., description="课程ID")
    filename: str = Field(..., description="文件名")
    chunk_count: int = Field(..., description="知识块数量")
    parse_status: str = Field(..., description="解析状态")
    index_status: str = Field(..., description="索引状态")


class CourseDocumentItem(BaseModel):
    document_id: str = Field(..., description="文档ID")
    course_id: str = Field(..., description="课程ID")
    chapter_id: Optional[str] = Field(None, description="章节ID")
    filename: str = Field(..., description="文件名")
    file_path: str = Field(..., description="文件路径")
    file_type: Optional[str] = Field(None, description="文件类型")
    file_size: Optional[int] = Field(None, description="文件大小")
    description: Optional[str] = Field(None, description="资料说明")
    status: Optional[str] = Field(None, description="资料状态")
    parse_status: Optional[str] = Field(None, description="解析状态")
    index_status: Optional[str] = Field(None, description="索引状态")
    chunk_count: Optional[int] = Field(0, description="知识块数量")
    uploaded_by: Optional[str] = Field(None, description="上传人")
    uploaded_at: Optional[str] = Field(None, description="上传时间")
    updated_at: Optional[str] = Field(None, description="更新时间")


class CourseDocumentListResponse(BaseModel):
    course_id: str = Field(..., description="课程ID")
    total: int = Field(..., description="文档总数")
    items: List[CourseDocumentItem] = Field(default_factory=list, description="文档列表")


class DeleteCourseDocumentResponse(BaseModel):
    document_id: str = Field(..., description="文档ID")
    course_id: str = Field(..., description="课程ID")
    filename: Optional[str] = Field(None, description="文件名")
    deleted_chunks: int = Field(..., description="逻辑删除的知识块数量")
    deleted_vectors: int = Field(0, description="删除的 Chroma 向量数量")
    document_status: str = Field(..., description="课程资料状态")


class CourseKnowledgeChunkItem(BaseModel):
    chunk_id: str = Field(..., description="知识块ID")
    document_id: str = Field(..., description="文档ID")
    course_id: str = Field(..., description="课程ID")
    chapter_id: Optional[str] = Field(None, description="章节ID")
    chapter: Optional[str] = Field(None, description="章节名称")
    section: Optional[str] = Field(None, description="片段标题")
    content: str = Field(..., description="知识块内容")
    keywords: List[str] = Field(default_factory=list, description="关键词")
    source: Optional[str] = Field(None, description="来源文档")
    page: Optional[int] = Field(None, description="页码")
    chunk_index: int = Field(..., description="知识块序号")
    indexed: bool = Field(..., description="是否已索引")


class CourseKnowledgeChunkListResponse(BaseModel):
    items: List[CourseKnowledgeChunkItem] = Field(default_factory=list, description="知识块列表")
    total: int = Field(..., description="知识块总数")
    page: int = Field(..., description="页码")
    page_size: int = Field(..., description="每页数量")


class CourseChapterCreate(BaseModel):
    parent_id: Optional[str] = Field(None, description="父级章节ID；为空创建章，传章ID创建小节")
    level: int = Field(1, description="层级：1=章，2=小节")
    title: str = Field(..., description="章节标题")
    sort_order: int = Field(0, description="章节排序")
    description: Optional[str] = Field(None, description="章节说明")


class CourseChapterCreateResponse(BaseModel):
    chapter_id: str = Field(..., description="章节ID")
    course_id: str = Field(..., description="课程ID")
    title: str = Field(..., description="章节标题")
    sort_order: int = Field(..., description="章节排序")
    description: Optional[str] = Field(None, description="章节说明")


class CourseChapterItem(BaseModel):
    chapter_id: str = Field(..., description="章节ID")
    course_id: str = Field(..., description="课程ID")
    parent_id: Optional[str] = Field(None, description="父级章节ID；为空表示章，不为空表示小节")
    level: int = Field(1, description="层级：1=章，2=小节")
    title: str = Field(..., description="章节标题")
    description: Optional[str] = Field(None, description="章节说明")
    sort_order: int = Field(..., description="章节排序")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")


class CourseChapterListResponse(BaseModel):
    course_id: str = Field(..., description="课程ID")
    total: int = Field(..., description="章节数量")
    items: List[CourseChapterItem] = Field(default_factory=list, description="章节列表")


class KnowledgePointCreate(BaseModel):
    name: str = Field(..., description="知识点名称")
    description: Optional[str] = Field(None, description="知识点说明")
    difficulty: Optional[str] = Field("基础", description="难度：基础 / 中等 / 较难")
    sort_order: int = Field(0, description="排序")


class KnowledgePointCreateResponse(BaseModel):
    knowledge_point_id: str = Field(..., description="知识点ID")
    course_id: str = Field(..., description="课程ID")
    chapter_id: str = Field(..., description="章节ID")
    name: str = Field(..., description="知识点名称")
    description: Optional[str] = Field(None, description="知识点说明")
    difficulty: Optional[str] = Field(None, description="难度")
    sort_order: int = Field(..., description="排序")


class KnowledgePointItem(BaseModel):
    knowledge_point_id: str = Field(..., description="知识点ID")
    course_id: str = Field(..., description="课程ID")
    chapter_id: Optional[str] = Field(None, description="章节ID")
    chapter_title: Optional[str] = Field(None, description="章节标题")
    name: str = Field(..., description="知识点名称")
    description: Optional[str] = Field(None, description="知识点说明")
    difficulty: Optional[str] = Field(None, description="难度")
    sort_order: int = Field(..., description="排序")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")


class KnowledgePointListResponse(BaseModel):
    course_id: str = Field(..., description="课程ID")
    chapter_id: Optional[str] = Field(None, description="章节ID")
    total: int = Field(..., description="知识点数量")
    items: List[KnowledgePointItem] = Field(default_factory=list, description="知识点列表")


#管理端查看索引记录
class VectorIndexRecordItem(BaseModel):
    index_record_id: str = Field(..., description="索引记录ID")
    course_id: str = Field(..., description="课程ID")
    document_id: str = Field(..., description="文档ID")
    index_type: str | None = Field(None, description="索引类型")
    collection_name: str | None = Field(None, description="Chroma Collection 名称")
    status: str | None = Field(None, description="状态")
    chunk_count: int | None = Field(0, description="chunk 数量")
    success_count: int | None = Field(0, description="成功数量")
    failed_count: int | None = Field(0, description="失败数量")
    error_message: str | None = Field(None, description="错误信息")
    started_at: str | None = Field(None, description="开始时间")
    finished_at: str | None = Field(None, description="结束时间")
    created_by: str | None = Field(None, description="创建人")


class VectorIndexRecordListResponse(BaseModel):
    course_id: str = Field(..., description="课程ID")
    total: int = Field(..., description="索引记录数量")
    items: List[VectorIndexRecordItem] = Field(default_factory=list)


class LinkCourseDocumentRequest(BaseModel):
    chapter_id: str = Field(..., description="章节ID")
    knowledge_point_id: Optional[str] = Field(None, description="知识点ID，可选")


class LinkCourseDocumentResponse(BaseModel):
    document_id: str = Field(..., description="文档ID")
    course_id: str = Field(..., description="课程ID")
    chapter_id: str = Field(..., description="章节ID")
    knowledge_point_id: Optional[str] = Field(None, description="知识点ID")
    updated_chunks: int = Field(..., description="更新的 MySQL 知识块数量")
    updated_chroma_chunks: int = Field(..., description="更新的 Chroma 知识块数量")
    linked: bool = Field(..., description="是否关联成功")


class VectorIndexRecordItem(BaseModel):
    index_record_id: str = Field(..., description="索引记录ID")
    course_id: str = Field(..., description="课程ID")
    document_id: str = Field(..., description="文档ID")
    filename: Optional[str] = Field(None, description="文档文件名")

    index_type: Optional[str] = Field(None, description="索引类型，例如 chroma")
    collection_name: Optional[str] = Field(None, description="Chroma Collection 名称")
    status: Optional[str] = Field(None, description="索引状态")

    chunk_count: int = Field(0, description="chunk 总数")
    success_count: int = Field(0, description="成功数量")
    failed_count: int = Field(0, description="失败数量")

    error_message: Optional[str] = Field(None, description="错误信息")
    started_at: Optional[str] = Field(None, description="开始时间")
    finished_at: Optional[str] = Field(None, description="结束时间")
    created_by: Optional[str] = Field(None, description="创建人")


class VectorIndexRecordListResponse(BaseModel):
    course_id: str = Field(..., description="课程ID")
    total: int = Field(..., description="索引记录数量")
    items: List[VectorIndexRecordItem] = Field(default_factory=list, description="索引记录列表")


class ReindexDocumentResponse(BaseModel):
    index_record: VectorIndexRecordItem


class CourseStructureDraftGenerateRequest(BaseModel):
    document_ids: Optional[List[str]] = Field(None, description="用于生成结构草稿的文档ID；为空表示使用该课程全部有效资料")


class CourseStructureDraftUpdateRequest(BaseModel):
    draft: dict[str, Any] = Field(..., description="教师编辑后的课程结构草稿")


class CourseStructureDraftConfirmRequest(BaseModel):
    draft: Optional[dict[str, Any]] = Field(None, description="可选；教师最终确认时提交的课程结构草稿")
    rebuild_index: bool = Field(True, description="确认后是否按课程结构重建知识块和 Chroma 索引")


class CourseStructureDraftResponse(BaseModel):
    draft_id: str = Field(..., description="草稿ID")
    course_id: str = Field(..., description="课程ID")
    source_document_ids: List[str] = Field(default_factory=list, description="草稿来源文档ID")
    draft: dict[str, Any] = Field(..., description="课程结构草稿")
    status: str = Field(..., description="草稿状态")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")
    confirmed_at: Optional[str] = Field(None, description="确认时间")


class CourseStructureConfirmResponse(BaseModel):
    draft_id: str = Field(..., description="草稿ID")
    course_id: str = Field(..., description="课程ID")
    created_chapters: int = Field(..., description="新增章节数量")
    created_sections: int = Field(..., description="新增小节数量")
    created_knowledge_points: int = Field(..., description="新增知识点数量")
    rebuilt_documents: int = Field(0, description="重建索引的文档数量")
    rebuilt_chunks: int = Field(0, description="重建后的知识块数量")
    status: str = Field(..., description="确认后的草稿状态")
