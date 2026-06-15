import json
import logging
from datetime import datetime

from fastapi import status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.user import User
from app.services.llm_service import DeepSeekService
from app.utils.response import AppException, ErrorCode

logger = logging.getLogger("app.services.evaluation")


def get_learning_report(db: Session, current_user: User, report_range: str, course_id: str | None) -> dict:
    if report_range not in {"week", "month", "all"}:
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message="range 仅支持 week / month / all",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    student_id = str(current_user.id)
    course_name = _get_course_name(db, course_id)
    completion_rate = _get_completion_rate(db, student_id, course_id)
    study_hours = _get_study_hours(db, student_id, course_id, report_range)
    mastery = _get_mastery_items(db, student_id, course_id)
    weak_points = _get_weak_point_items(db, student_id, course_id)
    weak_points = _enrich_weak_points_with_llm(db, student_id, weak_points)
    good_points = [
        {"knowledge_point": item["knowledge_point"], "score": item["score"]}
        for item in mastery
        if item["score"] >= 80
    ]
    learning_path = _get_learning_path_summary(db, student_id, course_id)
    exercise_summary = _get_exercise_summary(db, student_id, course_id, report_range)
    recent_submissions = _get_recent_submissions(db, student_id, course_id, report_range)
    daily_activity = _get_daily_activity(db, student_id, course_id, report_range)
    unfinished_tasks = _get_unfinished_tasks(db, student_id, course_id)
    mastery_distribution = _build_mastery_distribution(mastery)
    accuracy_rate = exercise_summary["average_accuracy"]
    recommendations = _build_recommendations(
        weak_points=weak_points,
        mastery=mastery,
        unfinished_tasks=unfinished_tasks,
        exercise_summary=exercise_summary,
    )

    return {
        "range": report_range,
        "course_id": course_id,
        "course_name": course_name,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "completion_rate": completion_rate,
        "accuracy_rate": accuracy_rate,
        "study_hours": study_hours,
        "overview": {
            "summary": _build_report_summary(completion_rate, accuracy_rate, study_hours, weak_points),
            "completion_percent": round(completion_rate * 100, 2),
            "accuracy_percent": round(accuracy_rate * 100, 2),
            "study_hours": study_hours,
            "mastered_count": len(good_points),
            "weak_point_count": len(weak_points),
            "submission_count": exercise_summary["submission_count"],
            "wrong_question_count": exercise_summary["wrong_question_count"],
        },
        "learning_path": learning_path,
        "exercise_summary": exercise_summary,
        "mastery_distribution": mastery_distribution,
        "recent_submissions": recent_submissions,
        "daily_activity": daily_activity,
        "unfinished_tasks": unfinished_tasks,
        "mastery": mastery,
        "good_points": good_points,
        "weak_points": weak_points,
        "recommendations": recommendations,
        "next_suggestion": recommendations[0] if recommendations else "保持当前学习节奏，继续完成学习路径任务。",
    }


def get_weak_points(db: Session, current_user: User, course_id: str | None = None) -> dict:
    student_id = str(current_user.id)
    items = _get_weak_point_items(db, student_id, course_id)
    items = _enrich_weak_points_with_llm(db, student_id, items)
    return {"items": items, "total": len(items)}


def get_mastery(db: Session, current_user: User, course_id: str | None = None) -> dict:
    student_id = str(current_user.id)
    course_name = _get_course_name(db, course_id)
    items = _get_mastery_items(db, student_id, course_id)
    return {"course": course_name, "course_id": course_id, "items": items}


def _get_course_name(db: Session, course_id: str | None) -> str | None:
    if not course_id:
        return None
    row = db.execute(
        text("SELECT name FROM courses WHERE course_id = :course_id LIMIT 1"),
        {"course_id": course_id},
    ).mappings().first()
    return row["name"] if row else None


def _get_completion_rate(db: Session, student_id: str, course_id: str | None) -> float:
    where = ["student_id = :student_id"]
    params = {"student_id": student_id}
    if course_id:
        where.append("course_id = :course_id")
        params["course_id"] = course_id
    row = db.execute(
        text(
            f"""
            SELECT AVG(progress) AS completion_rate
            FROM learning_paths
            WHERE {' AND '.join(where)}
            """
        ),
        params,
    ).mappings().first()
    return round(float(row["completion_rate"] or 0), 4)


