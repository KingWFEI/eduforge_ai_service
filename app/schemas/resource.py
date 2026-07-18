from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from app.constants.resource_generation import GenerationScope, ResourceType, validate_resource_scope


class RecommendedResourceItem(BaseModel):
    resource_id: str = Field(..., description="资源ID")
    title: str = Field(..., description="资源标题")
    type: str = Field(..., description="资源类型")
    difficulty: Optional[str] = Field(None, description="难度")
    description: Optional[str] = Field(None, description="资源描述")
    reason: Optional[str] = Field(None, description="推荐原因")
    review_status: Optional[str] = Field(None, description="审核状态")


class RecommendedResourcesResponse(BaseModel):
    items: List[RecommendedResourceItem] = Field(default_factory=list, description="推荐资源列表")
    total: int = Field(..., description="资源总数")

class MyResourceItem(BaseModel):
    resource_id: str = Field(..., description="资源ID")
    title: str = Field(..., description="资源标题")
    type: str = Field(..., description="资源类型")
    difficulty: Optional[str] = Field(None, description="难度")
    description: Optional[str] = Field(None, description="资源描述")
    reason: Optional[str] = Field(None, description="推荐/生成原因")
    source: Optional[str] = Field(None, description="资源来源")
    status: Optional[str] = Field(None, description="资源状态")
    rating: Optional[float] = Field(None, description="评分")
    favorite: bool = Field(False, description="是否已收藏")
    created_at: Optional[str] = Field(None, description="创建时间")


class MyResourcesResponse(BaseModel):
    items: List[MyResourceItem] = Field(default_factory=list, description="资源列表")
    total: int = Field(..., description="资源总数")
    page: int = Field(..., description="页码")
    page_size: int = Field(..., description="每页数量")


class ResourceDetailResponse(BaseModel):
    resource_id: str = Field(..., description="资源ID")
    student_id: Optional[str] = Field(None, description="学生ID")
    course_id: Optional[str] = Field(None, description="课程ID")
    knowledge_point_id: Optional[str] = Field(None, description="知识点ID")

    title: str = Field(..., description="资源标题")
    type: str = Field(..., description="资源类型")
    difficulty: Optional[str] = Field(None, description="难度")
    description: Optional[str] = Field(None, description="资源描述")
    reason: Optional[str] = Field(None, description="推荐原因")

    content_text: Optional[str] = Field(None, description="资源正文")
    content_json: Optional[dict] = Field(None, description="结构化内容")
    generation_scope: Optional[str] = None
    source_type: Optional[str] = None
    generation_mode: Optional[str] = None
    external_provider: Optional[str] = None
    external_id: Optional[str] = None
    file_url: Optional[str] = None
    preview_url: Optional[str] = None
    review_score: Optional[float] = None

    favorite: bool = Field(False, description="是否已收藏")
    review_status: Optional[str] = Field(None, description="审核状态")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")

class ResourceFeedbackCreate(BaseModel):
    liked: Optional[bool] = Field(None, description="是否喜欢")
    favorite: bool = Field(False, description="是否收藏")
    difficulty_feedback: Optional[str] = Field(
        None,
        description="难度反馈：太简单 / 合适 / 太难"
    )
    comment: Optional[str] = Field(None, description="文字反馈")


class ResourceFeedbackResponse(BaseModel):
    resource_id: str = Field(..., description="资源ID")
    profile_update_hint: str = Field(..., description="学生画像更新提示")


class ResourceFavoriteRequest(BaseModel):
    favorite: bool = Field(..., description="是否收藏")


class ResourceFavoriteResponse(BaseModel):
    resource_id: str = Field(..., description="资源ID")
    favorite: bool = Field(..., description="是否收藏")


class FavoriteResourceItem(BaseModel):
    resource_id: str = Field(..., description="资源ID")
    title: str = Field(..., description="资源标题")
    type: str = Field(..., description="资源类型")
    difficulty: Optional[str] = Field(None, description="难度")
    created_at: Optional[str] = Field(None, description="创建时间")


class FavoriteResourcesResponse(BaseModel):
    items: List[FavoriteResourceItem] = Field(default_factory=list, description="收藏资源列表")
    total: int = Field(..., description="资源总数")
    page: int = Field(..., description="页码")
    page_size: int = Field(..., description="每页数量")

class ResourceViewResponse(BaseModel):
    resource_id: str = Field(..., description="资源ID")
    student_id: str = Field(..., description="学生ID")
    course_id: Optional[str] = Field(None, description="课程ID")
    study_record_id: str = Field(..., description="学习记录ID")
    study_minutes_added: int = Field(..., description="本次新增学习分钟数")
    action_type: str = Field(..., description="学习行为类型")

# ─── 阶段 4：资源生成任务 ─────────────────────────────

