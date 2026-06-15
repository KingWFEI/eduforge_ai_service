from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.core.dependencies import get_current_admin, require_role
from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.admin_student import AdminStudentLearningData
from app.schemas.common import PageResponse
from app.schemas.user import AdminUserCreate, UserResponse
from app.services.admin_student_service import get_student_learning_data, list_student_learning_data
from app.utils.response import ApiResponse, AppException, ErrorCode, success
from app.utils.user_utils import user_to_response

router = APIRouter(prefix="/admin/users", tags=["管理端用户管理"])

VALID_ROLES = {Role.STUDENT.value, Role.TEACHER.value, Role.ADMIN.value}


@router.post("/", response_model=ApiResponse[UserResponse])
def create_user(
    payload: AdminUserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """管理员创建用户（可创建 student / teacher / admin）"""
    if payload.role.value not in VALID_ROLES:
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message="用户角色不合法",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if db.query(User).filter(User.username == payload.username).first():
        raise AppException(
            code=ErrorCode.CONFLICT,
            message="用户名已存在",
            status_code=status.HTTP_409_CONFLICT,
        )

    if payload.phone and db.query(User).filter(User.phone == payload.phone).first():
        raise AppException(
            code=ErrorCode.CONFLICT,
            message="手机号已存在",
            status_code=status.HTTP_409_CONFLICT,
        )

    if payload.email and db.query(User).filter(User.email == payload.email).first():
        raise AppException(
            code=ErrorCode.CONFLICT,
            message="邮箱已存在",
            status_code=status.HTTP_409_CONFLICT,
        )

    new_user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        role=payload.role.value,
        avatar_url="",
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return success(user_to_response(new_user), message="用户创建成功")


@router.get(
    "/students/learning-data",
    response_model=ApiResponse[PageResponse[AdminStudentLearningData]],
)
def list_students_learning_data(
    keyword: str | None = Query(None, description="按用户名、姓名、手机号或邮箱搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """老师和管理员分页查看所有学生的画像、资源、薄弱点等学习数据。"""
    items, total = list_student_learning_data(
        db=db,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return success(
        PageResponse[AdminStudentLearningData](
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get(
    "/students/{student_id}/learning-data",
    response_model=ApiResponse[AdminStudentLearningData],
)
def read_student_learning_data(
    student_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """老师和管理员查看指定学生的完整学习数据。"""
    return success(get_student_learning_data(db=db, student_id=student_id))
