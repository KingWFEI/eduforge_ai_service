from enum import IntEnum
from typing import Any, Generic, Optional, TypeVar

from fastapi import status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorCode(IntEnum):
    """业务错误码枚举"""
    SUCCESS = 0
    PARAM_ERROR = 40000
    LOGIN_FAILED = 40001
    UNAUTHORIZED = 40100
    FORBIDDEN = 40300
    NOT_FOUND = 40400
    CONFLICT = 40900
    RATE_LIMITED = 42900
    SERVER_ERROR = 50000
    LLM_ERROR = 51000
    KNOWLEDGE_RETRIEVAL_ERROR = 52000
    AGENT_TASK_ERROR = 53000


T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应格式"""
    code: int = ErrorCode.SUCCESS
    message: str = "success"
    data: Optional[T] = None


class AppException(Exception):
    """业务异常：携带错误码和 HTTP 状态码"""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        data: Any = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.data = data


def success(data: Any = None, message: str = "success") -> dict[str, Any]:
    """返回成功响应的统一格式"""
    return {
        "code": ErrorCode.SUCCESS,
        "message": message,
        "data": jsonable_encoder(data),
    }


def fail(
    code: ErrorCode,
    message: str,
    status_code: int = status.HTTP_400_BAD_REQUEST,
    data: Any = None,
) -> JSONResponse:
    """返回失败响应的统一格式（JSONResponse，携带 HTTP 状态码）"""
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "data": jsonable_encoder(data),
        },
    )
