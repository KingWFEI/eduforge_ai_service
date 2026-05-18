from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PageResponse(BaseModel, Generic[T]):
    """分页响应的通用数据结构"""
    items: list[T]
    total: int
    page: int
    page_size: int
