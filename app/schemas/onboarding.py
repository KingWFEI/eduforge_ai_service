from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.constants.role import Role


# ─── 基础数据结构 ─────────────────────────────────────

class OnboardingOption(BaseModel):
    """问卷选项（面向用户的展示层）"""
    value: str
    label: str
    description: str
    icon: Optional[str] = None
    color: Optional[str] = None


class OnboardingMatrixItem(BaseModel):
    """技能矩阵项"""
    key: str
    label: str
    levels: list[str]


class OnboardingQuestion(BaseModel):
    """问卷题目（面向用户的展示层）"""
    id: str
    step: int
    title: str
    subtitle: str
    type: Literal["single", "multi", "skill_matrix", "text", "scale"]
    required: bool = True
    options: list[OnboardingOption] = []
    matrix_items: list[OnboardingMatrixItem] = []


# ─── 问卷查询 ─────────────────────────────────────────

class OnboardingSurveyResponse(BaseModel):
    """问卷完整响应（含题目）"""
    survey_id: str
    title: str
    description: str
    version: int
    questions: list[OnboardingQuestion]


class OnboardingSurveyListItem(BaseModel):
    """问卷列表项"""
    survey_id: str
    title: str
    description: str
    version: int
    status: Literal["draft", "published", "archived"]
    question_count: int
    submit_count: int
    created_by: str
    created_at: datetime
    updated_at: datetime


# ─── 问卷管理（管理端）────────────────────────────────

class OnboardingSurveyCreateRequest(BaseModel):
    """创建问卷请求"""
    title: str = Field(..., min_length=1)
    description: str = ""
    target_role: Role = Role.STUDENT
    target_course_id: Optional[str] = None


class OnboardingSurveyCreateResponse(BaseModel):
    """创建问卷响应"""
    survey_id: str
    title: str
    status: Literal["draft"]


class OnboardingSurveyUpdateRequest(BaseModel):
    """更新问卷请求"""
    title: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    target_role: Optional[Role] = None
    target_course_id: Optional[str] = None


class OnboardingSurveyPublishResponse(BaseModel):
    """发布问卷响应"""
    survey_id: str
    status: Literal["published"]
    version: int


class AdminOnboardingOption(BaseModel):
    """问卷选项（管理端完整信息）"""
    option_id: str
    label: str
    value: str
    description: str = ""
    sort_order: int = 0
    icon: Optional[str] = None
    color: Optional[str] = None
    profile_mapping: dict[str, Any] = {}


class AdminOnboardingQuestion(BaseModel):
    """问卷题目（管理端完整信息）"""
    question_id: str
    step: int
    title: str
    subtitle: str = ""
    type: Literal["single", "multi", "skill_matrix", "text", "scale"]
    required: bool = True
    options: list[AdminOnboardingOption] = []
    matrix_items: list[OnboardingMatrixItem] = []


class OnboardingSurveyDetailResponse(BaseModel):
    """问卷详情（管理端，含题目和选项完整信息）"""
    survey_id: str
    title: str
    description: str = ""
    version: int
    status: Literal["draft", "published", "archived"]
    target_role: Role
    target_course_id: Optional[str] = None
    questions: list[AdminOnboardingQuestion]


# ─── 题目管理 ─────────────────────────────────────────

class OnboardingOptionCreateRequest(BaseModel):
    """创建选项请求"""
    label: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)
    description: str = ""
    sort_order: int = 0
    icon: Optional[str] = None
    color: Optional[str] = None
    profile_mapping: dict[str, Any] = {}


class OnboardingOptionUpdateRequest(BaseModel):
    """更新选项请求"""
    label: Optional[str] = None
    value: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    profile_mapping: Optional[dict[str, Any]] = None


class OnboardingOptionCreateResponse(BaseModel):
    """创建选项响应"""
    option_id: str


class OnboardingQuestionCreateRequest(BaseModel):
    """创建题目请求"""
    title: str = Field(..., min_length=1)
    subtitle: str = ""
    type: Literal["single", "multi", "skill_matrix", "text", "scale"]
    step: int = Field(..., ge=1)
    required: bool = True
    options: list[OnboardingOptionCreateRequest] = []
    matrix_items: list[OnboardingMatrixItem] = []


class OnboardingQuestionUpdateRequest(BaseModel):
    """更新题目请求"""
    title: Optional[str] = None
    subtitle: Optional[str] = None
    type: Optional[Literal["single", "multi", "skill_matrix", "text", "scale"]] = None
    required: Optional[bool] = None
    step: Optional[int] = Field(None, ge=1)
    matrix_items: Optional[list[OnboardingMatrixItem]] = None


class OnboardingQuestionCreateResponse(BaseModel):
    """创建题目响应"""
    question_id: str


class QuestionOrderItem(BaseModel):
    """题目排序项"""
    question_id: str
    step: int = Field(..., ge=1)


class QuestionReorderRequest(BaseModel):
    """题目排序请求"""
    question_orders: list[QuestionOrderItem]


# ─── 问卷提交 ─────────────────────────────────────────

class OnboardingSubmitRequest(BaseModel):
    """提交问卷请求"""
    survey_id: str
    answers: dict[str, Any]


class OnboardingSubmitResponse(BaseModel):
    """提交问卷响应（异步任务模式，不直接返回画像）"""
    submission_id: str
    analysis_id: str
    status: str = "processing"
    next_action: str = "poll_profile_result"

class OnBoardingStatusData(BaseModel):
    need_onboarding: bool
    onboarding_status: str
    survey_id: Optional[str] = None
    submission_id: Optional[str] = None
    profile_id: Optional[str] = None

    completed_at: Optional[datetime] = None
    skipped_at: Optional[datetime] = None
    reset_at: Optional[datetime] = None


# ─── 画像查询 ─────────────────────────────────────────

class ProfileData(BaseModel):
    """学生综合学习画像数据"""
    profile_id: str
    student_id: str
    name: str = ""
    learning_preferences: list[Any] = Field(default_factory=list)
    cognitive_traits: list[Any] = Field(default_factory=list)
    learning_habits: list[Any] = Field(default_factory=list)
    motivation_factors: list[Any] = Field(default_factory=list)
    general_strengths: list[Any] = Field(default_factory=list)
    general_challenges: list[Any] = Field(default_factory=list)
    preferred_pace: str = ""
    available_time: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    profile_dimensions: dict[str, Any] = Field(default_factory=dict)
    evidence: list[Any] = Field(default_factory=list)
    confidence: dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    last_updated: datetime


class AnalysisData(BaseModel):
    """画像分析数据"""
    analysis_text: Optional[str] = None
    learning_suggestion: Optional[str] = None


class AgentTrace(BaseModel):
    """智能体/技能/大模型调用记录"""
    agent_used: Optional[str] = None
    skill_used: Optional[bool] = None
    skill_name: Optional[str] = None
    llm_used: Optional[bool] = None
    llm_provider: Optional[str] = None
    llm_error: Optional[str] = None


class ErrorInfo(BaseModel):
    """分析失败错误信息"""
    error_code: str
    error_message: str


class ProfileQueryData(BaseModel):
    """画像查询响应数据"""
    submission_id: Optional[str] = None
    analysis_id: Optional[str] = None
    status: str
    progress: int
    current_step: Optional[str] = None
    agent_trace: Optional[AgentTrace] = None
    profile: Optional[ProfileData] = None
    analysis: Optional[AnalysisData] = None
    error: Optional[ErrorInfo] = None