def _get_study_hours(db: Session, student_id: str, course_id: str | None, report_range: str) -> float:
    where = ["student_id = :student_id"]
    params = {"student_id": student_id}
    if course_id:
        where.append("course_id = :course_id")
        params["course_id"] = course_id
    date_filter = _date_filter(report_range, "created_at")
    row = db.execute(
        text(
            f"""
            SELECT COALESCE(SUM(study_minutes), 0) AS study_minutes
            FROM study_records
            WHERE {' AND '.join(where)}
              {date_filter}
            """
        ),
        params,
    ).mappings().first()
    return round(float(row["study_minutes"] or 0) / 60, 2)


def _get_learning_path_summary(db: Session, student_id: str, course_id: str | None) -> dict:
    where = ["p.student_id = :student_id"]
    params = {"student_id": student_id}
    if course_id:
        where.append("p.course_id = :course_id")
        params["course_id"] = course_id
    path = db.execute(
        text(
            f"""
            SELECT
                p.id,
                p.title,
                p.course_id,
                p.goal,
                p.duration_days,
                p.daily_minutes,
                p.progress,
                p.status,
                p.created_at,
                p.updated_at,
                COUNT(t.id) AS total_tasks,
                SUM(CASE WHEN t.status = 'completed' THEN 1 ELSE 0 END) AS completed_tasks
            FROM learning_paths p
            LEFT JOIN learning_path_tasks t ON t.path_id = p.id
            WHERE {' AND '.join(where)}
            GROUP BY p.id, p.title, p.course_id, p.goal, p.duration_days,
                     p.daily_minutes, p.progress, p.status, p.created_at, p.updated_at
            ORDER BY p.updated_at DESC, p.created_at DESC
            LIMIT 1
            """
        ),
        params,
    ).mappings().first()
    if not path:
        return {
            "path_id": None,
            "title": None,
            "status": None,
            "progress": 0,
            "progress_percent": 0,
            "total_tasks": 0,
            "completed_tasks": 0,
            "remaining_tasks": 0,
        }

    total_tasks = int(path["total_tasks"] or 0)
    completed_tasks = int(path["completed_tasks"] or 0)
    progress = float(path["progress"] or 0)
    return {
        "path_id": path["id"],
        "title": path["title"],
        "course_id": path["course_id"],
        "goal": path["goal"],
        "duration_days": path["duration_days"],
        "daily_minutes": path["daily_minutes"],
        "status": path["status"],
        "progress": progress,
        "progress_percent": round(progress * 100, 2),
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "remaining_tasks": max(total_tasks - completed_tasks, 0),
        "created_at": path["created_at"].isoformat() if path["created_at"] else None,
        "updated_at": path["updated_at"].isoformat() if path["updated_at"] else None,
    }


def _get_exercise_summary(db: Session, student_id: str, course_id: str | None, report_range: str) -> dict:
    params = {"student_id": student_id}
    course_filter = ""
    if course_id:
        course_filter = "AND s.course_id = :course_id"
        params["course_id"] = course_id
    date_filter = _date_filter(report_range, "es.submitted_at")
    row = db.execute(
        text(
            f"""
            SELECT
                COUNT(*) AS submission_count,
                AVG(es.score) AS average_score,
                AVG(es.accuracy) AS average_accuracy,
                COALESCE(SUM(es.correct_count), 0) AS correct_count,
                COALESCE(SUM(es.total_count), 0) AS total_count,
                MAX(es.submitted_at) AS last_submitted_at
            FROM exercise_submissions es
            JOIN exercise_sets s ON s.id = es.exercise_set_id
            WHERE es.student_id = :student_id
              {course_filter}
              {date_filter}
            """
        ),
        params,
    ).mappings().first()

    wrong_params = {"student_id": student_id}
    wrong_course_filter = ""
    if course_id:
        wrong_course_filter = "AND s.course_id = :course_id"
        wrong_params["course_id"] = course_id
    wrong_row = db.execute(
        text(
            f"""
            SELECT COUNT(*) AS wrong_question_count
            FROM wrong_questions w
            JOIN exercise_questions q ON q.id = w.question_id
            JOIN exercise_sets s ON s.id = q.exercise_set_id
            WHERE w.student_id = :student_id
              AND w.mastered = 0
              {wrong_course_filter}
            """
        ),
        wrong_params,
    ).mappings().first()

    total_count = int(row["total_count"] or 0)
    correct_count = int(row["correct_count"] or 0)
    average_accuracy = round(float(row["average_accuracy"] or 0), 4)
    return {
        "submission_count": int(row["submission_count"] or 0),
        "average_score": round(float(row["average_score"] or 0), 2),
        "average_accuracy": average_accuracy,
        "average_accuracy_percent": round(average_accuracy * 100, 2),
        "correct_count": correct_count,
        "total_count": total_count,
        "wrong_count": max(total_count - correct_count, 0),
        "wrong_question_count": int(wrong_row["wrong_question_count"] or 0),
        "last_submitted_at": row["last_submitted_at"].isoformat() if row["last_submitted_at"] else None,
    }


