import asyncio
import json
import uuid
from typing import Any

from fastapi import status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agents.code_agent import CodeAgent
from app.agents.exercise_agent import ExerciseAgent
from app.agents.illustration_agent import IllustrationAgent
from app.agents.mindmap_agent import MindMapAgent
from app.agents.student_learning_content_agent import StudentLearningContentAgent
from app.models.resource_agent import LearningResource
from app.models.course_structure import SectionRecommendation
from app.models.student_profile import StudentProfile
from app.models.user import User
from app.services.llm_service import DeepSeekService
from app.services.illustration_render_service import render_python_illustration
from app.utils.response import AppException, ErrorCode
from app.constants.resource_generation import SUPPORTED_SECTION_RESOURCE_TYPES


SECTION_RESOURCE_TYPES = {item.value for item in SUPPORTED_SECTION_RESOURCE_TYPES}
LEGACY_INLINE_SECTION_RESOURCE_TYPES = {"illustration", "code_case", "exercise", "mind_map"}


def generate_section_resource(
    db: Session,
    current_user: User,
    course_id: str,
    section_id: str,
    resource_id: str | None,
    resource_type: str,
    content_id: str | None = None,
) -> dict[str, Any]:
    resource_type = str(resource_type or "").strip()
    if resource_type not in SECTION_RESOURCE_TYPES:
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message="不支持该小节资源类型",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if resource_type not in LEGACY_INLINE_SECTION_RESOURCE_TYPES:
        raise AppException(
            code=ErrorCode.CONFLICT,
            message="document / video / ppt 请使用统一异步入口 POST /api/resources/generate",
            status_code=status.HTTP_409_CONFLICT,
        )

    section = _load_section(db, course_id, section_id)
    content = _load_section_content(db, course_id, section_id, content_id)
    content_json = content["content_json"]
    shells = _get_or_create_resource_shells(
        db=db,
        current_user=current_user,
        course_id=course_id,
        section_id=section_id,
        section=section,
    )
    shell = _find_resource_shell(shells, resource_id, resource_type)
    if shell is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="资源壳子不存在或类型不匹配",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    chunks = _load_section_chunks(db, course_id, section)
    if resource_type == "exercise":
        resource = _build_stored_exercise_resource(content_json, shell, section)
        learning_resource_id = _save_section_learning_resource(
            db=db,
            current_user=current_user,
            course_id=course_id,
            section=section,
            shell=shell,
            resource_type=resource_type,
            resource=resource,
            content_id=content["content_id"],
            chunks=chunks,
            generation_model=None,
        )
        return {"generated": True, "resource_id": learning_resource_id}

    llm_service = DeepSeekService()
    input_data = {
        "db": db,
        "student_id": str(current_user.id),
        "course_id": course_id,
        "chapter_title": section.get("chapter_title"),
        "section_title": section.get("section_title"),
        "knowledge_point": _primary_knowledge_point(section),
        "knowledge_point_id": section.get("knowledge_point_id"),
        "goal": section.get("section_description") or section["section_title"],
        "difficulty": section.get("difficulty") or "基础",
        "profile": _load_student_profile(db, str(current_user.id)),
        "knowledge_chunks": chunks,
        "resource_plan": [
            {
                "resource_type": resource_type,
                "reason": shell.get("subtitle"),
                "focus": section["section_title"],
            }
        ],
        "generated_resources": [],
        "resource_types": [_agent_resource_type(resource_type)],
    }

    if resource_type == "illustration":
        illustration_result = asyncio.run(IllustrationAgent(llm_service).run(input_data))
        if not illustration_result["should_generate"]:
            return {"generated": False, "resource_id": None}
        resource = illustration_result["resource"]
        resource["title"] = resource.get("title") or shell["title"]
        resource["description"] = resource.get("description") or shell["subtitle"]
        rendered = render_python_illustration(resource.pop("_python_code"))
        resource["content_json"]["visualization"] = rendered
        resource["image_url"] = rendered["image_url"]
    else:
        resource = _run_resource_agent(llm_service, input_data, resource_type)
        resource["title"] = resource.get("title") or shell["title"]
        resource["description"] = resource.get("description") or shell["subtitle"]

    learning_resource_id = _save_section_learning_resource(
        db=db,
        current_user=current_user,
        course_id=course_id,
        section=section,
        shell=shell,
        resource_type=resource_type,
        resource=resource,
        content_id=content["content_id"],
        chunks=chunks,
        generation_model=llm_service.model,
    )
    return {"generated": True, "resource_id": learning_resource_id}


