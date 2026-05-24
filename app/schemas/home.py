from pydantic import BaseModel, Field


class HomeSummaryResponse(BaseModel):
    """阶段 3.1：学生首页摘要响应数据"""

    greeting: str = Field(..., description="首页问候语")
    target_course: str = Field(..., description="目标课程名称")
    course_progress: float = Field(..., description="课程学习进度，范围 0~1")
    today_topic: str = Field(..., description="今日学习主题")
    today_estimated_time: str = Field(..., description="今日预计学习时间")
    today_progress: float = Field(..., description="今日任务进度，范围 0~1")
    study_hours: float = Field(..., description="累计学习小时数")
    completed_tasks: int = Field(..., description="已完成任务数")
    average_accuracy: float = Field(..., description="练习平均正确率，范围 0~1")
    weak_points: list[str] = Field(default_factory=list, description="薄弱知识点")
    recommend_count: int = Field(..., description="可推荐资源数量")