def _get_recent_submissions(db: Session, student_id: str, course_id: str | None, report_range: str) -> list[dict]:
    params = {"student_id": student_id}
    course_filter = ""
    if course_id:
        course_filter = "AND s.course_id = :course_id"
        params["course_id"] = course_id
    date_filter = _date_filter(report_range, "es.submitted_at")
    rows = db.execute(
        text(
            f"""
            SELECT
                es.id,
                es.resource_id,
                s.title,
                s.course_id,
                es.score,
                es.accuracy,
                es.correct_count,
                es.total_count,
                es.duration_seconds,
                es.submitted_at
            FROM exercise_submissions es
            JOIN exercise_sets s ON s.id = es.exercise_set_id
            WHERE es.student_id = :student_id
              {course_filter}
              {date_filter}
            ORDER BY es.submitted_at DESC
            LIMIT 5
            """
        ),
        params,
    ).mappings().all()
    return [
        {
            "submission_id": row["id"],
            "resource_id": row["resource_id"],
            "title": row["title"],
            "course_id": row["course_id"],
            "score": float(row["score"] or 0),
            "accuracy": float(row["accuracy"] or 0),
            "correct_count": int(row["correct_count"] or 0),
            "total_count": int(row["total_count"] or 0),
            "duration_seconds": row["duration_seconds"],
            "submitted_at": row["submitted_at"].isoformat() if row["submitted_at"] else None,
        }
        for row in rows
    ]


def _get_daily_activity(db: Session, student_id: str, course_id: str | None, report_range: str) -> list[dict]:
    params = {"student_id": student_id}
    course_filter = ""
    if course_id:
        course_filter = "AND course_id = :course_id"
        params["course_id"] = course_id
    date_filter = _date_filter(report_range, "created_at")
    rows = db.execute(
        text(
            f"""
            SELECT
                DATE(created_at) AS stat_date,
                COALESCE(SUM(study_minutes), 0) AS study_minutes,
                COUNT(*) AS action_count
            FROM study_records
            WHERE student_id = :student_id
              {course_filter}
              {date_filter}
            GROUP BY DATE(created_at)
            ORDER BY stat_date ASC
            """
        ),
        params,
    ).mappings().all()
    return [
        {
            "date": row["stat_date"].isoformat() if row["stat_date"] else None,
            "study_minutes": int(row["study_minutes"] or 0),
            "study_hours": round(float(row["study_minutes"] or 0) / 60, 2),
            "action_count": int(row["action_count"] or 0),
        }
        for row in rows
    ]


def _get_unfinished_tasks(db: Session, student_id: str, course_id: str | None) -> list[dict]:
    params = {"student_id": student_id}
    course_filter = ""
    if course_id:
        course_filter = "AND p.course_id = :course_id"
        params["course_id"] = course_id
    rows = db.execute(
        text(
            f"""
            SELECT
                t.id,
                t.path_id,
                t.day_no,
                t.topic,
                t.description,
                t.estimated_minutes,
                t.status
            FROM learning_path_tasks t
            JOIN learning_paths p ON p.id = t.path_id
            WHERE p.student_id = :student_id
              AND p.status = 'active'
              AND t.status <> 'completed'
              {course_filter}
            ORDER BY t.day_no ASC, t.created_at ASC
            LIMIT 5
            """
        ),
        params,
    ).mappings().all()
    return [
        {
            "task_id": row["id"],
            "path_id": row["path_id"],
            "day_no": row["day_no"],
            "topic": row["topic"],
            "description": row["description"],
            "estimated_minutes": row["estimated_minutes"],
            "status": row["status"],
        }
        for row in rows
    ]


def _get_mastery_items(db: Session, student_id: str, course_id: str | None) -> list[dict]:
    where = ["student_id = :student_id"]
    params = {"student_id": student_id}
    if course_id:
        where.append("course_id = :course_id")
        params["course_id"] = course_id
    rows = db.execute(
        text(
            f"""
            SELECT knowledge_point, score
            FROM mastery_records
            WHERE {' AND '.join(where)}
            ORDER BY score ASC, updated_at DESC
            """
        ),
        params,
    ).mappings().all()
    return [{"knowledge_point": row["knowledge_point"], "score": float(row["score"] or 0)} for row in rows]


