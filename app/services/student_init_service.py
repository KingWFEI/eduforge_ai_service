import json
import uuid
from typing import Any, Dict, List

from sqlalchemy import text
from sqlalchemy.orm import Session


def _safe_list(value: Any) -> List[str]:
    """确保画像里的 JSON 字段最终是 list。"""
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return []


def _extract_minutes(time_budget: str | None) -> int:

    if not time_budget:
        return 0

    digits = "".join(ch for ch in time_budget if ch.isdigit())

    if not digits:
        return 0

    return int(digits)


def _resolve_or_create_course_id(
    db: Session,
    target_course: str,
    student_id: str,
) -> str:
    course = db.execute(
        text(
            """
            SELECT course_id
            FROM courses
            WHERE name = :target_course
            LIMIT 1
            """
        ),
        {"target_course": target_course},
    ).mappings().first()
    if course:
        return course["course_id"]

    course = db.execute(
        text(
            """
            SELECT course_id
            FROM courses
            WHERE :target_course LIKE CONCAT('%', name, '%')
               OR name LIKE CONCAT('%', :target_course, '%')
            ORDER BY id ASC
            LIMIT 1
            """
        ),
        {"target_course": target_course},
    ).mappings().first()
    if course:
        return course["course_id"]

    course_id = "course_" + uuid.uuid4().hex[:12]
    db.execute(
        text(
            """
            INSERT INTO courses (
                course_id,
                name,
                description,
                cover_url,
                semester,
                status,
                created_by,
                created_at,
                updated_at
            )
            VALUES (
                :course_id,
                :name,
                :description,
                NULL,
                '2026春季',
                'active',
                :created_by,
                NOW(),
                NOW()
            )
            """
        ),
        {
            "course_id": course_id,
            "name": target_course,
            "description": f"{target_course}个性化学习课程",
            "created_by": student_id,
        },
    )
    return course_id


def initialize_student_learning_data(
    db: Session,
    student_id: str,
    profile: Dict[str, Any],
) -> None:
    """
    根据学生画像，自动初始化学习路径、今日任务、推荐资源。

    当前是最小可运行版：
    1. 如果该学生已经有 active 学习路径，就不重复生成
    2. 根据 weaknesses 生成学习任务
    3. 根据 weaknesses 生成推荐资源
    """

    # 1. 如果已经有学习路径，不重复初始化
    existing_path = db.execute(
        text(
            """
            SELECT id
            FROM learning_paths
            WHERE student_id = :student_id
              AND status = 'active'
            LIMIT 1
            """
        ),
        {"student_id": student_id},
    ).mappings().first()

    if existing_path:
        return

    target_course = profile.get("target_course")
    weaknesses = _safe_list(profile.get("weaknesses"))
    learning_preferences = _safe_list(profile.get("learning_preferences"))
    time_budget = profile.get("time_budget")
    daily_minutes = _extract_minutes(time_budget) if time_budget else 0

    if not target_course or not weaknesses:
        return

    # 2. 确保课程存在，优先复用当前课程表中同名或近似同名课程
    course_id = _resolve_or_create_course_id(
        db=db,
        target_course=target_course,
        student_id=student_id,
    )

    # 3. 创建学习路径
    path_id = "path_" + uuid.uuid4().hex[:12]

    db.execute(
        text(
            """
            INSERT INTO learning_paths (
                id,
                student_id,
                course_id,
                title,
                goal,
                duration_days,
                daily_minutes,
                progress,
                status,
                plan_json
            )
            VALUES (
                :id,
                :student_id,
                :course_id,
                :title,
                :goal,
                :duration_days,
                :daily_minutes,
                0,
                'active',
                :plan_json
            )
            """
        ),
        {
            "id": path_id,
            "student_id": student_id,
            "course_id": course_id,
            "title": f"{target_course}个性化学习路径",
            "goal": f"围绕{target_course}进行基础学习，并重点补强：{'、'.join(weaknesses)}。",
            "duration_days": max(len(weaknesses), 3),
            "daily_minutes": daily_minutes,
            "plan_json": json.dumps(
            {
                    "target_course": target_course,
                    "weaknesses": weaknesses,
                    "learning_preferences": learning_preferences,
                    "time_budget": time_budget,
                },
                ensure_ascii=False,
            ),
        },
    )

    # 4. 创建学习任务
    for index, weakness in enumerate(weaknesses, start=1):
        task_id = "task_" + uuid.uuid4().hex[:12]

        db.execute(
            text(
                """
                INSERT INTO learning_path_tasks (
                    id,
                    path_id,
                    day_no,
                    topic,
                    description,
                    estimated_minutes,
                    resource_ids_json,
                    status,
                    completed_at,
                    created_at
                )
                VALUES (
                    :id,
                    :path_id,
                    :day_no,
                    :topic,
                    :description,
                    :estimated_minutes,
                    :resource_ids_json,
                    'pending',
                    NULL,
                    NOW()
                )
                """
            ),
            {
                "id": task_id,
                "path_id": path_id,
                "day_no": index,
                "topic": f"{weakness}基础学习",
                "description": f"结合{target_course}课程内容，重点理解{weakness}的基本概念和常见应用。",
                "estimated_minutes": daily_minutes,
                "resource_ids_json": json.dumps([], ensure_ascii=False),
            },
        )

    # 5. 创建推荐资源
    for index, weakness in enumerate(weaknesses, start=1):
        resource_id = "res_" + uuid.uuid4().hex[:12]

        resource_type = "document"
        if "图解讲解" in learning_preferences:
            resource_type = "document"
        elif "代码案例" in learning_preferences:
            resource_type = "code_case"

        db.execute(
            text(
                """
                INSERT INTO learning_resources (
                    id,
                    student_id,
                    course_id,
                    knowledge_point_id,
                    title,
                    type,
                    difficulty,
                    description,
                    reason,
                    content_text,
                    review_status,
                    created_at,
                    updated_at
                )
                VALUES (
                    :id,
                    :student_id,
                    :course_id,
                    NULL,
                    :title,
                    :type,
                    '基础',
                    :description,
                    :reason,
                    :content_text,
                    'approved',
                    NOW(),
                    NOW()
                )
                """
            ),
            {
                "id": resource_id,
                "student_id": student_id,
                "course_id": course_id,
                "title": f"{weakness}图解学习资料",
                "type": resource_type,
                "description": f"面向初学者的{weakness}基础学习资料。",
                "reason": f"你的画像显示需要重点补强{weakness}，因此推荐先学习这份基础资料。",
                "content_text": (
                    f"{weakness}是{target_course}学习中的重要内容。"
                    f"建议你先理解它的基本含义，再结合例子和练习逐步掌握。"
                ),
            },
        )

    db.commit()
