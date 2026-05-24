from typing import Optional

from pydantic import BaseModel


class CourseCreate(BaseModel):
    """创建课程请求"""
    course_id: str
    name: str
    description: Optional[str] = None


class CourseResponse(BaseModel):
    """课程信息响应"""
    id: int
    course_id: str
    name: str
    description: Optional[str] = None
    cover_url: Optional[str] = None
    semester: Optional[str] = None
    status: Optional[str] = None
    created_by: Optional[int] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class CourseFileResponse(BaseModel):
    """课程文件响应"""
    id: str
    course_id: str
    filename: str
    file_path: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    parse_status: Optional[str] = None

    class Config:
        from_attributes = True