class GenerateResourceRequest(BaseModel):
    """统一资源生成请求；旧版多资源请求字段继续兼容。"""

    course_id: str = Field(..., description="课程 ID")
    chapter_id: Optional[str] = Field(None, description="章节 ID")
    section_id: Optional[str] = Field(None, description="小节 ID")
    knowledge_point_ids: List[str] = Field(default_factory=list, description="知识点 ID 列表")
    resource_type: Optional[ResourceType] = Field(None, description="单一资源类型")
    user_request: Optional[str] = Field(None, max_length=2000, description="用户补充需求")
    generation_scope: GenerationScope = Field(GenerationScope.SECTION, description="生成范围")

    # Legacy request fields.
    knowledge_point: Optional[str] = Field(None, description="旧版知识点名称")
    goal: Optional[str] = Field(None, description="旧版学习目标")
    resource_types: List[str] = Field(default_factory=list, description="旧版资源类型列表")
    difficulty: str = Field("基础", description="难度：基础 / 中等 / 提高")
    use_profile: bool = Field(True, description="是否结合学生画像")

    @model_validator(mode="after")
    def validate_request(self):
        selected = [self.resource_type.value] if self.resource_type else list(self.resource_types)
        if not selected:
            raise ValueError("resource_type 不能为空")
        selected = ["video" if item == "video_script" else item for item in selected]
        if self.resource_type is None:
            self.resource_types = selected
        for item in selected:
            validate_resource_scope(item, self.generation_scope.value)
        if self.generation_scope == GenerationScope.SECTION and not self.section_id:
            # Legacy clients did not send section_id, so only enforce it for the new single-type contract.
            if self.resource_type is not None:
                raise ValueError("section scope 必须提供 section_id")
        if self.generation_scope in {GenerationScope.SECTION, GenerationScope.CHAPTER} and not self.chapter_id:
            # A section can be resolved to its parent chapter by the service.
            if self.generation_scope == GenerationScope.CHAPTER:
                raise ValueError("chapter scope 必须提供 chapter_id")
        return self


class GenerateResourceTaskResponse(BaseModel):
    task_id: str = Field(..., description="资源生成任务 ID")
    status: str = Field(..., description="任务状态")
    progress: int = Field(..., description="任务进度")
    message: str = Field("任务已进入队列", description="提示信息")


class ResourceTaskStepItem(BaseModel):
    agent_name: str = Field(..., description="智能体名称")
    step_order: int = Field(..., description="步骤顺序")
    status: str = Field(..., description="步骤状态")
    input_summary: Optional[str] = Field(None, description="输入摘要")
    output_summary: Optional[str] = Field(None, description="输出摘要")
    duration_ms: Optional[int] = Field(None, description="耗时")


class DeleteResourceResponse(BaseModel):
    deleted_resources: int = Field(..., description="删除的资源数量")
    deleted_generation_tasks: int = Field(0, description="删除的资源生成任务数量")
    scope: str = Field(..., description="删除范围：single / generated")


class ReviewResourceItem(BaseModel):
    resource_id: str
    title: str
    type: str
    course: Optional[str] = None
    review_status: str
    safety_score: Optional[float] = None
    hallucination_risk: Optional[str] = None
    created_at: Optional[str] = None


class ReviewResourceListResponse(BaseModel):
    items: List[ReviewResourceItem] = Field(default_factory=list)
    total: int
    page: int
    page_size: int


class ResourceReviewRequest(BaseModel):
    action: str = Field(..., description="approve / reject / need_modify / regenerate")
    comment: Optional[str] = Field(None, description="审核意见")


class ResourceReviewResponse(BaseModel):
    resource_id: str
    review_status: str
    reviewer: Optional[str] = None
    reviewed_at: Optional[str] = None


class ResourceRegenerateRequest(BaseModel):
    reason: str = Field(..., description="重新生成原因或修改意见")
    keep_references: bool = Field(True, description="是否保留原引用资料")


class ResourceRegenerateResponse(BaseModel):
    task_id: str
    status: str


class ResourceTaskDetailResponse(BaseModel):
    task_id: str = Field(..., description="资源生成任务 ID")
    status: str = Field(..., description="任务状态")
    progress: int = Field(..., description="任务进度")
    current_step: Optional[str] = Field(None, description="当前步骤")
    resource_ids: List[str] = Field(default_factory=list, description="生成的资源 ID")
    agent_task_id: Optional[str] = Field(None, description="智能体任务 ID")
    steps: List[ResourceTaskStepItem] = Field(default_factory=list, description="智能体执行步骤")
    error_message: Optional[str] = Field(None, description="错误信息")
    error_code: Optional[str] = None
    failed_step: Optional[str] = None
    retryable: bool = False
    retry_count: int = 0
