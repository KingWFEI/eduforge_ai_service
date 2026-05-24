from typing import List, Optional

from pydantic import BaseModel, Field


class TodayTaskItem(BaseModel):
    task_id: str = Field(..., description="任务ID")
    day_no: int = Field(..., description="第几天任务")
    topic: str = Field(..., description="任务主题")
    description: Optional[str] = Field(None, description="任务说明")
    estimated_minutes: Optional[int] = Field(None, description="预计学习分钟数")
    status: Optional[str] = Field(None, description="任务状态")
    completed_at: Optional[str] = Field(None, description="完成时间")


class TodayLearningPathResponse(BaseModel):
    path_id: Optional[str] = Field(None, description="学习路径ID")
    path_title: Optional[str] = Field(None, description="学习路径标题")
    course_id: Optional[str] = Field(None, description="课程ID")
    today_progress: float = Field(..., description="今日任务完成进度，0~1")
    total_tasks: int = Field(..., description="任务总数")
    completed_tasks: int = Field(..., description="已完成任务数")
    current_task: Optional[TodayTaskItem] = Field(None, description="当前建议学习任务")
    tasks: List[TodayTaskItem] = Field(default_factory=list, description="任务列表")

class CompleteTaskResponse(BaseModel):
    task_id: str = Field(..., description="任务ID")
    path_id: str = Field(..., description="学习路径ID")
    status: str = Field(..., description="任务状态")
    completed_at: Optional[str] = Field(None, description="完成时间")

    total_tasks: int = Field(..., description="任务总数")
    completed_tasks: int = Field(..., description="已完成任务数")
    path_progress: float = Field(..., description="学习路径进度，0~1")
    study_minutes_added: int = Field(..., description="本次新增学习分钟数")