def _get_or_create_resource_shells(
    db: Session,
    current_user: User,
    course_id: str,
    section_id: str,
    section: dict[str, Any],
) -> list[dict[str, str]]:
    """只读取个性化推荐入口已确定的资源壳子。"""
    user_id = str(current_user.id)
    cached = (
        db.query(SectionRecommendation)
        .filter(
            SectionRecommendation.user_id == user_id,
            SectionRecommendation.course_id == course_id,
            SectionRecommendation.section_id == section_id,
        )
        .first()
    )
    if cached is not None and isinstance(cached.resources_json, list) and cached.resources_json:
        shells = [
            {
                "id": str(item.get("id") or ""),
                "title": str(item.get("title") or ""),
                "subtitle": str(item.get("subtitle") or ""),
                "type": str(item.get("type") or ""),
                "reason": str(item.get("reason") or ""),
            }
            for item in cached.resources_json
            if (
                isinstance(item, dict)
                and item.get("type") in SECTION_RESOURCE_TYPES
                and item.get("reason")
            )
        ]
        if shells:
            return shells

    raise AppException(
        code=ErrorCode.CONFLICT,
        message="请先调用小节个性化资源推荐接口获取可生成的资源列表",
        status_code=status.HTTP_409_CONFLICT,
    )


def _build_stored_exercise_resource(
    content_json: dict[str, Any],
    shell: dict[str, str],
    section: dict[str, Any],
) -> dict[str, Any]:
    exercises = StudentLearningContentAgent.normalize_exercises(
        content_json.get("exercises") if isinstance(content_json, dict) else [],
        section_id=section["section_id"],
        default_difficulty=section.get("difficulty") or "easy",
    )
    if not exercises:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="当前小节尚未生成随堂练习题，请重新生成小节学习内容",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return {
        "title": shell.get("title") or f"{section['section_title']}巩固练习",
        "content_json": {
            "title": shell.get("title") or f"{section['section_title']}巩固练习",
            "difficulty": section.get("difficulty") or "easy",
            "description": shell.get("subtitle"),
            "reason": "用于检测并巩固当前小节知识点掌握情况",
            "exercises": exercises,
        },
    }


def _find_resource_shell(
    shells: list[dict[str, str]],
    resource_id: str | None,
    resource_type: str,
) -> dict[str, str] | None:
    # 首次生成优先校验壳子 ID；后续生成可能只传 type，或者误传实际
    # learning_resource_id。每种 type 在一个小节中只有一个壳子，因此可安全回退。
    for shell in shells:
        if shell.get("id") == resource_id and shell.get("type") == resource_type:
            return shell
    for shell in shells:
        if shell.get("type") == resource_type:
            return shell
    return None


def _agent_resource_type(resource_type: str) -> str:
    return {
        "code_case": "code_case",
        "exercise": "exercise",
        "mind_map": "mind_map",
    }.get(resource_type, resource_type)


def _run_resource_agent(
    llm_service: DeepSeekService,
    input_data: dict[str, Any],
    resource_type: str,
) -> dict[str, Any]:
    agent_map = {
        "code_case": CodeAgent(llm_service),
        "exercise": ExerciseAgent(llm_service),
        "mind_map": MindMapAgent(llm_service),
    }
    result = asyncio.run(agent_map[resource_type].run(input_data))
    resources = result.get("generated_resources") or []
    if not resources:
        raise RuntimeError("AI 未返回可用资源内容")
    return resources[-1]


def _generate_illustration_resource(
    llm_service: DeepSeekService,
    input_data: dict[str, Any],
    shell: dict[str, str],
) -> dict[str, Any]:
    payload = {
        "title": shell.get("title"),
        "subtitle": shell.get("subtitle"),
        "knowledge_point": input_data.get("knowledge_point"),
        "goal": input_data.get("goal"),
        "difficulty": input_data.get("difficulty"),
        "profile": input_data.get("profile"),
        "knowledge_chunks": input_data.get("knowledge_chunks"),
    }
    result = llm_service.generate_json_sync(
        system_prompt=(
            "你是 EduForge AI 的图解资源生成智能体。"
            "你必须严格输出 JSON 对象，不输出 Markdown，不生成真实图片文件。"
        ),
        user_prompt=f"""
请基于输入生成一个适合前端展示的图解讲解资源。

输入：
{json.dumps(payload, ensure_ascii=False, indent=2)}

要求：
1. 只基于课程资料和小节信息生成，不要编造资料之外的事实。
2. 输出内容用于前端渲染图解卡片、步骤图或流程图，不需要图片 URL。
3. scenes 是图解分镜，每个分镜包含 title、visual、explanation。
4. 严格输出 JSON。

JSON 格式：
{{
  "title": "",
  "description": "",
  "overview": "",
  "scenes": [
    {{
      "title": "",
      "visual": "",
      "explanation": ""
    }}
  ],
  "key_takeaways": []
}}
""",
        max_tokens=2500,
        temperature=0.25,
    )
    title = result.get("title") or shell.get("title")
    return {
        "type": "illustration",
        "title": title,
        "description": result.get("description") or shell.get("subtitle"),
        "content_text": result.get("overview"),
        "content_json": result,
        "source": "DeepSeek + 课程知识库 + 学生画像",
    }


