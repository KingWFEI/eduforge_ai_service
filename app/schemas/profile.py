from typing import List, Optional

from pydantic import BaseModel, Field


class StudentProfileMeResponse(BaseModel):
    profile_id: Optional[str] = Field(None, description="画像ID")
    student_id: str = Field(..., description="学生ID")
    name: Optional[str] = Field(None, description="学生姓名")

    major: Optional[str] = Field(None, description="专业")
    grade: Optional[str] = Field(None, description="年级")
    target_course_id: Optional[str] = Field(None, description="目标课程ID")
    target_course: Optional[str] = Field(None, description="目标课程名称")

    learning_goals: List[str] = Field(default_factory=list, description="学习目标")
    coding_level: Optional[str] = Field(None, description="编程基础")
    math_level: Optional[str] = Field(None, description="数学基础")
    course_level: Optional[str] = Field(None, description="课程基础")

    learning_preferences: List[str] = Field(default_factory=list, description="学习偏好")
    weaknesses: List[str] = Field(default_factory=list, description="薄弱点")
    cognitive_style: List[str] = Field(default_factory=list, description="认知风格")

    time_budget: Optional[str] = Field(None, description="学习时间预算")
    summary: Optional[str] = Field(None, description="画像总结")
    confidence: Optional[float] = Field(None, description="画像置信度")
    source: Optional[str] = Field(None, description="画像来源")
    last_updated: Optional[str] = Field(None, description="最后更新时间")