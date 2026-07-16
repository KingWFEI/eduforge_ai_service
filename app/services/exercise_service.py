import json
import uuid
from typing import Any

from fastapi import status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.user import User
from app.utils.response import AppException, ErrorCode


ALLOWED_EXERCISE_TYPES = {"choice", "multi_choice", "fill_blank", "true_false"}


def get_exercises_by_resource(db: Session, current_user: User, resource_id: str) -> dict:
    student_id = str(current_user.id)
    exercise_set = _get_or_create_exercise_set(db, student_id, resource_id)
    questions = _list_questions(db, exercise_set["id"], include_answer=False)
    return {
        "resource_id": resource_id,
        "exercise_set_id": exercise_set["id"],
        "title": exercise_set["title"],
        "course_id": exercise_set["course_id"],
        "difficulty": exercise_set["difficulty"],
        "questions": questions,
        "total": len(questions),
    }


def submit_exercise(db: Session, current_user: User, payload: Any) -> dict:
    student_id = str(current_user.id)
    exercise_set = _resolve_exercise_set(db, student_id, payload.exercise_set_id, payload.resource_id)
    questions = _list_questions(db, exercise_set["id"], include_answer=True)
    question_map = {item["question_id"]: item for item in questions}

    answer_map = {item.question_id: item.answer for item in payload.answers}
    results = []
    correct_count = 0
    weak_counter: dict[str, int] = {}

    submission_id = "sub_" + uuid.uuid4().hex[:12]
    for question_id, student_answer in answer_map.items():
        question = question_map.get(question_id)
        if question is None:
            raise AppException(
                code=ErrorCode.NOT_FOUND,
                message=f"题目不存在: {question_id}",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        is_correct = _answers_equal(student_answer, question["correct_answer"])
        if is_correct:
            correct_count += 1
        else:
            kp = question["related_knowledge"] or "未标注知识点"
            weak_counter[kp] = weak_counter.get(kp, 0) + 1
        results.append(
            {
                "question_id": question_id,
                "is_correct": is_correct,
                "correct_answer": question["correct_answer"],
                "student_answer": student_answer,
                "explanation": question["explanation"],
                "related_knowledge": question["related_knowledge"],
            }
        )

    total_count = len(answer_map)
    accuracy = round(correct_count / total_count, 4) if total_count else 0
    score = round(accuracy * 100, 2)
    weak_points = [
        {
            "knowledge_point": kp,
            "wrong_count": count,
            "reason": "本次练习答错次数较多",
            "suggested_action": "回看相关资源并完成同类题巩固",
        }
        for kp, count in sorted(weak_counter.items(), key=lambda item: item[1], reverse=True)
    ]
    analysis = {
        "summary": "练习提交已完成自动判分",
        "level": "good" if score >= 80 else "needs_practice" if score < 60 else "normal",
    }

    db.execute(
        text(
            """
            INSERT INTO exercise_submissions (
                id, exercise_set_id, resource_id, student_id, score, accuracy,
                correct_count, total_count, duration_seconds, weak_points_json,
                analysis_json, submitted_at
            )
            VALUES (
                :id, :exercise_set_id, :resource_id, :student_id, :score, :accuracy,
                :correct_count, :total_count, :duration_seconds, :weak_points_json,
                :analysis_json, NOW()
            )
            """
        ),
        {
            "id": submission_id,
            "exercise_set_id": exercise_set["id"],
            "resource_id": exercise_set["resource_id"],
            "student_id": student_id,
            "score": score,
            "accuracy": accuracy,
            "correct_count": correct_count,
            "total_count": total_count,
            "duration_seconds": payload.duration_seconds,
            "weak_points_json": json.dumps(weak_points, ensure_ascii=False),
            "analysis_json": json.dumps(analysis, ensure_ascii=False),
        },
    )

    for result in results:
        db.execute(
            text(
                """
                INSERT INTO exercise_answers (
                    id, submission_id, question_id, student_answer_json,
                    is_correct, explanation, created_at
                )
                VALUES (
                    :id, :submission_id, :question_id, :student_answer_json,
                    :is_correct, :explanation, NOW()
                )
                """
            ),
            {
                "id": "ans_" + uuid.uuid4().hex[:12],
                "submission_id": submission_id,
                "question_id": result["question_id"],
                "student_answer_json": json.dumps(result["student_answer"], ensure_ascii=False),
                "is_correct": 1 if result["is_correct"] else 0,
                "explanation": result["explanation"],
            },
        )
        if not result["is_correct"]:
            _upsert_wrong_question(db, student_id, result)

    _update_mastery_and_weak_points(
        db=db,
        student_id=student_id,
        course_id=exercise_set["course_id"],
        questions=questions,
        results=results,
    )
    db.commit()

    return {
        "submission_id": submission_id,
        "resource_id": exercise_set["resource_id"],
        "exercise_set_id": exercise_set["id"],
        "score": score,
        "accuracy": accuracy,
        "correct_count": correct_count,
        "total_count": total_count,
        "weak_points": weak_points,
        "analysis": analysis,
        "results": results,
    }


def list_wrong_questions(
    db: Session,
    current_user: User,
    course_id: str | None,
    knowledge_point: str | None,
    page: int,
    page_size: int,
) -> dict:
    student_id = str(current_user.id)
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    where = ["w.student_id = :student_id"]
    params = {"student_id": student_id, "limit": page_size, "offset": (page - 1) * page_size}
    if course_id:
        where.append("s.course_id = :course_id")
        params["course_id"] = course_id
    if knowledge_point:
        where.append("w.knowledge_point = :knowledge_point")
        params["knowledge_point"] = knowledge_point
    where_sql = " AND ".join(where)

    total = db.execute(
        text(
            f"""
            SELECT COUNT(*) AS total
            FROM wrong_questions w
            JOIN exercise_questions q ON q.id = w.question_id
            JOIN exercise_sets s ON s.id = q.exercise_set_id
            WHERE {where_sql}
            """
        ),
        params,
    ).mappings().first()["total"]
    rows = db.execute(
        text(
            f"""
            SELECT
                w.id AS wrong_id, w.question_id, s.course_id, w.knowledge_point,
                q.question, q.options_json, q.correct_answer_json, q.explanation,
                w.wrong_count, w.last_wrong_at, w.mastered
            FROM wrong_questions w
            JOIN exercise_questions q ON q.id = w.question_id
            JOIN exercise_sets s ON s.id = q.exercise_set_id
            WHERE {where_sql}
            ORDER BY w.last_wrong_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()
    return {
        "items": [
            {
                "wrong_id": row["wrong_id"],
                "question_id": row["question_id"],
                "course_id": row["course_id"],
                "knowledge_point": row["knowledge_point"],
                "question": row["question"],
                "options": _json_value(row["options_json"], None),
                "correct_answer": _json_value(row["correct_answer_json"], None),
                "explanation": row["explanation"],
                "wrong_count": row["wrong_count"] or 0,
                "last_wrong_at": row["last_wrong_at"].isoformat() if row["last_wrong_at"] else None,
                "mastered": bool(row["mastered"]),
            }
            for row in rows
        ],
        "total": int(total or 0),
        "page": page,
        "page_size": page_size,
    }


def _get_or_create_exercise_set(db: Session, student_id: str, resource_id: str) -> dict:
    existing = db.execute(
        text(
            """
            SELECT s.id, s.resource_id, s.course_id, s.title, s.difficulty
            FROM exercise_sets s
            JOIN learning_resources r ON r.id = s.resource_id
            WHERE s.resource_id = :resource_id
              AND r.student_id = :student_id
            LIMIT 1
            """
        ),
        {"resource_id": resource_id, "student_id": student_id},
    ).mappings().first()
    if existing:
        return dict(existing)

    resource = db.execute(
        text(
            """
            SELECT id, course_id, knowledge_point_id, title, difficulty, content_json
            FROM learning_resources
            WHERE id = :resource_id
              AND student_id = :student_id
              AND type = 'exercise'
              AND review_status IN ('approved', 'auto_passed')
            LIMIT 1
            """
        ),
        {"resource_id": resource_id, "student_id": student_id},
    ).mappings().first()
    if resource is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="练习资源不存在或无权限访问",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    content = _json_value(resource["content_json"], {})
    questions = None
    if isinstance(content, dict):
        questions = content.get("exercises") or content.get("questions")
    if not questions:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="练习资源未包含题目",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    set_id = "exset_" + uuid.uuid4().hex[:12]
    db.execute(
        text(
            """
            INSERT INTO exercise_sets (
                id, resource_id, course_id, knowledge_point_id, title, difficulty, created_at
            )
            VALUES (
                :id, :resource_id, :course_id, :knowledge_point_id, :title, :difficulty, NOW()
            )
            """
        ),
        {
            "id": set_id,
            "resource_id": resource_id,
            "course_id": resource["course_id"],
            "knowledge_point_id": resource["knowledge_point_id"],
            "title": resource["title"],
            "difficulty": resource["difficulty"],
        },
    )
    for index, item in enumerate(questions):
        question_type = _normalize_question_type(item.get("type"))
        question_id = "exq_" + uuid.uuid4().hex[:12]
        db.execute(
            text(
                """
                INSERT INTO exercise_questions (
                    id, exercise_set_id, type, question, options_json,
                    correct_answer_json, explanation, related_knowledge,
                    sort_order, created_at
                )
                VALUES (
                    :id, :exercise_set_id, :type, :question, :options_json,
                    :correct_answer_json, :explanation, :related_knowledge,
                    :sort_order, NOW()
                )
                """
            ),
            {
                "id": question_id,
                "exercise_set_id": set_id,
                "type": question_type,
                "question": _normalize_question_text(item.get("question"), question_type),
                "options_json": json.dumps(_question_payload(item, question_type), ensure_ascii=False),
                "correct_answer_json": json.dumps(_correct_answer_payload(item, question_type), ensure_ascii=False),
                "explanation": item.get("explanation") or item.get("analysis"),
                "related_knowledge": item.get("knowledge_point") or item.get("related_knowledge"),
                "sort_order": index + 1,
            },
        )
    db.commit()
    return {
        "id": set_id,
        "resource_id": resource_id,
        "course_id": resource["course_id"],
        "title": resource["title"],
        "difficulty": resource["difficulty"],
    }


def _resolve_exercise_set(db: Session, student_id: str, exercise_set_id: str | None, resource_id: str | None) -> dict:
    if exercise_set_id:
        row = db.execute(
            text(
                """
                SELECT s.id, s.resource_id, s.course_id, s.title, s.difficulty
                FROM exercise_sets s
                LEFT JOIN learning_resources r ON r.id = s.resource_id
                WHERE s.id = :exercise_set_id
                  AND (r.student_id = :student_id OR r.student_id IS NULL OR s.resource_id IS NULL)
                LIMIT 1
                """
            ),
            {"exercise_set_id": exercise_set_id, "student_id": student_id},
        ).mappings().first()
        if row:
            return dict(row)
    if resource_id:
        return _get_or_create_exercise_set(db, student_id, resource_id)
    raise AppException(
        code=ErrorCode.PARAM_ERROR,
        message="resource_id 和 exercise_set_id 至少传一个",
        status_code=status.HTTP_400_BAD_REQUEST,
    )


def _list_questions(db: Session, exercise_set_id: str, include_answer: bool) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT
                s.course_id,
                s.title AS exercise_title,
                kp.name AS set_knowledge_point,
                q.id,
                q.type,
                q.question,
                q.options_json,
                q.correct_answer_json,
                q.explanation,
                q.related_knowledge,
                q.sort_order
            FROM exercise_questions q
            JOIN exercise_sets s ON s.id = q.exercise_set_id
            LEFT JOIN knowledge_points kp ON kp.id = s.knowledge_point_id
            WHERE q.exercise_set_id = :exercise_set_id
            ORDER BY q.sort_order ASC, q.created_at ASC
            """
        ),
        {"exercise_set_id": exercise_set_id},
    ).mappings().all()
    items = []
    for row in rows:
        related_knowledge = _normalize_knowledge_point(
            db=db,
            course_id=row["course_id"],
            raw_value=row["related_knowledge"],
            fallback=row["set_knowledge_point"] or _knowledge_point_from_title(row["exercise_title"]),
        )
        question_type = _normalize_question_type(row["type"])
        options_payload = _json_value(row["options_json"], None)
        item = {
            "question_id": row["id"],
            "type": question_type,
            "question": _normalize_question_text(row["question"], question_type),
            "options": options_payload if question_type in {"choice", "multi_choice"} else None,
            "blanks": options_payload if question_type == "fill_blank" else None,
            "related_knowledge": related_knowledge,
            "sort_order": row["sort_order"] or 0,
        }
        if include_answer:
            item["correct_answer"] = _json_value(row["correct_answer_json"], None)
            item["explanation"] = row["explanation"]
        items.append(item)
    return items


def _upsert_wrong_question(db: Session, student_id: str, result: dict) -> None:
    existing = db.execute(
        text(
            """
            SELECT id
            FROM wrong_questions
            WHERE student_id = :student_id
              AND question_id = :question_id
            LIMIT 1
            """
        ),
        {"student_id": student_id, "question_id": result["question_id"]},
    ).mappings().first()
    if existing:
        db.execute(
            text(
                """
                UPDATE wrong_questions
                SET wrong_count = wrong_count + 1,
                    last_wrong_at = NOW(),
                    mastered = 0,
                    knowledge_point = :knowledge_point
                WHERE id = :id
                """
            ),
            {"id": existing["id"], "knowledge_point": result["related_knowledge"]},
        )
    else:
        db.execute(
            text(
                """
                INSERT INTO wrong_questions (
                    id, student_id, question_id, knowledge_point,
                    wrong_count, last_wrong_at, mastered, created_at
                )
                VALUES (
                    :id, :student_id, :question_id, :knowledge_point,
                    1, NOW(), 0, NOW()
                )
                """
            ),
            {
                "id": "wrong_" + uuid.uuid4().hex[:12],
                "student_id": student_id,
                "question_id": result["question_id"],
                "knowledge_point": result["related_knowledge"],
            },
        )


def _update_mastery_and_weak_points(
    db: Session,
    student_id: str,
    course_id: str,
    questions: list[dict],
    results: list[dict],
) -> None:
    kp_stats: dict[str, dict[str, int]] = {}
    for result in results:
        kp = _normalize_knowledge_point(
            db=db,
            course_id=course_id,
            raw_value=result.get("related_knowledge"),
            fallback=None,
        )
        item = kp_stats.setdefault(kp, {"total": 0, "correct": 0})
        item["total"] += 1
        item["correct"] += 1 if result["is_correct"] else 0

    for kp, stat in kp_stats.items():
        score = round((stat["correct"] / stat["total"]) * 100, 2) if stat["total"] else 0
        existing = db.execute(
            text(
                """
                SELECT id
                FROM mastery_records
                WHERE student_id = :student_id
                  AND course_id = :course_id
                  AND knowledge_point = :knowledge_point
                LIMIT 1
                """
            ),
            {"student_id": student_id, "course_id": course_id, "knowledge_point": kp},
        ).mappings().first()
        if existing:
            db.execute(
                text(
                    """
                    UPDATE mastery_records
                    SET score = :score,
                        source = 'exercise',
                        updated_at = NOW()
                    WHERE id = :id
                    """
                ),
                {"id": existing["id"], "score": score},
            )
        else:
            db.execute(
                text(
                    """
                    INSERT INTO mastery_records (
                        id, student_id, course_id, knowledge_point,
                        score, source, updated_at
                    )
                    VALUES (
                        :id, :student_id, :course_id, :knowledge_point,
                        :score, 'exercise', NOW()
                    )
                    """
                ),
                {
                    "id": "mastery_" + uuid.uuid4().hex[:12],
                    "student_id": student_id,
                    "course_id": course_id,
                    "knowledge_point": kp,
                    "score": score,
                },
            )
        if score < 60:
            _upsert_weak_point(db, student_id, course_id, kp, score, stat["total"] - stat["correct"])


def _upsert_weak_point(db: Session, student_id: str, course_id: str, kp: str, score: float, wrong_count: int) -> None:
    existing = db.execute(
        text(
            """
            SELECT id, wrong_count
            FROM weak_point_records
            WHERE student_id = :student_id
              AND course_id = :course_id
              AND knowledge_point = :knowledge_point
            LIMIT 1
            """
        ),
        {"student_id": student_id, "course_id": course_id, "knowledge_point": kp},
    ).mappings().first()
    params = {
        "student_id": student_id,
        "course_id": course_id,
        "knowledge_point": kp,
        "mastery_score": score,
        "wrong_count": wrong_count,
        "reason": "练习正确率低于 60%",
        "suggested_action": "复习概念说明并重做错题",
    }
    if existing:
        params["id"] = existing["id"]
        params["wrong_count"] = int(existing["wrong_count"] or 0) + wrong_count
        db.execute(
            text(
                """
                UPDATE weak_point_records
                SET mastery_score = :mastery_score,
                    wrong_count = :wrong_count,
                    reason = :reason,
                    suggested_action = :suggested_action,
                    source = 'exercise',
                    updated_at = NOW()
                WHERE id = :id
                """
            ),
            params,
        )
    else:
        params["id"] = "weak_" + uuid.uuid4().hex[:12]
        db.execute(
            text(
                """
                INSERT INTO weak_point_records (
                    id, student_id, course_id, knowledge_point, mastery_score,
                    wrong_count, reason, suggested_action, source, updated_at, created_at
                )
                VALUES (
                    :id, :student_id, :course_id, :knowledge_point, :mastery_score,
                    :wrong_count, :reason, :suggested_action, 'exercise', NOW(), NOW()
                )
                """
            ),
            params,
        )


def _answers_equal(left: Any, right: Any) -> bool:
    return _normalize_answer(left) == _normalize_answer(right)


def _normalize_knowledge_point(
    db: Session,
    course_id: str,
    raw_value: Any,
    fallback: str | None = None,
) -> str:
    raw_text = _clean_knowledge_text(raw_value)
    fallback_text = _clean_knowledge_text(fallback)
    candidates = [item for item in [raw_text, fallback_text] if item]

    course_points = _load_course_knowledge_names(db, course_id)
    for candidate in candidates:
        for point in course_points:
            if candidate == point:
                return point
        for point in course_points:
            if point and (point in candidate or candidate in point):
                return point

    if fallback_text and not _looks_like_sentence(fallback_text):
        return fallback_text
    if raw_text and not _looks_like_sentence(raw_text):
        return raw_text
    if course_points:
        return course_points[0]
    return "未标注知识点"


def _load_course_knowledge_names(db: Session, course_id: str) -> list[str]:
    rows = db.execute(
        text(
            """
            SELECT name
            FROM knowledge_points
            WHERE course_id = :course_id
            ORDER BY sort_order ASC, created_at ASC
            """
        ),
        {"course_id": course_id},
    ).mappings().all()
    return [row["name"] for row in rows if row["name"]]


def _knowledge_point_from_title(title: str | None) -> str | None:
    text_value = _clean_knowledge_text(title)
    if not text_value:
        return None
    suffixes = [
        "个性化练习题",
        "基础练习题",
        "练习题",
        "专项练习",
        "练习",
    ]
    for suffix in suffixes:
        if text_value.endswith(suffix):
            return text_value[: -len(suffix)].strip() or text_value
    return text_value


def _clean_knowledge_text(value: Any) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    if not text_value:
        return None
    return text_value


def _normalize_question_type(raw_type: Any) -> str:
    question_type = str(raw_type or "").strip()
    aliases = {
        "single_choice": "choice",
        "choice": "choice",
        "multiple_choice": "multi_choice",
        "multi": "multi_choice",
        "multi_choice": "multi_choice",
        "blank": "fill_blank",
        "fill": "fill_blank",
        "fill_blank": "fill_blank",
        "true_false": "true_false",
        "judgement": "true_false",
    }
    question_type = aliases.get(question_type, question_type)
    if question_type in ALLOWED_EXERCISE_TYPES:
        return question_type
    return "fill_blank"


def _normalize_question_text(raw_question: Any, question_type: str) -> str:
    question = str(raw_question or "").strip()
    if question_type == "fill_blank" and question and "___" not in question:
        return f"{question}___"
    return question


def _question_payload(item: dict[str, Any], question_type: str) -> Any:
    if question_type in {"choice", "multi_choice"}:
        return _normalize_options_payload(item.get("options"))
    if question_type == "fill_blank":
        return item.get("blanks")
    return None


def _correct_answer_payload(item: dict[str, Any], question_type: str) -> Any:
    if question_type == "fill_blank":
        blanks = item.get("blanks")
        if isinstance(blanks, list):
            return [blank.get("answer") for blank in blanks if isinstance(blank, dict)]
    return item.get("correct_answer") if "correct_answer" in item else item.get("answer")


def _normalize_options_payload(options: Any) -> Any:
    if not isinstance(options, list):
        return None
    normalized = []
    for index, option in enumerate(options):
        key = chr(ord("A") + index)
        if isinstance(option, dict):
            normalized.append(
                {
                    "key": str(option.get("key") or key),
                    "text": str(option.get("text") or option.get("value") or ""),
                }
            )
        else:
            normalized.append({"key": key, "text": str(option)})
    return normalized


def _looks_like_sentence(value: str) -> bool:
    if len(value) > 24:
        return True
    return any(mark in value for mark in ["。", "，", "；", "：", ".", ",", ";", ":"])


def _normalize_answer(value: Any) -> Any:
    if isinstance(value, str):
        value = value.strip()
        try:
            parsed = json.loads(value)
            return _normalize_answer(parsed)
        except json.JSONDecodeError:
            return value.lower()
    if isinstance(value, list):
        return sorted((_normalize_answer(item) for item in value), key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
    if isinstance(value, dict):
        return {str(k): _normalize_answer(v) for k, v in sorted(value.items())}
    return value


def _json_value(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value

