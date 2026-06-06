# app/api/v1/home.py

from typing import Union

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.core.dependencies import require_role
from app.db.session import get_db
from app.models import User
from app.schemas.home import AddHomeCourseRequest
from app.services.home_service import HomeService


router = APIRouter(prefix="/api/home", tags=["阶段3-首页课程"])


@router.get("/courses")
def get_home_courses(
        db: Session = Depends(get_db),
        current_user: User = Depends(require_role(Role.STUDENT)),
):
    """
    阶段 3.1：获取学生已经选择的课程。

    Flutter 首页初始化时调用。
    """

    student_id = current_user.id

    service = HomeService(db)

    data = service.get_home_courses(student_id=student_id)

    return {
        "code": 0,
        "message": "success",
        "data": data
    }


@router.post("/courses")
def add_home_course(
    req: AddHomeCourseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    """
    阶段 3.3：添加课程到学生首页。

    Flutter 课程选择页点击"添加课程"时调用。
    """

    student_id = current_user.id

    service = HomeService(db)

    try:
        data = service.add_home_course(
            student_id=student_id,
            course_id=req.course_id
        )

        return {
            "code": 0,
            "message": "课程添加成功",
            "data": data
        }

    except ValueError as e:
        message = str(e)

        if message == "课程不存在":
            return {
                "code": 40401,
                "message": "课程不存在",
                "data": None
            }

        if message == "课程不可添加":
            return {
                "code": 40001,
                "message": "课程不可添加",
                "data": None
            }

        return {
            "code": 40000,
            "message": message,
            "data": None
        }


@router.delete("/courses/{course_id}")
def remove_home_course(
    course_id: Union[int, str],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    """
    阶段 3.4：从学生首页移除课程。

    注意：
    只把 student_learning_contexts.status 改成 removed，
    不删除课程本身。
    """

    student_id = current_user.id

    service = HomeService(db)

    try:
        data = service.remove_home_course(
            student_id=student_id,
            course_id=course_id
        )

        return {
            "code": 0,
            "message": "课程已移除",
            "data": data
        }

    except ValueError as e:
        message = str(e)

        if message == "当前学生未添加该课程":
            return {
                "code": 40401,
                "message": "当前学生未添加该课程",
                "data": None
            }

        return {
            "code": 40000,
            "message": message,
            "data": None
        }