def _save_section_learning_resource(
    db: Session,
    current_user: User,
    course_id: str,
    section: dict[str, Any],
    shell: dict[str, str],
    resource_type: str,
    resource: dict[str, Any],
    content_id: str | None,
    chunks: list[dict[str, Any]],
    generation_model: str | None,
) -> str:
    student_id = str(current_user.id)
    resource_id = _new_section_learning_resource_id()
    content_json = _json_value(resource.get("content_json"), {})
    if not isinstance(content_json, dict):
        content_json = {"value": content_json}
    content_json = {
        **content_json,
        "_metadata": {
            "source": "section_resource_generate",
            "resource_shell_id": shell.get("id"),
            "section_id": section["section_id"],
            "chapter_id": section.get("chapter_id"),
            "content_id": content_id,
            "resource_type": resource_type,
            "source_chunk_ids": [item["chunk_id"] for item in chunks if item.get("chunk_id")],
            "generation_model": generation_model,
        },
    }

    item = LearningResource(id=resource_id)
    db.add(item)

    item.student_id = student_id
    item.course_id = course_id
    item.knowledge_point_id = section.get("knowledge_point_id")
    item.title = resource.get("title") or shell.get("title") or section["section_title"]
    item.type = resource_type
    item.difficulty = section.get("difficulty") or "基础"
    item.description = resource.get("description") or shell.get("subtitle")
    item.reason = shell.get("subtitle") or f"根据小节《{section['section_title']}》生成"
    item.content_text = resource.get("content_text")
    item.content_json = content_json
    item.source = resource.get("source") or "section_resource_generate"
    item.review_status = "auto_passed"
    item.generated_by_task_id = None
    db.commit()
    return resource_id


def _new_section_learning_resource_id() -> str:
    return "slr_" + uuid.uuid4().hex[:20]


