import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile, status
from sqlalchemy.orm import Session

from app.models.learning_profile import StudentLearningProfile
from app.models.learning_style_character import LearningStyleCharacter, StudentStyleMatch
from app.schemas.learning_style_character import LearningStyleCharacterUpdate
from app.utils.response import AppException, ErrorCode

UPLOAD_ROOT = Path("uploads") / "learning-styles"
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
VALID_CHARACTER_STATUSES = {"DRAFT", "PUBLISHED", "DISABLED"}


def parse_json_array(value: str | None, field_name: str) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message=f"{field_name} must be a JSON array string",
            status_code=status.HTTP_400_BAD_REQUEST,
        ) from exc
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message=f"{field_name} must be a JSON array of strings",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return parsed


def _serialize_character(character: LearningStyleCharacter) -> dict[str, Any]:
    return {
        "id": character.id,
        "name": character.name,
        "code": character.code,
        "image_url": character.image_url,
        "description": character.description,
        "style_prompt": character.style_prompt,
        "feature_tags": character.feature_tags or [],
        "suitable_methods": character.suitable_methods or [],
        "status": character.status,
        "priority": character.priority,
        "version": character.version,
        "created_by": character.created_by,
        "created_at": character.created_at.isoformat() if character.created_at else None,
        "updated_at": character.updated_at.isoformat() if character.updated_at else None,
    }


def _get_character_or_404(db: Session, character_id: str) -> LearningStyleCharacter:
    character = (
        db.query(LearningStyleCharacter)
        .filter(LearningStyleCharacter.id == character_id)
        .first()
    )
    if character is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="Learning style character not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return character


def _ensure_unique_code(db: Session, code: str, exclude_id: str | None = None) -> None:
    query = db.query(LearningStyleCharacter).filter(LearningStyleCharacter.code == code)
    if exclude_id:
        query = query.filter(LearningStyleCharacter.id != exclude_id)
    if query.first() is not None:
        raise AppException(
            code=ErrorCode.CONFLICT,
            message="Character code already exists",
            status_code=status.HTTP_409_CONFLICT,
        )


def save_character_image(image: UploadFile) -> str:
    filename = image.filename or ""
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message="Only png, jpg, jpeg, webp, and gif images are supported",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}{extension}"
    target_path = UPLOAD_ROOT / stored_name
    with target_path.open("wb") as target:
        shutil.copyfileobj(image.file, target)
    return f"/uploads/learning-styles/{stored_name}"


def create_character(
    db: Session,
    *,
    name: str,
    code: str,
    image: UploadFile,
    description: str | None,
    style_prompt: str | None,
    feature_tags: list[str],
    suitable_methods: list[str],
    priority: int,
    created_by: str,
) -> dict[str, Any]:
    _ensure_unique_code(db, code)
    image_url = save_character_image(image)
    character = LearningStyleCharacter(
        id=uuid4().hex,
        name=name,
        code=code,
        image_url=image_url,
        description=description,
        style_prompt=style_prompt,
        feature_tags=feature_tags,
        suitable_methods=suitable_methods,
        priority=priority,
        status="DRAFT",
        version=1,
        created_by=created_by,
    )
    db.add(character)
    db.commit()
    db.refresh(character)
    return {
        "id": character.id,
        "name": character.name,
        "code": character.code,
        "image_url": character.image_url,
        "status": character.status,
    }


