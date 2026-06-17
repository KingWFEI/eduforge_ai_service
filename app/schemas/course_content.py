from typing import Any, List, Optional

from pydantic import BaseModel, Field


class FailedGenerationItem(BaseModel):
    section_id: str = Field(..., description="小节ID")
    section_title: str = Field(..., description="小节标题")
    error_message: str = Field(..., description="失败原因")


class SectionLearningContentOut(BaseModel):
    content_id: str = Field(..., description="学习内容ID")
    course_id: str = Field(..., description="课程ID")
    chapter_id: Optional[str] = Field(None, description="章节ID")
    section_id: str = Field(..., description="小节ID")
    knowledge_point_id: Optional[str] = Field(None, description="知识点ID")
    title: str = Field(..., description="标题")
    content_type: str = Field(..., description="内容类型")
    content_markdown: Optional[str] = Field(None, description="Markdown 内容")
    content_json: Optional[dict[str, Any]] = Field(None, description="结构化内容")
    source_chunk_ids: List[str] = Field(default_factory=list, description="来源知识块ID")
    generation_model: Optional[str] = Field(None, description="生成模型")
    status: str = Field(..., description="生成状态")
    error_message: Optional[str] = Field(None, description="错误信息")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")


class ConfirmAndGenerateContentResponse(BaseModel):
    draft_id: str = Field(..., description="草稿ID")
    course_id: str = Field(..., description="课程ID")
    status: str = Field(..., description="草稿最终状态")
    chapters_created: int = Field(..., description="创建章节数")
    sections_created: int = Field(..., description="创建小节数")
    knowledge_points_created: int = Field(..., description="创建知识点数")
    contents_generated: int = Field(..., description="成功生成内容数")
    contents_failed: int = Field(..., description="生成失败内容数")
    content_ids: List[str] = Field(default_factory=list, description="成功生成的内容ID")
    failed_items: List[FailedGenerationItem] = Field(default_factory=list, description="失败项")


class SectionLearningContentListResponse(BaseModel):
    course_id: str = Field(..., description="课程ID")
    chapter_id: Optional[str] = Field(None, description="章节ID")
    section_id: Optional[str] = Field(None, description="小节ID")
    total: int = Field(..., description="总数")
    items: List[SectionLearningContentOut] = Field(default_factory=list, description="学习内容列表")


class StartContentGenerationTaskResponse(BaseModel):
    task_id: str = Field(..., description="后台生成任务ID")
    draft_id: str = Field(..., description="草稿ID")
    course_id: str = Field(..., description="课程ID")
    status: str = Field(..., description="任务状态")
    progress: int = Field(0, description="任务进度，0-100")
    total_sections: int = Field(0, description="待生成小节数")


class ContentGenerationTaskStatusResponse(BaseModel):
    task_id: str = Field(..., description="后台生成任务ID")
    draft_id: str = Field(..., description="草稿ID")
    course_id: str = Field(..., description="课程ID")
    status: str = Field(..., description="任务状态")
    progress: int = Field(0, description="任务进度，0-100")
    current_step: Optional[str] = Field(None, description="当前步骤")
    total_sections: int = Field(0, description="小节总数")
    current_section: Optional[str] = Field(None, description="当前处理小节")
    contents_generated: int = Field(0, description="成功生成数量")
    contents_failed: int = Field(0, description="失败数量")
    content_ids: List[str] = Field(default_factory=list, description="生成内容ID")
    failed_items: List[FailedGenerationItem] = Field(default_factory=list, description="失败项")
    error_message: Optional[str] = Field(None, description="任务错误")