def list_generated_section_resources(
    db: Session,
    current_user: User,
    course_id: str,
    section_id: str,
) -> list[dict[str, Any]]:
    """返回当前用户在该小节生成过的全部资源，最新资源排在前面。"""
    rows = (
        db.query(LearningResource)
        .filter(
            LearningResource.student_id == str(current_user.id),
            LearningResource.course_id == course_id,
            LearningResource.review_status.in_(["approved", "auto_passed"]),
        )
        .order_by(LearningResource.created_at.desc(), LearningResource.id.desc())
        .all()
    )
    resources = []
    for item in rows:
        content_json = _json_value(item.content_json, {})
        metadata = content_json.get("_metadata", {}) if isinstance(content_json, dict) else {}
        if metadata.get("section_id") != section_id:
            continue
        resources.append(
            {
                "resource_id": item.id,
                "title": item.title,
                "type": item.type,
                "description": item.description,
                "content_text": item.content_text,
                "content_json": content_json,
                "image_url": (
                    content_json.get("visualization", {}).get("image_url")
                    if isinstance(content_json, dict)
                    else None
                ),
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
        )
    return resources


def get_generated_section_resource(
    db: Session,
    current_user: User,
    course_id: str,
    section_id: str,
    resource_id: str,
) -> dict[str, Any]:
    """根据实际资源 ID 返回当前用户在指定小节生成的资源详情。"""
    item = db.get(LearningResource, resource_id)
    if (
        item is None
        or str(item.student_id) != str(current_user.id)
        or str(item.course_id) != str(course_id)
        or item.review_status not in {"approved", "auto_passed"}
    ):
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="资源不存在或无权访问",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    content_json = _json_value(item.content_json, {})
    metadata = content_json.get("_metadata", {}) if isinstance(content_json, dict) else {}
    if str(metadata.get("section_id") or "") != str(section_id):
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="资源不属于当前小节",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    visualization = content_json.get("visualization", {}) if isinstance(content_json, dict) else {}
    return {
        "resource_id": item.id,
        "course_id": item.course_id,
        "section_id": section_id,
        "knowledge_point_id": item.knowledge_point_id,
        "title": item.title,
        "type": item.type,
        "difficulty": item.difficulty,
        "description": item.description,
        "content_text": item.content_text,
        "content_json": content_json,
        "image_url": visualization.get("image_url") if isinstance(visualization, dict) else None,
        "source": item.source,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _load_section(db: Session, course_id: str, section_id: str) -> dict[str, Any]:
    row = db.execute(
        text(
            """
            SELECT
                s.id AS section_id,
                s.course_id,
                s.title AS section_title,
                s.description AS section_description,
                p.id AS chapter_id,
                p.title AS chapter_title
            FROM course_chapters s
            LEFT JOIN course_chapters p ON p.id = s.parent_id
            WHERE s.course_id = :course_id
              AND s.id = :section_id
            LIMIT 1
            """
        ),
        {"course_id": course_id, "section_id": section_id},
    ).mappings().first()
    if row is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="小节不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    section = dict(row)
    point_rows = db.execute(
        text(
            """
            SELECT id, name, description, difficulty
            FROM knowledge_points
            WHERE course_id = :course_id
              AND chapter_id = :section_id
            ORDER BY sort_order ASC, created_at ASC
            """
        ),
        {"course_id": course_id, "section_id": section_id},
    ).mappings().all()
    section["knowledge_points"] = [dict(item) for item in point_rows]
    if point_rows:
        section["knowledge_point_id"] = point_rows[0]["id"]
        section["difficulty"] = point_rows[0]["difficulty"]
    else:
        section["knowledge_point_id"] = None
        section["difficulty"] = "基础"
    return section


def _load_section_content(
    db: Session,
    course_id: str,
    section_id: str,
    content_id: str | None,
) -> dict[str, Any]:
    where = [
        "course_id = :course_id",
        "section_id = :section_id",
        "status IN ('generated', 'completed')",
    ]
    params = {"course_id": course_id, "section_id": section_id}
    if content_id:
        where.append("id = :content_id")
        params["content_id"] = content_id

    row = db.execute(
        text(
            f"""
            SELECT id, content_json
            FROM course_section_learning_contents
            WHERE {' AND '.join(where)}
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        params,
    ).mappings().first()
    if row is None:
        if content_id:
            raise AppException(
                code=ErrorCode.NOT_FOUND,
                message="小节内容不存在",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return {"content_id": None, "content_json": {}}
    return {"content_id": row["id"], "content_json": _json_value(row["content_json"], {})}


def _load_section_chunks(
    db: Session,
    course_id: str,
    section: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT id AS chunk_id, content, section, page_no, chapter_id, knowledge_point_id
            FROM knowledge_chunks
            WHERE course_id = :course_id
              AND COALESCE(deleted, 0) = 0
              AND (
                chapter_id = :section_id
                OR knowledge_point_id = :knowledge_point_id
              )
            ORDER BY chunk_index ASC
            LIMIT 8
            """
        ),
        {
            "course_id": course_id,
            "section_id": section["section_id"],
            "knowledge_point_id": section.get("knowledge_point_id"),
        },
    ).mappings().all()
    if rows:
        return [dict(row) for row in rows]

    fallback_rows = db.execute(
        text(
            """
            SELECT id AS chunk_id, content, section, page_no, chapter_id, knowledge_point_id
            FROM knowledge_chunks
            WHERE course_id = :course_id
              AND COALESCE(deleted, 0) = 0
            ORDER BY chunk_index ASC
            LIMIT 5
            """
        ),
        {"course_id": course_id},
    ).mappings().all()
    return [dict(row) for row in fallback_rows]


def _load_student_profile(db: Session, student_id: str) -> dict[str, Any]:
    profile = db.query(StudentProfile).filter(StudentProfile.student_id == student_id).first()
    if profile is None:
        return {
            "student_id": student_id,
            "learning_preferences": ["图解讲解"],
            "coding_level": "一般",
            "course_level": "入门",
            "summary": "暂未生成学习画像，使用默认画像。",
        }
    return {
        "student_id": student_id,
        "learning_goals": profile.learning_goals_json or [],
        "coding_level": profile.coding_level,
        "math_level": profile.math_level,
        "course_level": profile.course_level,
        "learning_preferences": profile.learning_preferences_json or [],
        "weaknesses": profile.weaknesses_json or [],
        "summary": profile.summary,
    }


def _primary_knowledge_point(section: dict[str, Any]) -> str:
    points = section.get("knowledge_points") or []
    if points:
        return points[0].get("name") or section["section_title"]
    return section["section_title"]


def _json_value(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default
