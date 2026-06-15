from typing import Any, List, Optional

from pydantic import BaseModel, Field


class TodayTaskItem(BaseModel):
    task_id: str = Field(..., description="任务 ID")
    day_no: int = Field(..., description="第几天任务")
    topic: str = Field(..., description="任务主题")
    description: Optional[str] = Field(None, description="任务说明")
    estimated_minutes: Optional[int] = Field(None, description="预计学习分钟数")
    status: Optional[str] = Field(None, description="任务状态")
    completed_at: Optional[str] = Field(None, description="完成时间")


class TodayLearningPathResponse(BaseModel):
    path_id: Optional[str] = Field(None, description="学习路径 ID")
    path_title: Optional[str] = Field(None, description="学习路径标题")
    course_id: Optional[str] = Field(None, description="课程 ID")
    today_progress: float = Field(..., description="今日任务完成进度，0~1")
    total_tasks: int = Field(..., description="任务总数")
    completed_tasks: int = Field(..., description="已完成任务数")
    current_task: Optional[TodayTaskItem] = Field(None, description="当前建议学习任务")
    tasks: List[TodayTaskItem] = Field(default_factory=list, description="任务列表")


class CompleteTaskResponse(BaseModel):
    task_id: str = Field(..., description="任务 ID")
    path_id: str = Field(..., description="学习路径 ID")
    status: str = Field(..., description="任务状态")
    completed_at: Optional[str] = Field(None, description="完成时间")
    total_tasks: int = Field(..., description="任务总数")
    completed_tasks: int = Field(..., description="已完成任务数")
    path_progress: float = Field(..., description="学习路径进度，0~1")
    study_minutes_added: int = Field(..., description="本次新增学习分钟数")


class GenerateLearningPathRequest(BaseModel):
    course_id: str = Field(..., description="课程 ID")
    goal: Optional[str] = Field(None, description="学习目标")
    duration_days: int = Field(7, ge=1, le=90, description="规划天数")
    daily_minutes: int = Field(30, ge=5, le=240, description="每日学习分钟数")
    knowledge_points: List[str] = Field(default_factory=list, description="指定知识点，可为空")


class LearningPathTaskItem(BaseModel):
    task_id: str
    day_no: int
    topic: str
    description: Optional[str] = None
    estimated_minutes: Optional[int] = None
    resource_ids: List[str] = Field(default_factory=list)
    status: str
    completed_at: Optional[str] = None


class LearningPathResponse(BaseModel):
    path_id: str
    title: str
    course_id: str
    course_name: Optional[str] = None
    goal: Optional[str] = None
    duration_days: Optional[int] = None
    daily_minutes: Optional[int] = None
    progress: float = 0
    status: str
    plan: dict[str, Any] = Field(default_factory=dict)
    tasks: List[LearningPathTaskItem] = Field(default_factory=list)
    total_tasks: int = 0
    completed_tasks: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class GenerateLearningPathResponse(LearningPathResponse):
    agent: str = "Planner Agent"
