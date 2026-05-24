import uuid
from fastapi import status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.user import User
from app.utils.response import AppException, ErrorCode


def get_today_learning_path(db: Session, current_user: User) -> dict:
    """
    阶段 3.2：获取当前学生今日学习任务。

    思路：
    1. 根据当前学生 id 找 active 学习路径
    2. 查询该路径下的所有任务
    3. 找到第一个未完成任务，作为 current_task
    4. 计算任务完成进度
    """

    student_id = str(current_user.id)

    # 1. 查询当前学生正在进行的学习路径
    path_row = db.execute(
        text(
            """
            SELECT id, course_id, title, progress, status
            FROM learning_paths
            WHERE student_id = :student_id
              AND status = 'active'
            ORDER BY id DESC
            LIMIT 1
            """
        ),
        {"student_id": student_id},
    ).mappings().first()

    if path_row is None:
        return {
            "path_id": None,
            "path_title": None,
            "course_id": None,
            "today_progress": 0,
            "total_tasks": 0,
            "completed_tasks": 0,
            "current_task": None,
            "tasks": [],
        }

    path_id = path_row["id"]

    # 2. 查询该学习路径下的任务
    task_rows = db.execute(
        text(
            """
            SELECT id, day_no, topic, description, estimated_minutes, status, completed_at
            FROM learning_path_tasks
            WHERE path_id = :path_id
            ORDER BY day_no ASC
            """
        ),
        {"path_id": path_id},
    ).mappings().all()

    tasks = []
    completed_count = 0
    current_task = None

    for row in task_rows:
        item = {
            "task_id": row["id"],
            "day_no": row["day_no"],
            "topic": row["topic"],
            "description": row["description"],
            "estimated_minutes": row["estimated_minutes"],
            "status": row["status"],
            "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
        }

        tasks.append(item)

        if row["status"] == "completed":
            completed_count += 1

        # 第一个未完成任务，作为今日推荐任务
        if current_task is None and row["status"] != "completed":
            current_task = item

    total_tasks = len(tasks)
    today_progress = round(completed_count / total_tasks, 2) if total_tasks > 0 else 0

    return {
        "path_id": path_row["id"],
        "path_title": path_row["title"],
        "course_id": path_row["course_id"],
        "today_progress": today_progress,
        "total_tasks": total_tasks,
        "completed_tasks": completed_count,
        "current_task": current_task,
        "tasks": tasks,
    }

def complete_learning_task(
    db: Session,
    current_user: User,
    task_id: str,
) -> dict:
    """
    阶段：完成学习任务。

    功能：
    1. 校验任务是否属于当前学生
    2. 更新任务状态为 completed
    3. 写入 study_records 学习记录
    4. 重新计算 learning_paths.progress
    """

    student_id = str(current_user.id)

    # 1. 查询任务，并确保任务属于当前学生
    task_row = db.execute(
        text(
            """
            SELECT
                t.id AS task_id,
                t.path_id AS path_id,
                t.topic AS topic,
                t.estimated_minutes AS estimated_minutes,
                t.status AS task_status,
                t.completed_at AS completed_at,
                p.student_id AS student_id,
                p.course_id AS course_id
            FROM learning_path_tasks t
            JOIN learning_paths p ON p.id = t.path_id
            WHERE t.id = :task_id
              AND p.student_id = :student_id
            LIMIT 1
            """
        ),
        {
            "task_id": task_id,
            "student_id": student_id,
        },
    ).mappings().first()

    if task_row is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="学习任务不存在或无权限操作",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    path_id = task_row["path_id"]
    course_id = task_row["course_id"]
    estimated_minutes = task_row["estimated_minutes"] or 0

    # 2. 如果已经完成，就不要重复写学习记录
    if task_row["task_status"] == "completed":
        counts = _get_path_task_counts(db=db, path_id=path_id)

        return {
            "task_id": task_id,
            "path_id": path_id,
            "status": "completed",
            "completed_at": task_row["completed_at"].isoformat() if task_row["completed_at"] else None,
            "total_tasks": counts["total_tasks"],
            "completed_tasks": counts["completed_tasks"],
            "path_progress": counts["path_progress"],
            "study_minutes_added": 0,
        }

    # 3. 更新任务为 completed
    db.execute(
        text(
            """
            UPDATE learning_path_tasks
            SET status = 'completed',
                completed_at = NOW()
            WHERE id = :task_id
            """
        ),
        {
            "task_id": task_id,
        },
    )

    # 4. 写入学习记录
    study_record_id = "study_" + uuid.uuid4().hex[:12]

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
                NULL,
                :path_task_id,
                'complete_task',
                :study_minutes,
                0,
                NOW()
            )
            """
        ),
        {
            "id": study_record_id,
            "student_id": student_id,
            "course_id": course_id,
            "path_task_id": task_id,
            "study_minutes": estimated_minutes,
        },
    )

    # 5. 重新计算任务完成数量和路径进度
    counts = _get_path_task_counts(db=db, path_id=path_id)
    path_progress = counts["path_progress"]

    db.execute(
        text(
            """
            UPDATE learning_paths
            SET progress = :progress
            WHERE id = :path_id
            """
        ),
        {
            "progress": path_progress,
            "path_id": path_id,
        },
    )

    db.commit()

    # 6. 重新查 completed_at
    completed_row = db.execute(
        text(
            """
            SELECT completed_at
            FROM learning_path_tasks
            WHERE id = :task_id
            LIMIT 1
            """
        ),
        {
            "task_id": task_id,
        },
    ).mappings().first()

    return {
        "task_id": task_id,
        "path_id": path_id,
        "status": "completed",
        "completed_at": completed_row["completed_at"].isoformat() if completed_row and completed_row["completed_at"] else None,
        "total_tasks": counts["total_tasks"],
        "completed_tasks": counts["completed_tasks"],
        "path_progress": path_progress,
        "study_minutes_added": estimated_minutes,
    }


def _get_path_task_counts(db: Session, path_id: str) -> dict:
    """
    统计某条学习路径的任务数量和完成进度。
    """

    row = db.execute(
        text(
            """
            SELECT
                COUNT(*) AS total_tasks,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_tasks
            FROM learning_path_tasks
            WHERE path_id = :path_id
            """
        ),
        {
            "path_id": path_id,
        },
    ).mappings().first()

    total_tasks = int(row["total_tasks"] or 0)
    completed_tasks = int(row["completed_tasks"] or 0)

    path_progress = round(completed_tasks / total_tasks, 2) if total_tasks > 0 else 0

    return {
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "path_progress": path_progress,
    }