import os
import time
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import OperationalError
from starlette.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import (
    agent_tasks,
    admin_learning_style_characters,
    admin_onboarding,
    admin_users,
    auth,
    courses,
    course_structure_drafts,
    dashboard,
    evaluation,
    exercise,
    home,
    knowledge,
    learning_path,
    onboarding,
    profile,
    profile_dialogue,
    resources,
    settings,
    student_learning_style,
    students,
    tutor,
    users,
)
from app.utils.openapi_zh import install_chinese_openapi
from app.utils.logging_config import setup_logging
from app.utils.response import AppException, ErrorCode, fail, success

# Configure logging
logger = setup_logging()
KNOWLEDGE_UPLOAD_MAX_MB = int(os.getenv("KNOWLEDGE_UPLOAD_MAX_MB", "50"))
KNOWLEDGE_UPLOAD_MAX_BYTES = KNOWLEDGE_UPLOAD_MAX_MB * 1024 * 1024


def _request_context(request: Request, request_id: str) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "path": request.url.path,
        "method": request.method,
        "query": str(request.url.query) or None,
        "client": request.client.host if request.client else None,
    }


def _validation_error_hint(error: dict[str, Any]) -> str:
    location = error.get("loc") or []
    field = ".".join(str(item) for item in location if item not in ("body", "query", "path"))
    message = error.get("msg") or "Invalid parameter format"
    if field:
        return f"Check parameter {field}: {message}"
    return f"Check request parameters: {message}"


def _format_validation_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    formatted_errors = []
    for error in errors:
        location = error.get("loc") or []
        formatted_errors.append(
            {
                "location": list(location),
                "field": ".".join(str(item) for item in location if item not in ("body", "query", "path")) or None,
                "message": error.get("msg"),
                "type": error.get("type"),
                "hint": _validation_error_hint(error),
            }
        )
    return formatted_errors


def _http_error_message_and_hint(
    request: Request,
    exc: StarletteHTTPException,
    allowed_methods: list[str],
) -> tuple[str, str]:
    if exc.status_code == status.HTTP_400_BAD_REQUEST:
        return f"Bad request: {exc.detail}", "Check parameters, JSON format, and Content-Type"
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        return f"Unauthorized or login expired: {exc.detail}", "Login again and send a valid Authorization token"
    if exc.status_code == status.HTTP_403_FORBIDDEN:
        return f"Forbidden: {exc.detail}", "Check whether the current user role can call this API"
    if exc.status_code == status.HTTP_404_NOT_FOUND:
        return f"API or resource not found: {request.method} {request.url.path}", "Check the URL, path parameters, or resource ID"
    if exc.status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
        allowed_text = ", ".join(allowed_methods) if allowed_methods else "the methods defined by this API"
        message = f"Method not allowed: {request.method} {request.url.path}. Allowed methods: {allowed_text}"
        hint = "Use one of the allowed HTTP methods shown in allowed_methods"
        if request.url.path.endswith("/upload") and "POST" in allowed_methods:
            hint = "This is an upload API. Do not open it with GET in the browser address bar; use POST + multipart/form-data"
        return message, hint
    if exc.status_code == status.HTTP_409_CONFLICT:
        return f"Conflict: {exc.detail}", "Check for duplicate creation, invalid state transition, or concurrent modification"
    if exc.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE:
        return f"Request body too large: {exc.detail}", "Compress or split the file, or increase the upload size limit"
    if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        return f"Too many requests: {exc.detail}", "Retry later or reduce request frequency"
    return f"HTTP request failed: {exc.detail}", "Check status_code, path, method, and request format"

