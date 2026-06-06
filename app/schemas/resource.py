from typing import List, Optional

from pydantic import BaseModel, Field


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
    feedback_id: str = Field(..., description="反馈ID")
    resource_id: str = Field(..., description="资源ID")
    student_id: str = Field(..., description="学生ID")
    liked: Optional[bool] = Field(None, description="是否喜欢")
    favorite: bool = Field(..., description="是否收藏")
    difficulty_feedback: Optional[str] = Field(None, description="难度反馈")
    comment: Optional[str] = Field(None, description="文字反馈")

class ResourceViewResponse(BaseModel):
    resource_id: str = Field(..., description="资源ID")
    student_id: str = Field(..., description="学生ID")
    course_id: Optional[str] = Field(None, description="课程ID")
    study_record_id: str = Field(..., description="学习记录ID")
    study_minutes_added: int = Field(..., description="本次新增学习分钟数")
    action_type: str = Field(..., description="学习行为类型")

# ─── 阶段 4：资源生成任务 ─────────────────────────────

class GenerateResourceRequest(BaseModel):
    course_id: str = Field(..., description="课程 ID")
    knowledge_point: str = Field(..., description="知识点名称")
    goal: str = Field(..., description="学习目标")
    resource_types: List[str] = Field(..., description="资源类型：document / mind_map / exercise / code_case / video_script")
    difficulty: str = Field("基础", description="难度：基础 / 中等 / 提高")
    use_profile: bool = Field(True, description="是否结合学生画像")


class GenerateResourceTaskResponse(BaseModel):
    task_id: str = Field(..., description="资源生成任务 ID")
    status: str = Field(..., description="任务状态")
    progress: int = Field(..., description="任务进度")
    message: str = Field(..., description="提示信息")


class ResourceTaskStepItem(BaseModel):
    agent_name: str = Field(..., description="智能体名称")
    step_order: int = Field(..., description="步骤顺序")
    status: str = Field(..., description="步骤状态")
    input_summary: Optional[str] = Field(None, description="输入摘要")
    output_summary: Optional[str] = Field(None, description="输出摘要")
    duration_ms: Optional[int] = Field(None, description="耗时")


class ResourceTaskDetailResponse(BaseModel):
    task_id: str = Field(..., description="资源生成任务 ID")
    status: str = Field(..., description="任务状态")
    progress: int = Field(..., description="任务进度")
    current_step: Optional[str] = Field(None, description="当前步骤")
    resource_ids: List[str] = Field(default_factory=list, description="生成的资源 ID")
    agent_task_id: Optional[str] = Field(None, description="智能体任务 ID")
    steps: List[ResourceTaskStepItem] = Field(default_factory=list, description="智能体执行步骤")
    error_message: Optional[str] = Field(None, description="错误信息")
