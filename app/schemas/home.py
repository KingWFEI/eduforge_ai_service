from datetime import datetime
from typing import List, Optional, Union

from pydantic import BaseModel, Field


class HomeCourseItem(BaseModel):
    """
    首页课程卡片数据。
    对应新版阶段 3 的 selected_courses 数组元素。
    """

    course_id: Union[int, str]
    course_name: str

    progress: float = Field(default=0.0, ge=0.0, le=1.0)

    today_suggestion: Optional[str] = None
    today_topic: Optional[str] = None
    today_estimated_time: Optional[str] = None

    study_hours: float = 0.0
    average_accuracy: float = Field(default=0.0, ge=0.0, le=1.0)

    cover_color: Optional[str] = None
    last_study_at: Optional[datetime] = None


class HomeCoursesData(BaseModel):
    """
    GET /api/home/courses 的 data 部分。
    """

    selected_courses: List[HomeCourseItem]
    max_home_display: int = 3


class AddHomeCourseRequest(BaseModel):
    """
    POST /api/home/courses 请求体。
    """

    course_id: Union[int, str]


class AddHomeCourseData(BaseModel):
    """
    POST /api/home/courses 返回 data。
    """

    course_id: Union[int, str]
    course_name: str
    status: str


class RemoveHomeCourseData(BaseModel):
    """
    DELETE /api/home/courses/{course_id} 返回 data。
    """

    course_id: Union[int, str]
    status: str