# Create FastAPI app
app = FastAPI(
    title="EduForge AI 服务接口文档",
    description="EduForge AI 后端服务接口文档",
    version="0.4.0",
    debug=True
)
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log request duration, client IP, and status."""
    start_time = time.perf_counter()
    client_host = request.client.host if request.client else "-"

    if request.method == "POST" and request.url.path.startswith("/api/knowledge/upload/"):
        content_length = request.headers.get("content-length")
        content_length_value = int(content_length) if content_length and content_length.isdigit() else 0

        if content_length_value > KNOWLEDGE_UPLOAD_MAX_BYTES:
            process_time_ms = (time.perf_counter() - start_time) * 1000
            logger.warning(
                "upload rejected | method=%s path=%s client=%s content_length=%s max_bytes=%s duration_ms=%.2f",
                request.method,
                request.url.path,
                client_host,
                content_length,
                KNOWLEDGE_UPLOAD_MAX_BYTES,
                process_time_ms,
            )
            return fail(
                code=ErrorCode.PAYLOAD_TOO_LARGE,
                message=f"Upload file too large: max allowed size is {KNOWLEDGE_UPLOAD_MAX_MB}MB",
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                data={
                    "request": _request_context(request, str(uuid4())),
                    "content_length": content_length_value,
                    "max_bytes": KNOWLEDGE_UPLOAD_MAX_BYTES,
                    "hint": "Compress or split the file, or increase KNOWLEDGE_UPLOAD_MAX_MB",
                },
            )

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
async def detailed_app_exception_handler(request: Request, exc: AppException):
    request_id = str(uuid4())
    logger.warning(
        "app exception | request_id=%s path=%s method=%s code=%s message=%s",
        request_id,
        request.url.path,
        request.method,
        exc.code,
        exc.message,
    )
    return fail(
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        data={
            "request": _request_context(request, request_id),
            "error": exc.data,
            "hint": "Business error. Check code, message, error, and request context",
        },
    )


@app.exception_handler(RequestValidationError)
async def detailed_validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = str(uuid4())
    errors = _format_validation_errors(exc.errors())
    logger.warning(
        "validation exception | request_id=%s path=%s method=%s errors=%s",
        request_id,
        request.url.path,
        request.method,
        len(errors),
    )
    return fail(
        code=ErrorCode.PARAM_ERROR,
        message=f"Parameter error: {len(errors)} invalid field(s)",
        status_code=status.HTTP_400_BAD_REQUEST,
        data={
            "request": _request_context(request, request_id),
            "errors": errors,
            "hint": errors[0]["hint"] if errors else "Check whether request parameters match the API definition",
        },
    )


@app.exception_handler(OperationalError)
async def detailed_database_exception_handler(request: Request, exc: OperationalError):
    request_id = str(uuid4())
    logger.exception(
        "database exception | request_id=%s path=%s method=%s error_type=%s",
        request_id,
        request.url.path,
        request.method,
        exc.__class__.__name__,
    )
    return fail(
        code=ErrorCode.SERVER_ERROR,
        message="Database unavailable: cannot connect to MySQL",
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        data={
            "request": _request_context(request, request_id),
            "error_type": exc.__class__.__name__,
            "hint": "Check DB_HOST, DB_PORT, MySQL service status, firewall, VPN, and network access",
        },
    )


@app.exception_handler(StarletteHTTPException)
async def detailed_http_exception_handler(request: Request, exc: StarletteHTTPException):
    request_id = str(uuid4())
    allowed_methods = []
    if exc.status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
        allow_header = (exc.headers or {}).get("Allow")
        if allow_header:
            allowed_methods = [method.strip() for method in allow_header.split(",") if method.strip()]

    logger.warning(
        "http exception | request_id=%s path=%s method=%s status=%s detail=%s allowed_methods=%s",
        request_id,
        request.url.path,
        request.method,
        exc.status_code,
        exc.detail,
        ",".join(allowed_methods) if allowed_methods else "-",
    )
    code_map = {
        status.HTTP_401_UNAUTHORIZED: ErrorCode.UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: ErrorCode.FORBIDDEN,
        status.HTTP_404_NOT_FOUND: ErrorCode.NOT_FOUND,
        status.HTTP_405_METHOD_NOT_ALLOWED: ErrorCode.METHOD_NOT_ALLOWED,
        status.HTTP_409_CONFLICT: ErrorCode.CONFLICT,
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: ErrorCode.PAYLOAD_TOO_LARGE,
        status.HTTP_429_TOO_MANY_REQUESTS: ErrorCode.RATE_LIMITED,
    }
    message, hint = _http_error_message_and_hint(request, exc, allowed_methods)
    return fail(
        code=code_map.get(exc.status_code, ErrorCode.PARAM_ERROR),
        message=message,
        status_code=exc.status_code,
        data={
            "request": _request_context(request, request_id),
            "status_code": exc.status_code,
            "detail": exc.detail,
            "allowed_methods": allowed_methods or None,
            "hint": hint,
        },
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def detailed_unhandled_exception_handler(request: Request, exc: Exception):
    request_id = str(uuid4())
    logger.exception(
        "unhandled exception | request_id=%s path=%s method=%s error_type=%s",
        request_id,
        request.url.path,
        request.method,
        exc.__class__.__name__,
    )
    data = {
        "request": _request_context(request, request_id),
        "error_type": exc.__class__.__name__,
        "hint": "Unhandled server exception. Use request_id to find the full stack trace in server logs",
    }
    if app.debug:
        data["detail"] = str(exc)
    return fail(
        code=ErrorCode.SERVER_ERROR,
        message="Server error: unexpected exception while processing request",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        data=data,
    )


@app.get("/")
def root():
    """Health check endpoint."""
    return success({"message": "FastAPI backend is running"})


@app.get("/api/health")
def health_check():
    """Public service health check."""
    return success(
        {
            "status": "ok",
            "service": "eduforge-ai-service",
            "version": app.version,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
    )


# Register routes
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(courses.router, prefix="/api")
app.include_router(course_structure_drafts.router, prefix="/api")
app.include_router(home.router)
app.include_router(onboarding.router, prefix="/api")
app.include_router(admin_onboarding.router, prefix="/api")
app.include_router(admin_learning_style_characters.router, prefix="/api")
app.include_router(admin_users.router, prefix="/api")

app.include_router(profile.router, prefix="/api")
app.include_router(learning_path.router, prefix="/api")
app.include_router(exercise.router, prefix="/api")
app.include_router(evaluation.router, prefix="/api")
app.include_router(resources.router, prefix="/api")
app.include_router(agent_tasks.router, prefix="/api")
app.include_router(agent_tasks.task_alias_router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(students.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(student_learning_style.router, prefix="/api")
app.include_router(profile_dialogue.router, prefix="/api")
app.include_router(knowledge.router, prefix="/api")
app.include_router(tutor.router, prefix="/api")

install_chinese_openapi(app)
