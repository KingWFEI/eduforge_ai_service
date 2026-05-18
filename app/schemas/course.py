from typing import Optional

from pydantic import BaseModel


class CourseCreate(BaseModel):
    """创建课程请求"""
    name: str
    description: Optional[str] = None


class CourseResponse(BaseModel):
    """课程信息响应"""
    id: int
    name: str
    description: Optional[str] = None
    created_by: Optional[int] = None

    class Config:
        from_attributes = True


class CourseFileResponse(BaseModel):
    """课程文件响应"""
    id: int
    course_id: int
    filename: str
    file_path: str
    file_type: Optional[str] = None

    class Config:
        from_attributes = True
