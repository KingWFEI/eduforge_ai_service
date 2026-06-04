from typing import Any, Optional

from pydantic import BaseModel, Field


class StudentProfileMeResponse(BaseModel):
    profile_id: Optional[str] = Field(None, description="综合画像ID")
    student_id: str = Field(..., description="学生ID")
    name: Optional[str] = Field(None, description="学生姓名")
    learning_preferences: list[Any] = Field(default_factory=list, description="学习偏好")
    cognitive_traits: list[Any] = Field(default_factory=list, description="认知特点")
    learning_habits: list[Any] = Field(default_factory=list, description="学习习惯")
    motivation_factors: list[Any] = Field(default_factory=list, description="学习动力因素")
    general_strengths: list[Any] = Field(default_factory=list, description="通用学习优势")
    general_challenges: list[Any] = Field(default_factory=list, description="通用学习挑战")
    preferred_pace: Optional[str] = Field(None, description="偏好的学习节奏")
    available_time: dict[str, Any] = Field(default_factory=dict, description="可用学习时间")
    summary: Optional[str] = Field(None, description="综合画像总结")
    profile_dimensions: dict[str, Any] = Field(default_factory=dict, description="动态画像维度")
    evidence: list[Any] = Field(default_factory=list, description="画像证据")
    confidence: dict[str, Any] = Field(default_factory=dict, description="各维度置信度")
    version: int = Field(1, description="画像版本")
    source: Optional[str] = Field(None, description="画像来源")
    last_updated: Optional[str] = Field(None, description="最后更新时间")
