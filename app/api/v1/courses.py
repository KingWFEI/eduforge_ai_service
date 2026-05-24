import os

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.core.dependencies import get_current_user, require_role
from app.db.session import get_db
from app.models.course import Course
from app.models.course_structure import CourseDocument
from app.models.user import User
from app.schemas.course import CourseCreate, CourseFileResponse, CourseResponse
from app.schemas.common import PageResponse
from app.utils.response import ApiResponse, AppException, ErrorCode, success

router = APIRouter(prefix="/courses", tags=["课程"])


@router.post("/", response_model=ApiResponse[CourseResponse])
def create_course(
    course: CourseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """创建课程（教师/管理员权限）"""
    new_course = Course(
        course_id=course.course_id,
        name=course.name,
        description=course.description,
        created_by=current_user.id,
    )

    db.add(new_course)
    db.commit()
    db.refresh(new_course)

    return success(new_course)


@router.get("/", response_model=ApiResponse[PageResponse[CourseResponse]])
def get_courses(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """分页查询课程列表"""
    query = db.query(Course)
    total = query.count()
    courses = query.offset((page - 1) * page_size).limit(page_size).all()

    return success(
        PageResponse[CourseResponse](
            items=courses,
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/{course_id}", response_model=ApiResponse[CourseResponse])
def get_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取课程详情"""
    course = db.query(Course).filter(Course.id == course_id).first()

    if course is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="课程不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return success(course)


@router.post("/{course_id}/upload", response_model=ApiResponse[CourseFileResponse])
async def upload_course_file(
    course_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """上传课程文件（教师/管理员权限，支持 PDF/Word/Markdown/TXT）"""
    course = db.query(Course).filter(Course.course_id == course_id).first()

    if course is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="课程不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    allowed_extensions = {".pdf", ".docx", ".md", ".txt"}

    filename = file.filename or ""
    file_ext = os.path.splitext(filename)[1].lower()

    if file_ext not in allowed_extensions:
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message="只允许上传 PDF、Word、Markdown、TXT 文件",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)

    save_path = os.path.join(upload_dir, filename)

    with open(save_path, "wb") as f:
        content = await file.read()
        f.write(content)

    new_file = CourseDocument(
        course_id=course_id,
        filename=filename,
        file_path=save_path,
        file_type=file_ext,
    )

    db.add(new_file)
    db.commit()
    db.refresh(new_file)

    return success(new_file)
