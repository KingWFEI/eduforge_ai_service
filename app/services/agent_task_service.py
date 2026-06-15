import json
import uuid

from fastapi import status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.utils.response import AppException, ErrorCode


def list_agent_tasks(
    db: Session,
    task_type: str | None = None,
    task_status: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> dict:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    where = ["1 = 1"]
    params = {"limit": page_size, "offset": (page - 1) * page_size}
    if task_type:
        where.append("a.task_type = :task_type")
        params["task_type"] = task_type
    if task_status:
        where.append("a.status = :task_status")
        params["task_status"] = task_status
    where_sql = " AND ".join(where)

    total = db.execute(
        text(f"SELECT COUNT(*) AS total FROM agent_tasks a WHERE {where_sql}"),
        params,
    ).mappings().first()["total"]
    rows = db.execute(
        text(
            f"""
            SELECT
                a.id,
                a.task_type,
                a.status,
                a.progress,
                u.name AS student_name,
                c.name AS course,
                r.knowledge_point,
                a.created_at,
                a.updated_at
            FROM agent_tasks a
            LEFT JOIN users u
              ON CAST(u.id AS CHAR) COLLATE utf8mb4_unicode_ci
               = a.student_id COLLATE utf8mb4_unicode_ci
            LEFT JOIN courses c
              ON c.course_id COLLATE utf8mb4_unicode_ci
               = a.course_id COLLATE utf8mb4_unicode_ci
            LEFT JOIN resource_generation_tasks r
              ON r.id COLLATE utf8mb4_unicode_ci
               = a.related_task_id COLLATE utf8mb4_unicode_ci
            WHERE {where_sql}
            ORDER BY a.created_at DESC, a.id DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()
    return {
        "items": [
            {
                "task_id": row["id"],
                "task_type": row["task_type"],
                "status": row["status"],
                "progress": row["progress"] or 0,
                "student_name": row["student_name"],
                "course": row["course"],
                "knowledge_point": row["knowledge_point"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            }
            for row in rows
        ],
        "total": int(total or 0),
        "page": page,
        "page_size": page_size,
    }


def get_agent_task_detail(db: Session, task_id: str) -> dict:
    task = db.execute(
        text(
            """
            SELECT id, task_type, status, progress, input_json, output_json, error_message
            FROM agent_tasks
            WHERE id = :task_id
            LIMIT 1
            """
        ),
        {"task_id": task_id},
    ).mappings().first()
    if task is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="智能体任务不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    step_rows = db.execute(
        text(
            """
            SELECT agent_name, status, input_summary, output_summary,
                   duration_ms, error_message
            FROM agent_task_steps
            WHERE task_id = :task_id
            ORDER BY step_order ASC
            """
        ),
        {"task_id": task_id},
    ).mappings().all()
    return {
        "task_id": task["id"],
        "task_type": task["task_type"],
        "status": task["status"],
        "progress": task["progress"] or 0,
        "input": _json_value(task["input_json"], {}),
        "agent_steps": [
            {
                "agent": row["agent_name"],
                "status": row["status"],
                "input_summary": row["input_summary"],
                "output_summary": row["output_summary"],
                "duration_ms": row["duration_ms"],
                "error_message": row["error_message"],
            }
            for row in step_rows
        ],
        "output": _json_value(task["output_json"], {}),
        "error_message": task["error_message"],
    }


def retry_agent_task(db: Session, task_id: str, retry_from_step: str | None = None) -> dict:
    task = db.execute(
        text(
            """
            SELECT id, task_type, related_task_id, input_json, status
            FROM agent_tasks
            WHERE id = :task_id
            LIMIT 1
            """
        ),
        {"task_id": task_id},
    ).mappings().first()
    if task is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="智能体任务不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if task["task_type"] != "resource_generate":
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message="当前仅支持重试资源生成类智能体任务",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    source_resource_task = db.execute(
        text(
            """
            SELECT student_id, course_id, knowledge_point, goal,
                   resource_types_json, difficulty
            FROM resource_generation_tasks
            WHERE id = :related_task_id
            LIMIT 1
            """
        ),
        {"related_task_id": task["related_task_id"]},
    ).mappings().first()
    if source_resource_task is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="原资源生成任务不存在，无法重试",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    new_task_id = "task_retry_" + uuid.uuid4().hex[:12]
    goal = source_resource_task["goal"] or ""
    if retry_from_step:
        goal = f"{goal}\n重试起点建议：{retry_from_step}".strip()
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
                '重试任务已进入队列', NULL, NULL, NOW(), NOW()
            )
            """
        ),
        {
            "id": new_task_id,
            "student_id": source_resource_task["student_id"],
            "course_id": source_resource_task["course_id"],
            "knowledge_point": source_resource_task["knowledge_point"],
            "goal": goal,
            "resource_types_json": json.dumps(
                _json_value(source_resource_task["resource_types_json"], []),
                ensure_ascii=False,
            ),
            "difficulty": source_resource_task["difficulty"],
        },
    )
    db.commit()
    return {"new_task_id": new_task_id, "status": "pending"}


def _json_value(value, default):
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value
