import uuid
from fastapi import status

from app.utils.response import AppException, ErrorCode

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.user import User


def get_recommended_resources(db: Session, current_user: User) -> dict:
    """
    阶段 3.3：获取当前学生推荐资源列表。

    先做最小可运行版：
    1. 查询当前学生自己的资源
    2. 只返回 approved / auto_passed 的资源
    3. 按创建顺序倒序返回
    """

    student_id = str(current_user.id)

    rows = db.execute(
        text(
            """
            SELECT
                id,
                title,
                type,
                difficulty,
                description,
                reason,
                review_status
            FROM learning_resources
            WHERE student_id = :student_id
              AND review_status IN ('approved', 'auto_passed')
            ORDER BY id DESC
            """
        ),
        {"student_id": student_id},
    ).mappings().all()

    items = []
    for row in rows:
        items.append(
            {
                "resource_id": row["id"],
                "title": row["title"],
                "type": row["type"],
                "difficulty": row["difficulty"],
                "description": row["description"],
                "reason": row["reason"],
                "review_status": row["review_status"],
            }
        )

    return {
        "items": items,
        "total": len(items),
    }

def get_resource_detail(db: Session, current_user: User, resource_id: str) -> dict:
    """
    阶段 3.4：获取资源详情。

    权限规则：
    1. 学生只能查看自己的资源
    2. 资源必须是 approved / auto_passed
    """

    student_id = str(current_user.id)

    row = db.execute(
        text(
            """
            SELECT
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
                content_json,
                review_status,
                created_at,
                updated_at
            FROM learning_resources
            WHERE id = :resource_id
              AND student_id = :student_id
              AND review_status IN ('approved', 'auto_passed')
            LIMIT 1
            """
        ),
        {
            "resource_id": resource_id,
            "student_id": student_id,
        },
    ).mappings().first()

    if row is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="学习资源不存在或无权限访问",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return {
        "resource_id": row["id"],
        "student_id": str(row["student_id"]) if row["student_id"] is not None else None,
        "course_id": str(row["course_id"]) if row["course_id"] is not None else None,
        "knowledge_point_id": str(row["knowledge_point_id"]) if row["knowledge_point_id"] is not None else None,
        "title": row["title"],
        "type": row["type"],
        "difficulty": row["difficulty"],
        "description": row["description"],
        "reason": row["reason"],
        "content_text": row["content_text"],
        "content_json": row["content_json"],
        "review_status": row["review_status"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }

def submit_resource_feedback(
    db: Session,
    current_user: User,
    resource_id: str,
    feedback_data,
) -> dict:
    """
    阶段 3.5：提交资源反馈。

    规则：
    1. 学生只能反馈自己能访问的资源
    2. 如果以前反馈过，就更新
    3. 如果没有反馈过，就新增
    """

    student_id = str(current_user.id)

    # 1. 先确认资源存在，并且属于当前学生
    resource = db.execute(
        text(
            """
            SELECT id
            FROM learning_resources
            WHERE id = :resource_id
              AND student_id = :student_id
              AND review_status IN ('approved', 'auto_passed')
            LIMIT 1
            """
        ),
        {
            "resource_id": resource_id,
            "student_id": student_id,
        },
    ).mappings().first()

    if resource is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="学习资源不存在或无权限反馈",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # 2. 查看是否已经反馈过
    existing = db.execute(
        text(
            """
            SELECT id
            FROM resource_feedback
            WHERE resource_id = :resource_id
              AND student_id = :student_id
            LIMIT 1
            """
        ),
        {
            "resource_id": resource_id,
            "student_id": student_id,
        },
    ).mappings().first()

    liked = feedback_data.liked
    favorite = feedback_data.favorite
    difficulty_feedback = feedback_data.difficulty_feedback
    comment = feedback_data.comment

    # 3. 已存在：更新
    if existing:
        feedback_id = existing["id"]

        db.execute(
            text(
                """
                UPDATE resource_feedback
                SET liked = :liked,
                    favorite = :favorite,
                    difficulty_feedback = :difficulty_feedback,
                    comment = :comment,
                    updated_at = NOW()
                WHERE id = :feedback_id
                """
            ),
            {
                "feedback_id": feedback_id,
                "liked": liked,
                "favorite": favorite,
                "difficulty_feedback": difficulty_feedback,
                "comment": comment,
            },
        )
        db.commit()

    # 4. 不存在：新增
    else:
        feedback_id = "fb_" + uuid.uuid4().hex[:12]

        db.execute(
            text(
                """
                INSERT INTO resource_feedback (
                    id,
                    resource_id,
                    student_id,
                    liked,
                    favorite,
                    difficulty_feedback,
                    comment,
                    created_at,
                    updated_at
                )
                VALUES (
                    :id,
                    :resource_id,
                    :student_id,
                    :liked,
                    :favorite,
                    :difficulty_feedback,
                    :comment,
                    NOW(),
                    NOW()
                )
                """
            ),
            {
                "id": feedback_id,
                "resource_id": resource_id,
                "student_id": student_id,
                "liked": liked,
                "favorite": favorite,
                "difficulty_feedback": difficulty_feedback,
                "comment": comment,
            },
        )
        db.commit()

    return {
        "feedback_id": feedback_id,
        "resource_id": resource_id,
        "student_id": student_id,
        "liked": liked,
        "favorite": favorite,
        "difficulty_feedback": difficulty_feedback,
        "comment": comment,
    }

def record_resource_view(
    db: Session,
    current_user: User,
    resource_id: str,
) -> dict:
    """
    记录学生查看学习资源的行为。

    作用：
    1. 校验资源是否属于当前学生
    2. 写入 study_records
    3. 后续首页 study_hours 可以统计到这部分学习时间
    """

    student_id = str(current_user.id)

    # 1. 确认资源存在，并且当前学生有权限查看
    resource_row = db.execute(
        text(
            """
            SELECT
                id,
                student_id,
                course_id,
                title,
                review_status
            FROM learning_resources
            WHERE id = :resource_id
              AND student_id = :student_id
              AND review_status IN ('approved', 'auto_passed')
            LIMIT 1
            """
        ),
        {
            "resource_id": resource_id,
            "student_id": student_id,
        },
    ).mappings().first()

    if resource_row is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="学习资源不存在或无权限访问",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # 2. 写入学习记录
    study_record_id = "study_" + uuid.uuid4().hex[:12]
    study_minutes = 5

    db.execute(
        text(
            """
            INSERT INTO study_records (
                id,
                student_id,
                course_id,
                resource_id,
                path_task_id,
                action_type,
                study_minutes,
                progress_delta,
                created_at
            )
            VALUES (
                :id,
                :student_id,
                :course_id,
                :resource_id,
                NULL,
                'view_resource',
                :study_minutes,
                0,
                NOW()
            )
            """
        ),
        {
            "id": study_record_id,
            "student_id": student_id,
            "course_id": resource_row["course_id"],
            "resource_id": resource_id,
            "study_minutes": study_minutes,
        },
    )

    db.commit()

    return {
        "resource_id": resource_id,
        "student_id": student_id,
        "course_id": str(resource_row["course_id"]) if resource_row["course_id"] else None,
        "study_record_id": study_record_id,
        "study_minutes_added": study_minutes,
        "action_type": "view_resource",
    }