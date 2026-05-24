import json
from typing import Any

from fastapi import status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.user import User
from app.services.student_init_service import initialize_student_learning_data
from app.utils.response import AppException, ErrorCode


def _parse_json_array(value: Any) -> list:
    """
    把数据库里的 JSON 字段转成 Python list。

    有些 MySQL 驱动会直接返回 list；
    有些会返回字符串；
    有些为空。
    这个函数统一处理。
    """
    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []

    return []


def get_my_profile(db: Session, current_user: User) -> dict:
    """
    获取当前登录学生的学习画像。
    """

    student_id = str(current_user.id)

    row = db.execute(
        text(
            """
            SELECT
                sp.id,
                sp.student_id,
                sp.major,
                sp.grade,
                sp.target_course_id,
                sp.target_course,
                sp.learning_goals_json,
                sp.coding_level,
                sp.math_level,
                sp.course_level,
                sp.learning_preferences_json,
                sp.weaknesses_json,
                sp.cognitive_style_json,
                sp.time_budget,
                sp.summary,
                sp.confidence,
                sp.source,
                sp.last_updated,
                u.name
            FROM student_profiles sp
            LEFT JOIN users u ON u.id = sp.student_id
            WHERE sp.student_id = :student_id
            LIMIT 1
            """
        ),
        {"student_id": student_id},
    ).mappings().first()

    if row is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="当前学生还没有学习画像，请先完成引导问卷",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return {
        "profile_id": row["id"],
        "student_id": str(row["student_id"]),
        "name": row["name"],
        "major": row["major"],
        "grade": row["grade"],
        "target_course_id": str(row["target_course_id"]) if row["target_course_id"] else None,
        "target_course": row["target_course"],
        "learning_goals": _parse_json_array(row["learning_goals_json"]),
        "coding_level": row["coding_level"],
        "math_level": row["math_level"],
        "course_level": row["course_level"],
        "learning_preferences": _parse_json_array(row["learning_preferences_json"]),
        "weaknesses": _parse_json_array(row["weaknesses_json"]),
        "cognitive_style": _parse_json_array(row["cognitive_style_json"]),
        "time_budget": row["time_budget"],
        "summary": row["summary"],
        "confidence": float(row["confidence"]) if row["confidence"] is not None else None,
        "source": row["source"],
        "last_updated": row["last_updated"].isoformat() if row["last_updated"] else None,
    }

def init_my_learning_data(db: Session, current_user: User) -> dict:
    """
    根据当前学生已有画像，补生成学习路径、任务和推荐资源。
    """

    student_id = str(current_user.id)

    row = db.execute(
        text(
            """
            SELECT
                id,
                student_id,
                target_course,
                learning_goals_json,
                coding_level,
                math_level,
                course_level,
                learning_preferences_json,
                weaknesses_json,
                cognitive_style_json,
                time_budget,
                summary,
                confidence
            FROM student_profiles
            WHERE student_id = :student_id
            LIMIT 1
            """
        ),
        {"student_id": student_id},
    ).mappings().first()

    if row is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="当前学生还没有学习画像，无法初始化学习数据",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    initialize_student_learning_data(
        db=db,
        student_id=student_id,
        profile={
            "target_course": row["target_course"],
            "learning_goals": _parse_json_array(row["learning_goals_json"]),
            "coding_level": row["coding_level"],
            "math_level": row["math_level"],
            "course_level": row["course_level"],
            "learning_preferences": _parse_json_array(row["learning_preferences_json"]),
            "weaknesses": _parse_json_array(row["weaknesses_json"]),
            "cognitive_style": _parse_json_array(row["cognitive_style_json"]),
            "time_budget": row["time_budget"],
            "summary": row["summary"],
            "confidence": row["confidence"],
        },
    )

    return {
        "student_id": student_id,
        "message": "学习路径、任务和推荐资源初始化完成"
    }