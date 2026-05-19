import time

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError

from app.api.v1 import admin_onboarding, auth, courses, onboarding, users
from app.utils.logging_config import setup_logging
from app.utils.response import AppException, ErrorCode, fail, success

# 配置日志
logger = setup_logging()

# 创建 FastAPI 应用实例
app = FastAPI(
    title="FastAPI Demo Backend",
    description="FastAPI demo backend service",
    version="0.4.0",
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """HTTP 请求日志中间件：记录请求耗时、来源 IP 和状态"""
    start_time = time.perf_counter()
    client_host = request.client.host if request.client else "-"

    try:
        response = await call_next(request)
    except Exception:
        process_time_ms = (time.perf_counter() - start_time) * 1000
        logger.exception(
            "request failed | method=%s path=%s client=%s duration_ms=%.2f",
            request.method,
            request.url.path,
            client_host,
            process_time_ms,
        )
        raise

    process_time_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        "request completed | method=%s path=%s status=%s client=%s duration_ms=%.2f",
        request.method,
        request.url.path,
        response.status_code,
        client_host,
        process_time_ms,
    )
    response.headers["X-Process-Time-Ms"] = f"{process_time_ms:.2f}"
    return response


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """统一业务异常处理器"""
    return fail(
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        data=exc.data,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """请求参数校验异常处理器"""
    return fail(
        code=ErrorCode.PARAM_ERROR,
        message="参数错误",
        status_code=status.HTTP_400_BAD_REQUEST,
        data=exc.errors(),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP 异常处理器（将 FastAPI 原生异常转换为统一格式）"""
    code_map = {
        status.HTTP_401_UNAUTHORIZED: ErrorCode.UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: ErrorCode.FORBIDDEN,
        status.HTTP_404_NOT_FOUND: ErrorCode.NOT_FOUND,
        status.HTTP_409_CONFLICT: ErrorCode.CONFLICT,
    }
    return fail(
        code=code_map.get(exc.status_code, ErrorCode.PARAM_ERROR),
        message=str(exc.detail),
        status_code=exc.status_code,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """未捕获异常兜底处理器"""
    logger.exception("unhandled exception | path=%s", request.url.path)
    return fail(
        code=ErrorCode.SERVER_ERROR,
        message="服务异常",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


@app.get("/")
def root():
    """健康检查端点"""
    return success({"message": "FastAPI backend is running"})


# ─── 注册路由 ─────────────────────────────────────────
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(courses.router, prefix="/api")
app.include_router(onboarding.router, prefix="/api")
app.include_router(admin_onboarding.router, prefix="/api")
