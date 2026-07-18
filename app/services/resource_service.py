import uuid
import json
from fastapi import status

from app.utils.response import AppException, ErrorCode

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.user import User


def _ensure_accessible_resource(db: Session, student_id: str, resource_id: str) -> dict:
    row = db.execute(
        text(
            """
            SELECT id, course_id, type
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

    return row


def _sync_resource_favorite(db: Session, student_id: str, resource_id: str, favorite: bool) -> bool:
    existing = db.execute(
        text(
            """
            SELECT id
            FROM resource_favorites
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

    if favorite and existing is None:
        db.execute(
            text(
                """
                INSERT INTO resource_favorites (
                    id,
                    resource_id,
                    student_id,
                    created_at
                )
                VALUES (
                    :id,
                    :resource_id,
                    :student_id,
                    NOW()
                )
                """
            ),
            {
                "id": "fav_" + uuid.uuid4().hex[:12],
                "resource_id": resource_id,
                "student_id": student_id,
            },
        )
    elif not favorite and existing is not None:
        db.execute(
            text(
                """
                DELETE FROM resource_favorites
                WHERE resource_id = :resource_id
                  AND student_id = :student_id
                """
            ),
            {
                "resource_id": resource_id,
                "student_id": student_id,
            },
        )

    return favorite


def _build_profile_update_hint(favorite: bool, difficulty_feedback: str | None, resource_type: str | None) -> str:
    resource_type_name = {
        "document": "讲解文档",
        "mind_map": "思维导图",
        "exercise": "练习题",
        "code_case": "代码案例",
        "video_script": "视频脚本",
    }.get(resource_type or "", "同类")

    if favorite:
        return f"系统将提高{resource_type_name}类资源的推荐权重。"
    if difficulty_feedback:
        return "系统将结合难度反馈优化后续资源推荐。"
    return "系统将结合本次反馈优化后续资源推荐。"


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


def list_my_resources(
    db: Session,
    current_user: User,
    resource_type: str | None = None,
    difficulty: str | None = None,
    course_id: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> dict:
    student_id = str(current_user.id)
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    where = ["lr.student_id = :student_id"]
    params = {
        "student_id": student_id,
        "limit": page_size,
        "offset": (page - 1) * page_size,
    }

    if resource_type:
        where.append("lr.type = :resource_type")
        params["resource_type"] = resource_type

    if difficulty:
        where.append("lr.difficulty = :difficulty")
        params["difficulty"] = difficulty

    if course_id:
        where.append("lr.course_id = :course_id")
        params["course_id"] = course_id

    where_sql = " AND ".join(where)

    total = db.execute(
        text(
            f"""
            SELECT COUNT(*) AS total
            FROM learning_resources lr
            WHERE {where_sql}
            """
        ),
        params,
    ).mappings().first()["total"]

    rows = db.execute(
        text(
            f"""
            SELECT
                lr.id,
                lr.title,
                lr.type,
                lr.difficulty,
                lr.description,
                lr.reason,
                lr.source,
                lr.review_status,
                lr.safety_score,
                lr.created_at,
                rf.id AS favorite_id
            FROM learning_resources lr
            LEFT JOIN resource_favorites rf
              ON rf.resource_id = lr.id
             AND rf.student_id = :student_id
            WHERE {where_sql}
            ORDER BY lr.created_at DESC, lr.id DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
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
                "source": row["source"],
                "status": row["review_status"],
                "rating": float(row["safety_score"]) if row["safety_score"] is not None else None,
                "favorite": row["favorite_id"] is not None,
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def parse_json_field(value, default=None):
    """
    把数据库里的 JSON 字段转换成 Python dict/list。
    """

    if default is None:
        default = {}

    if value is None:
        return default

    if isinstance(value, (dict, list)):
        return value

    if isinstance(value, str):
        if value.strip() == "":
            return default

        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {
                "raw": value
            }

    return value

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
                generation_scope,
                source_type,
                generation_mode,
                external_provider,
                external_id,
                file_url,
                preview_url,
                review_score,
                EXISTS (
                    SELECT 1
                    FROM resource_favorites rf
                    WHERE rf.resource_id = learning_resources.id
                      AND rf.student_id = :student_id
                ) AS favorite,
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

    content_json = parse_json_field(row["content_json"], default={})
    if isinstance(content_json, dict):
        if content_json.get("current_chapter_tree") is not None:
            content_json["tree"] = content_json["current_chapter_tree"]
        visualization = content_json.get("visualization")
        if isinstance(visualization, dict) and visualization.get("renderer") == "frontend_slides_html":
            visualization.setdefault("html_url", row["file_url"])
            visualization.setdefault("cover_url", row["preview_url"])

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
        "content_json": content_json,
        "generation_scope": row["generation_scope"],
        "source_type": row["source_type"],
        "generation_mode": row["generation_mode"],
        "external_provider": row["external_provider"],
        "external_id": row["external_id"],
        "file_url": row["file_url"] or (
            content_json.get("visualization", {}).get("html_url")
            if isinstance(content_json.get("visualization"), dict) else None
        ),
        "preview_url": row["preview_url"],
        "review_score": row["review_score"],
        "favorite": bool(row["favorite"]),
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
            SELECT id, type
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

    _sync_resource_favorite(db, student_id, resource_id, favorite)
    db.commit()

    return {
        "resource_id": resource_id,
        "profile_update_hint": _build_profile_update_hint(
            favorite=favorite,
            difficulty_feedback=difficulty_feedback,
            resource_type=resource["type"],
        ),
    }


def set_resource_favorite(
    db: Session,
    current_user: User,
    resource_id: str,
    favorite: bool,
) -> dict:
    student_id = str(current_user.id)
    _ensure_accessible_resource(db, student_id, resource_id)
    _sync_resource_favorite(db, student_id, resource_id, favorite)
    db.commit()

    return {
        "resource_id": resource_id,
        "favorite": favorite,
    }


def list_favorite_resources(
    db: Session,
    current_user: User,
    page: int = 1,
    page_size: int = 10,
) -> dict:
    student_id = str(current_user.id)
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    params = {
        "student_id": student_id,
        "limit": page_size,
        "offset": (page - 1) * page_size,
    }

    total = db.execute(
        text(
            """
            SELECT COUNT(*) AS total
            FROM resource_favorites rf
            JOIN learning_resources lr ON lr.id = rf.resource_id
            WHERE rf.student_id = :student_id
              AND lr.student_id = :student_id
              AND lr.review_status IN ('approved', 'auto_passed')
            """
        ),
        params,
    ).mappings().first()["total"]

    rows = db.execute(
        text(
            """
            SELECT
                lr.id,
                lr.title,
                lr.type,
                lr.difficulty,
                lr.created_at
            FROM resource_favorites rf
            JOIN learning_resources lr ON lr.id = rf.resource_id
            WHERE rf.student_id = :student_id
              AND lr.student_id = :student_id
              AND lr.review_status IN ('approved', 'auto_passed')
            ORDER BY rf.created_at DESC, lr.created_at DESC, lr.id DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()

    items = []
    for row in rows:
        items.append(
            {
                "resource_id": row["id"],
                "title": row["title"],
                "type": row["type"],
                "difficulty": row["difficulty"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def list_review_resources(
    db: Session,
    course_id: str | None = None,
    resource_type: str | None = None,
    review_status: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> dict:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    where = ["1 = 1"]
    params = {
        "limit": page_size,
        "offset": (page - 1) * page_size,
    }
    if course_id:
        where.append("lr.course_id = :course_id")
        params["course_id"] = course_id
    if resource_type:
        where.append("lr.type = :resource_type")
        params["resource_type"] = resource_type
    if review_status:
        where.append("lr.review_status = :review_status")
        params["review_status"] = review_status
    where_sql = " AND ".join(where)

    total = db.execute(
        text(
            f"""
            SELECT COUNT(*) AS total
            FROM learning_resources lr
            WHERE {where_sql}
            """
        ),
        params,
    ).mappings().first()["total"]
    rows = db.execute(
        text(
            f"""
            SELECT
                lr.id,
                lr.title,
                lr.type,
                c.name AS course,
                lr.review_status,
                lr.safety_score,
                lr.hallucination_risk,
                lr.created_at
            FROM learning_resources lr
            LEFT JOIN courses c ON c.course_id = lr.course_id
            WHERE {where_sql}
            ORDER BY lr.created_at DESC, lr.id DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()
    return {
        "items": [
            {
                "resource_id": row["id"],
                "title": row["title"],
                "type": row["type"],
                "course": row["course"],
                "review_status": row["review_status"],
                "safety_score": float(row["safety_score"]) if row["safety_score"] is not None else None,
                "hallucination_risk": row["hallucination_risk"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            for row in rows
        ],
        "total": int(total or 0),
        "page": page,
        "page_size": page_size,
    }


def review_resource(
    db: Session,
    current_user: User,
    resource_id: str,
    action: str,
    comment: str | None = None,
) -> dict:
    action_map = {
        "approve": "approved",
        "reject": "rejected",
        "need_modify": "need_modify",
        "regenerate": "need_modify",
    }
    if action not in action_map:
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message="action 仅支持 approve / reject / need_modify / regenerate",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    row = db.execute(
        text("SELECT id FROM learning_resources WHERE id = :resource_id LIMIT 1"),
        {"resource_id": resource_id},
    ).mappings().first()
    if row is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="资源不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    review_id = "review_" + uuid.uuid4().hex[:12]
    db.execute(
        text(
            """
            INSERT INTO resource_reviews (
                id, resource_id, reviewer_id, action, comment, reviewed_at
            )
            VALUES (
                :id, :resource_id, :reviewer_id, :action, :comment, NOW()
            )
            """
        ),
        {
            "id": review_id,
            "resource_id": resource_id,
            "reviewer_id": str(current_user.id),
            "action": action,
            "comment": comment,
        },
    )
    db.execute(
        text(
            """
            UPDATE learning_resources
            SET review_status = :review_status,
                updated_at = NOW()
            WHERE id = :resource_id
            """
        ),
        {"resource_id": resource_id, "review_status": action_map[action]},
    )
    db.commit()

    reviewed_at = db.execute(
        text("SELECT reviewed_at FROM resource_reviews WHERE id = :id"),
        {"id": review_id},
    ).mappings().first()["reviewed_at"]
    return {
        "resource_id": resource_id,
        "review_status": action_map[action],
        "reviewer": current_user.username,
        "reviewed_at": reviewed_at.isoformat() if reviewed_at else None,
    }


def create_resource_regeneration_task(
    db: Session,
    resource_id: str,
    reason: str,
    keep_references: bool = True,
) -> dict:
    row = db.execute(
        text(
            """
            SELECT id, student_id, course_id, type, difficulty, title, generated_by_task_id
            FROM learning_resources
            WHERE id = :resource_id
            LIMIT 1
            """
        ),
        {"resource_id": resource_id},
    ).mappings().first()
    if row is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="资源不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    knowledge_point = db.execute(
        text(
            """
            SELECT r.knowledge_point
            FROM resource_generation_tasks r
            WHERE r.id = :task_id
            LIMIT 1
            """
        ),
        {"task_id": row["generated_by_task_id"]},
    ).mappings().first()

    task_id = "task_regen_" + uuid.uuid4().hex[:12]
    db.execute(
        text(
            """
            INSERT INTO resource_generation_tasks (
                id, student_id, course_id, knowledge_point, goal,
                resource_types_json, difficulty, status, progress,
                current_step, result_resource_ids_json, error_message,
                created_at, updated_at
            )
            VALUES (
                :id, :student_id, :course_id, :knowledge_point, :goal,
                :resource_types_json, :difficulty, 'pending', 0,
                '重新生成任务已进入队列', NULL, NULL, NOW(), NOW()
            )
            """
        ),
        {
            "id": task_id,
            "student_id": row["student_id"],
            "course_id": row["course_id"],
            "knowledge_point": knowledge_point["knowledge_point"] if knowledge_point else row["title"],
            "goal": f"根据审核意见重新生成资源：{reason}",
            "resource_types_json": json.dumps([row["type"]], ensure_ascii=False),
            "difficulty": row["difficulty"],
        },
    )
    db.execute(
        text(
            """
            UPDATE learning_resources
            SET review_status = 'need_modify',
                updated_at = NOW()
            WHERE id = :resource_id
            """
        ),
        {"resource_id": resource_id},
    )
    db.commit()
    return {"task_id": task_id, "status": "pending"}

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


def delete_resource(
    db: Session,
    current_user: User,
    resource_id: str,
) -> dict:
    student_id = str(current_user.id)
    is_admin = current_user.role == "admin"

    resource_row = db.execute(
        text(
            """
            SELECT id
            FROM learning_resources
            WHERE id = :resource_id
              AND (:is_admin = 1 OR student_id = :student_id)
            LIMIT 1
            """
        ),
        {
            "resource_id": resource_id,
            "student_id": student_id,
            "is_admin": 1 if is_admin else 0,
        },
    ).mappings().first()
    if resource_row is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="学习资源不存在或无权限删除",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    _create_tmp_resources(
        db=db,
        where_sql="id = :resource_id",
        params={"resource_id": resource_id},
    )
    deleted_resources = _delete_tmp_resources(db)
    db.commit()
    return {
        "deleted_resources": deleted_resources,
        "deleted_generation_tasks": 0,
        "scope": "single",
    }


def clear_generated_resources(
    db: Session,
    current_user: User,
    course_id: str | None = None,
    all_students: bool = False,
) -> dict:
    student_id = str(current_user.id)
    is_admin = current_user.role == "admin"
    if all_students and not is_admin:
        raise AppException(
            code=ErrorCode.FORBIDDEN,
            message="只有管理员可以清空所有学生的生成资源",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    where = ["generated_by_task_id IS NOT NULL"]
    params = {}
    if not all_students:
        where.append("student_id = :student_id")
        params["student_id"] = student_id
    if course_id:
        where.append("course_id = :course_id")
        params["course_id"] = course_id

    _create_tmp_resources(db=db, where_sql=" AND ".join(where), params=params)
    db.execute(text("DROP TEMPORARY TABLE IF EXISTS tmp_resource_tasks_to_delete"))
    db.execute(
        text(
            """
            CREATE TEMPORARY TABLE tmp_resource_tasks_to_delete AS
            SELECT DISTINCT generated_by_task_id AS id
            FROM tmp_resources_to_delete
            WHERE generated_by_task_id IS NOT NULL
            """
        )
    )
    deleted_resources = _delete_tmp_resources(db)
    db.execute(
        text(
            """
            DELETE FROM agent_task_steps
            WHERE task_id IN (
                SELECT id
                FROM agent_tasks
                WHERE related_task_id IN (SELECT id FROM tmp_resource_tasks_to_delete)
            )
            """
        )
    )
    db.execute(
        text(
            """
            DELETE FROM agent_tasks
            WHERE related_task_id IN (SELECT id FROM tmp_resource_tasks_to_delete)
            """
        )
    )
    task_result = db.execute(
        text(
            """
            DELETE FROM resource_generation_tasks
            WHERE id IN (SELECT id FROM tmp_resource_tasks_to_delete)
            """
        )
    )
    db.execute(text("DROP TEMPORARY TABLE IF EXISTS tmp_resource_tasks_to_delete"))
    db.commit()

    return {
        "deleted_resources": deleted_resources,
        "deleted_generation_tasks": task_result.rowcount or 0,
        "scope": "generated",
    }


def _create_tmp_resources(db: Session, where_sql: str, params: dict) -> None:
    db.execute(text("DROP TEMPORARY TABLE IF EXISTS tmp_resources_to_delete"))
    db.execute(
        text(
            f"""
            CREATE TEMPORARY TABLE tmp_resources_to_delete AS
            SELECT id, generated_by_task_id
            FROM learning_resources
            WHERE {where_sql}
            """
        ),
        params,
    )


def _delete_tmp_resources(db: Session) -> int:
    db.execute(text("DROP TEMPORARY TABLE IF EXISTS tmp_exercise_sets_to_delete"))
    db.execute(text("DROP TEMPORARY TABLE IF EXISTS tmp_exercise_questions_to_delete"))
    db.execute(text("DROP TEMPORARY TABLE IF EXISTS tmp_exercise_submissions_to_delete"))
    db.execute(
        text(
            """
            CREATE TEMPORARY TABLE tmp_exercise_sets_to_delete AS
            SELECT id
            FROM exercise_sets
            WHERE resource_id IN (SELECT id FROM tmp_resources_to_delete)
            """
        )
    )
    db.execute(
        text(
            """
            CREATE TEMPORARY TABLE tmp_exercise_questions_to_delete AS
            SELECT id
            FROM exercise_questions
            WHERE exercise_set_id IN (SELECT id FROM tmp_exercise_sets_to_delete)
            """
        )
    )
    db.execute(
        text(
            """
            CREATE TEMPORARY TABLE tmp_exercise_submissions_to_delete AS
            SELECT id
            FROM exercise_submissions
            WHERE exercise_set_id IN (SELECT id FROM tmp_exercise_sets_to_delete)
            """
        )
    )

    db.execute(
        text(
            """
            DELETE FROM wrong_questions
            WHERE question_id IN (SELECT id FROM tmp_exercise_questions_to_delete)
            """
        )
    )
    db.execute(
        text(
            """
            DELETE FROM exercise_answers
            WHERE submission_id IN (SELECT id FROM tmp_exercise_submissions_to_delete)
               OR question_id IN (SELECT id FROM tmp_exercise_questions_to_delete)
            """
        )
    )
    db.execute(
        text(
            """
            DELETE FROM exercise_submissions
            WHERE id IN (SELECT id FROM tmp_exercise_submissions_to_delete)
            """
        )
    )
    db.execute(
        text(
            """
            DELETE FROM exercise_questions
            WHERE id IN (SELECT id FROM tmp_exercise_questions_to_delete)
            """
        )
    )
    db.execute(
        text(
            """
            DELETE FROM exercise_sets
            WHERE id IN (SELECT id FROM tmp_exercise_sets_to_delete)
            """
        )
    )
    db.execute(text("DELETE FROM resource_references WHERE resource_id IN (SELECT id FROM tmp_resources_to_delete)"))
    db.execute(text("DELETE FROM resource_feedback WHERE resource_id IN (SELECT id FROM tmp_resources_to_delete)"))
    db.execute(text("DELETE FROM resource_favorites WHERE resource_id IN (SELECT id FROM tmp_resources_to_delete)"))
    db.execute(text("DELETE FROM resource_reviews WHERE resource_id IN (SELECT id FROM tmp_resources_to_delete)"))
    db.execute(
        text(
            """
            UPDATE study_records
            SET resource_id = NULL
            WHERE resource_id IN (SELECT id FROM tmp_resources_to_delete)
            """
        )
    )
    result = db.execute(text("DELETE FROM learning_resources WHERE id IN (SELECT id FROM tmp_resources_to_delete)"))
    deleted_resources = result.rowcount or 0

    db.execute(text("DROP TEMPORARY TABLE IF EXISTS tmp_exercise_submissions_to_delete"))
    db.execute(text("DROP TEMPORARY TABLE IF EXISTS tmp_exercise_questions_to_delete"))
    db.execute(text("DROP TEMPORARY TABLE IF EXISTS tmp_exercise_sets_to_delete"))
    db.execute(text("DROP TEMPORARY TABLE IF EXISTS tmp_resources_to_delete"))
    return deleted_resources