def _get_weak_point_items(db: Session, student_id: str, course_id: str | None) -> list[dict]:
    where = ["student_id = :student_id"]
    params = {"student_id": student_id}
    if course_id:
        where.append("course_id = :course_id")
        params["course_id"] = course_id
    rows = db.execute(
        text(
            f"""
            SELECT id, course_id, knowledge_point, mastery_score, wrong_count,
                   reason, suggested_action, source, updated_at
            FROM weak_point_records
            WHERE {' AND '.join(where)}
            ORDER BY COALESCE(mastery_score, 0) ASC, wrong_count DESC, updated_at DESC
            """
        ),
        params,
    ).mappings().all()
    return [
        {
            "course_id": row["course_id"],
            "weak_point_id": row["id"],
            "knowledge_point": row["knowledge_point"],
            "mastery_score": float(row["mastery_score"]) if row["mastery_score"] is not None else None,
            "wrong_count": int(row["wrong_count"] or 0),
            "reason": row["reason"],
            "suggested_action": row["suggested_action"],
            "source": row["source"],
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        }
        for row in rows
    ]


GENERIC_WEAK_REASONS = {
    "练习正确率低于 60%",
    "练习正确率低于60%",
    "本次练习答错次数较多",
}

GENERIC_WEAK_ACTIONS = {
    "复习概念说明并重做错题",
    "回看相关资源并完成同类题巩固",
}


def _enrich_weak_points_with_llm(db: Session, student_id: str, items: list[dict]) -> list[dict]:
    candidates = [
        item
        for item in items
        if item.get("weak_point_id")
        and (
            item.get("reason") in GENERIC_WEAK_REASONS
            or item.get("suggested_action") in GENERIC_WEAK_ACTIONS
            or not item.get("reason")
            or not item.get("suggested_action")
        )
    ]
    if not candidates:
        return items

    try:
        llm_service = DeepSeekService()
    except Exception as exc:
        logger.warning("skip weak point LLM enrichment | reason=%s", exc)
        return items

    changed = False
    for item in candidates[:5]:
        try:
            context = _get_weak_point_context(
                db=db,
                student_id=student_id,
                course_id=item.get("course_id"),
                knowledge_point=item.get("knowledge_point"),
            )
            analysis = _generate_weak_point_analysis(llm_service, item, context)
            reason = _clean_text(analysis.get("reason"), max_length=180)
            suggested_action = _clean_text(analysis.get("suggested_action"), max_length=220)
            if not reason or not suggested_action:
                continue

            db.execute(
                text(
                    """
                    UPDATE weak_point_records
                    SET reason = :reason,
                        suggested_action = :suggested_action,
                        source = 'evaluation_agent',
                        updated_at = NOW()
                    WHERE id = :id
                    """
                ),
                {
                    "id": item["weak_point_id"],
                    "reason": reason,
                    "suggested_action": suggested_action,
                },
            )
            item["reason"] = reason
            item["suggested_action"] = suggested_action
            item["source"] = "evaluation_agent"
            changed = True
        except Exception:
            logger.exception(
                "failed to enrich weak point | student_id=%s | knowledge_point=%s",
                student_id,
                item.get("knowledge_point"),
            )

    if changed:
        db.commit()
    return items


def _get_weak_point_context(
    db: Session,
    student_id: str,
    course_id: str | None,
    knowledge_point: str | None,
) -> dict:
    rows = db.execute(
        text(
            """
            SELECT
                q.question,
                q.type,
                q.correct_answer_json,
                q.explanation,
                q.related_knowledge,
                w.wrong_count,
                w.last_wrong_at
            FROM wrong_questions w
            JOIN exercise_questions q ON q.id = w.question_id
            JOIN exercise_sets s ON s.id = q.exercise_set_id
            WHERE w.student_id = :student_id
              AND (:course_id IS NULL OR s.course_id = :course_id)
              AND (
                    w.knowledge_point = :knowledge_point
                 OR q.related_knowledge = :knowledge_point
              )
            ORDER BY w.last_wrong_at DESC
            LIMIT 5
            """
        ),
        {
            "student_id": student_id,
            "course_id": course_id,
            "knowledge_point": knowledge_point,
        },
    ).mappings().all()
    return {
        "wrong_questions": [
            {
                "question": row["question"],
                "type": row["type"],
                "correct_answer": _json_value(row["correct_answer_json"]),
                "explanation": row["explanation"],
                "related_knowledge": row["related_knowledge"],
                "wrong_count": row["wrong_count"],
                "last_wrong_at": row["last_wrong_at"].isoformat() if row["last_wrong_at"] else None,
            }
            for row in rows
        ]
    }