def list_characters(
    db: Session,
    *,
    status_value: str | None,
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], int]:
    query = db.query(LearningStyleCharacter)
    if status_value:
        if status_value not in VALID_CHARACTER_STATUSES:
            raise AppException(
                code=ErrorCode.PARAM_ERROR,
                message="Invalid character status",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        query = query.filter(LearningStyleCharacter.status == status_value)
    total = query.count()
    items = (
        query.order_by(LearningStyleCharacter.priority.desc(), LearningStyleCharacter.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return [_serialize_character(item) for item in items], total


def get_character_detail(db: Session, character_id: str) -> dict[str, Any]:
    return _serialize_character(_get_character_or_404(db, character_id))


def update_character(
    db: Session,
    *,
    character_id: str,
    payload: LearningStyleCharacterUpdate,
) -> dict[str, Any]:
    character = _get_character_or_404(db, character_id)
    data = payload.model_dump(exclude_unset=True)
    if "code" in data and data["code"] != character.code:
        _ensure_unique_code(db, data["code"], exclude_id=character.id)
    for field, value in data.items():
        setattr(character, field, value)
    character.version = (character.version or 1) + 1
    db.commit()
    db.refresh(character)
    return _serialize_character(character)


def update_character_image(db: Session, *, character_id: str, image: UploadFile) -> dict[str, Any]:
    character = _get_character_or_404(db, character_id)
    character.image_url = save_character_image(image)
    character.version = (character.version or 1) + 1
    db.commit()
    db.refresh(character)
    return _serialize_character(character)


def update_character_status(db: Session, *, character_id: str, status_value: str) -> dict[str, Any]:
    if status_value not in VALID_CHARACTER_STATUSES:
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message="Invalid character status",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    character = _get_character_or_404(db, character_id)
    character.status = status_value
    character.version = (character.version or 1) + 1
    db.commit()
    db.refresh(character)
    return _serialize_character(character)


def disable_character(db: Session, *, character_id: str) -> bool:
    character = _get_character_or_404(db, character_id)
    character.status = "DISABLED"
    character.version = (character.version or 1) + 1
    db.commit()
    return True


def _flatten_profile_terms(profile: StudentLearningProfile) -> list[str]:
    values: list[Any] = [
        profile.learning_preferences_json,
        profile.cognitive_traits_json,
        profile.learning_habits_json,
        profile.motivation_factors_json,
        profile.general_strengths_json,
        profile.general_challenges_json,
        profile.preferred_pace,
        profile.available_time_json,
        profile.summary,
        profile.profile_dimensions_json,
    ]
    terms: list[str] = []

    def collect(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized:
                terms.append(normalized)
            return
        if isinstance(value, dict):
            for key, item in value.items():
                collect(key)
                collect(item)
            return
        if isinstance(value, list):
            for item in value:
                collect(item)

    for value in values:
        collect(value)
    return terms


def _score_character(profile_terms: list[str], character: LearningStyleCharacter) -> tuple[float, list[str]]:
    feature_tags = character.feature_tags or []
    suitable_methods = character.suitable_methods or []
    weighted_tags = [(tag, 0.7) for tag in feature_tags] + [(method, 0.3) for method in suitable_methods]
    if not weighted_tags:
        return 0.01, []

    score = 0.0
    matched_features: list[str] = []
    profile_blob = " ".join(profile_terms)
    for tag, weight in weighted_tags:
        normalized_tag = tag.strip().lower()
        if not normalized_tag:
            continue
        matched = normalized_tag in profile_blob or any(term in normalized_tag for term in profile_terms)
        if matched:
            score += weight
            if tag not in matched_features:
                matched_features.append(tag)

    max_score = sum(weight for _, weight in weighted_tags) or 1
    normalized_score = min(score / max_score, 1.0)
    if not matched_features:
        normalized_score = 0.2 + min((character.priority or 0) / 100, 0.1)
    return round(normalized_score, 2), matched_features[:5]


def _build_reason(character: LearningStyleCharacter, matched_features: list[str]) -> str:
    if matched_features:
        features = "、".join(matched_features[:3])
        return f"你的学习画像与该人物的{features}等特征较匹配。"
    if character.description:
        return f"根据当前画像信息，优先推荐这个学习风格人物：{character.description[:60]}"
    return "根据当前画像信息，系统推荐这个学习风格人物。"


def _build_match_response(
    *,
    character: LearningStyleCharacter,
    match: StudentStyleMatch,
) -> dict[str, Any]:
    return {
        "status": "MATCHED",
        "profile_required": False,
        "character": {
            "id": character.id,
            "code": character.code,
            "name": character.name,
            "image_url": character.image_url,
            "description": character.description,
            "match_score": match.match_score,
            "match_reason": match.match_reason,
            "matched_features": match.matched_features or [],
            "suitable_methods": character.suitable_methods or [],
        },
        "matched_at": match.updated_at.isoformat() if match.updated_at else None,
    }


def get_student_learning_style_character(db: Session, *, student_id: str) -> dict[str, Any]:
    profile = (
        db.query(StudentLearningProfile)
        .filter(StudentLearningProfile.student_id == student_id)
        .first()
    )
    if profile is None:
        return {
            "status": "PROFILE_REQUIRED",
            "profile_required": True,
            "character": None,
            "action": {
                "type": "CREATE_PROFILE",
                "route": "/profile/create",
                "button_text": "生成学习画像",
            },
        }

    existing_match = (
        db.query(StudentStyleMatch)
        .filter(
            StudentStyleMatch.student_id == student_id,
            StudentStyleMatch.profile_id == profile.id,
        )
        .order_by(StudentStyleMatch.updated_at.desc())
        .first()
    )
    if existing_match is not None and existing_match.profile_version == (profile.version or 1):
        cached_character = (
            db.query(LearningStyleCharacter)
            .filter(
                LearningStyleCharacter.id == existing_match.character_id,
                LearningStyleCharacter.status == "PUBLISHED",
                LearningStyleCharacter.version == existing_match.character_version,
            )
            .first()
        )
        if cached_character is not None:
            return _build_match_response(character=cached_character, match=existing_match)

    characters = (
        db.query(LearningStyleCharacter)
        .filter(LearningStyleCharacter.status == "PUBLISHED")
        .order_by(LearningStyleCharacter.priority.desc(), LearningStyleCharacter.created_at.desc())
        .all()
    )
    if not characters:
        return {
            "status": "STYLE_UNAVAILABLE",
            "profile_required": False,
            "character": None,
        }

    profile_terms = _flatten_profile_terms(profile)
    scored = []
    for character in characters:
        score, matched_features = _score_character(profile_terms, character)
        scored.append((score, character.priority or 0, character, matched_features))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    score, _, best_character, matched_features = scored[0]

    match = existing_match or StudentStyleMatch(
        id=uuid4().hex,
        student_id=student_id,
        profile_id=profile.id,
    )
    match.profile_version = profile.version or 1
    match.character_id = best_character.id
    match.character_version = best_character.version or 1
    match.match_score = score
    match.match_reason = _build_reason(best_character, matched_features)
    match.matched_features = matched_features
    match.matching_source = "rule"
    match.updated_at = datetime.now(timezone.utc)
    db.add(match)
    db.commit()
    db.refresh(match)
    return _build_match_response(character=best_character, match=match)
