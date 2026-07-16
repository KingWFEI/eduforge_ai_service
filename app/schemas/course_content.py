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


class GenerateSectionResourceRequest(BaseModel):
    course_id: str = Field(..., description="课程ID")
    section_id: str = Field(..., description="小节ID")
    resource_id: Optional[str] = Field(
        None,
        description="首次生成时可传资源壳子ID；后续生成可省略，后端按 type 定位",
    )
    type: str = Field(..., description="资源类型：illustration / code_case / exercise / mind_map")
    content_id: Optional[str] = Field(None, description="小节内容ID；不传则使用该小节最新内容")


class GenerateCourseSectionResourceRequest(BaseModel):
    resource_id: Optional[str] = Field(
        None,
        description="首次生成时可传资源壳子ID；后续生成可省略，后端按 type 定位",
    )
    type: str = Field(..., description="资源类型：illustration / code_case / exercise / mind_map")
    content_id: Optional[str] = Field(None, description="小节内容 ID；不传则使用该小节最新内容")


class GeneratedSectionResourceHistoryItem(BaseModel):
    resource_id: str = Field(..., description="实际学习资源ID")
    title: str = Field(..., description="资源标题")
    type: str = Field(..., description="资源类型")
    description: Optional[str] = Field(None, description="资源描述")
    content_text: Optional[str] = Field(None, description="资源正文")
    content_json: Optional[dict[str, Any]] = Field(None, description="结构化资源内容")
    image_url: Optional[str] = Field(None, description="后端生成的图解图片地址")
    created_at: Optional[str] = Field(None, description="生成时间")


class GeneratedSectionResourceListResponse(BaseModel):
    course_id: str = Field(..., description="课程ID")
    section_id: str = Field(..., description="小节ID")
    total: int = Field(..., ge=0, description="历史资源数量")
    items: List[GeneratedSectionResourceHistoryItem] = Field(
        default_factory=list,
        description="历史资源，最新在前",
    )


class SectionResourceGenerateResponse(BaseModel):
    generated: bool = Field(..., description="资源是否成功生成")
    resource_id: Optional[str] = Field(None, description="实际学习资源ID；未生成时为空")


class GeneratedSectionResourceDetailResponse(BaseModel):
    resource_id: str = Field(..., description="实际学习资源ID")
    course_id: str = Field(..., description="课程ID")
    section_id: str = Field(..., description="小节ID")
    knowledge_point_id: Optional[str] = Field(None, description="知识点ID")
    title: str = Field(..., description="资源标题")
    type: str = Field(..., description="资源类型")
    difficulty: Optional[str] = Field(None, description="难度")
    description: Optional[str] = Field(None, description="资源描述")
    content_text: Optional[str] = Field(None, description="资源正文")
    content_json: Optional[dict[str, Any]] = Field(None, description="结构化资源内容")
    image_url: Optional[str] = Field(None, description="图解图片地址")
    source: Optional[str] = Field(None, description="资源来源")
    created_at: Optional[str] = Field(None, description="生成时间")
    updated_at: Optional[str] = Field(None, description="更新时间")


class GeneratedSectionResourceResponse(BaseModel):
    resource_id: str = Field(..., description="资源壳子ID")
    learning_resource_id: Optional[str] = Field(None, description="落库后的学习资源ID")
    title: str = Field(..., description="资源标题")
    subtitle: Optional[str] = Field(None, description="资源副标题")
    type: str = Field(..., description="资源类型")
    course_id: str = Field(..., description="课程ID")
    section_id: str = Field(..., description="小节ID")
    content_id: Optional[str] = Field(None, description="小节内容ID")
    knowledge_point_id: Optional[str] = Field(None, description="知识点ID")
    content_text: Optional[str] = Field(None, description="资源正文")
    content_json: Optional[dict[str, Any]] = Field(None, description="资源结构化内容")
    image_url: Optional[str] = Field(None, description="后端生成的图解图片地址")
    source_chunk_ids: List[str] = Field(default_factory=list, description="来源知识块ID")
    generation_model: Optional[str] = Field(None, description="生成模型")
    source: Optional[str] = Field(None, description="资源来源")
    generation_status: str = Field("generated", description="生成状态：generated / skipped")
    should_generate: bool = Field(True, description="智能体是否建议生成该资源")
    decision_reason: Optional[str] = Field(None, description="智能体判断原因")
    suitability_score: Optional[float] = Field(None, ge=0, le=1, description="章节内容图解适用度")
    profile_fit_score: Optional[float] = Field(None, ge=0, le=1, description="图解与用户画像匹配度")
    generated_resources: List[GeneratedSectionResourceHistoryItem] = Field(
        default_factory=list,
        description="当前用户在该小节生成过的全部资源，最新在前",
    )


class GeneratedCourseSectionResourceResponse(GeneratedSectionResourceResponse):
    resource_type: str = Field(..., description="资源类型")


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