def _generate_weak_point_analysis(
    llm_service: DeepSeekService,
    item: dict,
    context: dict,
) -> dict:
    system_prompt = (
        "你是 EduForge AI 的 Evaluation Agent。"
        "请根据学生错题、掌握度和知识点，输出具体、可执行的薄弱点分析。"
        "严格输出 JSON，不要输出 Markdown。"
    )
    user_prompt = f"""
请分析学生薄弱点，并输出 JSON：
{{
  "reason": "一句话说明薄弱原因，必须具体到概念、方法或题型",
  "suggested_action": "一句话给出可执行学习建议，包含复习动作和练习动作"
}}

薄弱点数据：
{json.dumps({
    "knowledge_point": item.get("knowledge_point"),
    "course_id": item.get("course_id"),
    "mastery_score": item.get("mastery_score"),
    "wrong_count": item.get("wrong_count"),
    "current_reason": item.get("reason"),
    "current_suggested_action": item.get("suggested_action"),
    "wrong_question_context": context,
}, ensure_ascii=False, indent=2)}

要求：
1. 不要写“练习正确率低于 60%”这类泛泛原因。
2. 如果 knowledge_point 像一句话或题目解析，请概括成真实薄弱能力点。
3. reason 控制在 80 字以内。
4. suggested_action 控制在 100 字以内。
"""
    return llm_service.generate_json_sync(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=800,
        temperature=0.2,
    )


def _json_value(value):
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _clean_text(value, max_length: int) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    if not text_value:
        return None
    return text_value[:max_length]


def _build_mastery_distribution(mastery: list[dict]) -> dict:
    distribution = {
        "excellent": 0,
        "good": 0,
        "basic": 0,
        "weak": 0,
        "unknown": 0,
    }
    for item in mastery:
        score = item.get("score")
        if score is None:
            distribution["unknown"] += 1
        elif score >= 90:
            distribution["excellent"] += 1
        elif score >= 75:
            distribution["good"] += 1
        elif score >= 60:
            distribution["basic"] += 1
        else:
            distribution["weak"] += 1
    distribution["total"] = len(mastery)
    return distribution


def _build_report_summary(
    completion_rate: float,
    accuracy_rate: float,
    study_hours: float,
    weak_points: list[dict],
) -> str:
    if completion_rate == 0 and accuracy_rate == 0 and study_hours == 0:
        return "本周期暂无足够学习数据，建议先完成学习路径任务并提交练习。"
    if weak_points:
        return f"本周期已有学习记录，当前最需要优先巩固的是 {weak_points[0]['knowledge_point']}。"
    if completion_rate >= 0.8 and accuracy_rate >= 0.8:
        return "本周期学习完成度和练习正确率表现较好，可以逐步提高练习难度。"
    return "本周期已有学习进展，建议继续按学习路径推进并保持练习反馈。"


def _build_recommendations(
    weak_points: list[dict],
    mastery: list[dict],
    unfinished_tasks: list[dict],
    exercise_summary: dict,
) -> list[str]:
    recommendations = []
    for item in weak_points[:3]:
        action = item.get("suggested_action") or "回看相关资源并完成同类题巩固"
        recommendations.append(f"优先复习 {item['knowledge_point']}，{action}。")
    if unfinished_tasks:
        task = unfinished_tasks[0]
        recommendations.append(f"下一步完成学习路径任务：第 {task['day_no']} 天 - {task['topic']}。")
    if exercise_summary.get("submission_count", 0) == 0:
        recommendations.append("本周期还没有练习提交，建议完成至少一次练习以更新掌握度。")
    elif exercise_summary.get("average_accuracy", 0) < 0.6:
        recommendations.append("练习正确率偏低，建议先复习错题解析，再提交一次同类练习。")
    if not recommendations and mastery:
        recommendations.append("掌握度整体稳定，可以进入下一组知识点或提高难度。")
    return recommendations


def _date_filter(report_range: str, column_name: str) -> str:
    if report_range == "week":
        return f"AND {column_name} >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
    if report_range == "month":
        return f"AND {column_name} >= DATE_SUB(NOW(), INTERVAL 1 MONTH)"
    return ""
