from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import status
from sqlalchemy.orm import Session

from app.models.learning_profile import StudentLearningProfile
from app.models.profile_analysis import ProfileVersion
from app.models.profile_dialogue_sessions import ProfileDialogueSession
from app.models.user import UserOnboardingStatus
from app.services.profile_dialogue_presenter import (
    build_profile_dialogue_display,
    normalize_profile_dialogue_fields,
)
from app.services.learning_style_character_service import (
    get_student_learning_style_character,
    match_and_persist_character,
)
from app.utils.response import AppException, ErrorCode


def _as_list(*values: Any) -> list[Any]:
    result: list[Any] = []
    for value in values:
        items = value if isinstance(value, list) else [value]
        for item in items:
            if item is None or item == "" or item in result:
                continue
            result.append(item)
    return result


def _profile_values(fields: dict[str, dict], preview: dict, session_id: int) -> dict:
    learning_style = fields.get("learning_style") or {}
    learning_habits = fields.get("learning_habits") or {}
    motivation = fields.get("motivation") or {}
    strengths = fields.get("strengths_challenges") or {}
    pace = fields.get("pace_and_time") or {}

    display = build_profile_dialogue_display(
        current_slot="confirm",
        missing_slots=[],
        extracted_fields=fields,
    )
    summary = preview.get("summary") if isinstance(preview.get("summary"), str) else ""
    if not summary.strip():
        summary_values = [item["value"] for item in display["fields"][:5]]
        summary = (
            "已通过对话整理学习画像：" + "；".join(summary_values)
            if summary_values
            else "已通过对话完成基础学习画像。"
        )

    confidence = preview.get("confidence", 0.0)
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        confidence = 0.0

    return {
        "learning_preferences_json": _as_list(
            learning_style.get("preferred_content_formats"),
            learning_style.get("theory_practice_preference"),
            learning_style.get("interaction_preference"),
        ),
        "cognitive_traits_json": _as_list(learning_style.get("cognitive_preference")),
        "learning_habits_json": _as_list(
            learning_habits.get("planning_habit"),
            learning_habits.get("review_habit"),
            learning_habits.get("note_taking_habit"),
            learning_habits.get("focus_environment"),
        ),
        "motivation_factors_json": _as_list(
            motivation.get("primary_learning_goal"),
            motivation.get("motivation_source"),
            motivation.get("expected_outcome"),
        ),
        "general_strengths_json": _as_list(strengths.get("learning_strengths")),
        "general_challenges_json": _as_list(
            strengths.get("learning_challenges"),
            strengths.get("difficult_knowledge_types"),
        ),
        "preferred_pace": pace.get("preferred_learning_pace"),
        "available_time_json": {
            key: pace[key]
            for key in (
                "available_learning_time",
                "preferred_learning_period",
                "session_duration",
            )
            if key in pace
        },
        "summary": summary.strip()[:1000],
        "profile_dimensions_json": fields,
        "evidence_json": [
            {
                "source": "profile_dialogue",
                "session_id": session_id,
                "fields": [item["key"] for item in display["fields"]],
            }
        ],
        "confidence_json": {
            "overall": max(0.0, min(1.0, float(confidence))),
            "source": "profile_dialogue",
        },
    }


def _snapshot(profile: StudentLearningProfile) -> dict[str, Any]:
    return {
        "learning_preferences": profile.learning_preferences_json or [],
        "cognitive_traits": profile.cognitive_traits_json or [],
        "learning_habits": profile.learning_habits_json or [],
        "motivation_factors": profile.motivation_factors_json or [],
        "general_strengths": profile.general_strengths_json or [],
        "general_challenges": profile.general_challenges_json or [],
        "preferred_pace": profile.preferred_pace,
        "available_time": profile.available_time_json or {},
        "summary": profile.summary,
        "profile_dimensions": profile.profile_dimensions_json or {},
        "evidence": profile.evidence_json or [],
        "confidence": profile.confidence_json or {},
    }


def confirm_dialogue_profile(
    db: Session,
    *,
    session_id: int,
    student_id: int,
) -> dict[str, Any]:
    session = (
        db.query(ProfileDialogueSession)
        .filter(
            ProfileDialogueSession.id == session_id,
            ProfileDialogueSession.student_id == student_id,
        )
        .first()
    )
    if session is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="画像对话会话不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    student_key = str(student_id)
    if session.status == "completed" and session.profile_id:
        profile = (
            db.query(StudentLearningProfile)
            .filter(
                StudentLearningProfile.id == str(session.profile_id),
                StudentLearningProfile.student_id == student_key,
            )
            .first()
        )
        if profile is not None:
            return _confirmation_response(db, session, profile)

    legacy_completed_without_profile = (
        session.status == "completed"
        and not session.profile_id
        and bool(session.extracted_fields_json)
    )
    if session.status != "ready_to_confirm" and not legacy_completed_without_profile:
        raise AppException(
            code=ErrorCode.CONFLICT,
            message="当前画像还未生成，不能确认保存",
            status_code=status.HTTP_409_CONFLICT,
        )

    fields = normalize_profile_dialogue_fields(session.extracted_fields_json)
    preview = session.profile_preview_json if isinstance(session.profile_preview_json, dict) else {}
    values = _profile_values(fields, preview, session.id)

    profile = (
        db.query(StudentLearningProfile)
        .filter(StudentLearningProfile.student_id == student_key)
        .first()
    )
    previous_dimensions = dict(profile.profile_dimensions_json or {}) if profile else {}
    if profile is None:
        profile = StudentLearningProfile(
            id="learning_profile_" + uuid4().hex[:12],
            student_id=student_key,
            version=1,
        )
        db.add(profile)
    else:
        profile.version = (profile.version or 0) + 1

    for field, value in values.items():
        setattr(profile, field, value)
    profile.source = "profile_dialogue"
    profile.last_updated = datetime.now(timezone.utc)
    db.flush()

    db.add(
        ProfileVersion(
            id="profile_version_" + uuid4().hex[:12],
            profile_id=profile.id,
            student_id=student_key,
            version=profile.version,
            source="profile_dialogue",
            profile_snapshot_json=_snapshot(profile),
            changed_fields_json={
                "previous_profile_dimensions": previous_dimensions,
                "current_profile_dimensions": fields,
            },
            summary=profile.summary,
        )
    )

    onboarding_status = (
        db.query(UserOnboardingStatus)
        .filter(UserOnboardingStatus.user_id == student_id)
        .first()
    )
    if onboarding_status is None:
        onboarding_status = UserOnboardingStatus(user_id=student_id)
        db.add(onboarding_status)
    onboarding_status.status = "completed"
    onboarding_status.profile_id = profile.id
    onboarding_status.need_onboarding = False
    onboarding_status.completed_at = datetime.now(timezone.utc)

    session.status = "completed"
    session.current_slot = "confirm"
    session.profile_id = profile.id
    session.end_reason = "completed"
    session.ended_at = datetime.now(timezone.utc)
    session.last_active_at = datetime.now(timezone.utc)
    db.add(session)

    match_and_persist_character(
        db,
        student_id=student_key,
        profile=profile,
    )
    db.commit()
    db.refresh(profile)
    db.refresh(session)
    return _confirmation_response(db, session, profile)


def _confirmation_response(
    db: Session,
    session: ProfileDialogueSession,
    profile: StudentLearningProfile,
) -> dict[str, Any]:
    fields = normalize_profile_dialogue_fields(session.extracted_fields_json)
    return {
        "session_id": session.id,
        "status": session.status,
        "profile_id": profile.id,
        "profile_version": profile.version or 1,
        "profile_source": profile.source,
        "profile_preview": session.profile_preview_json or {},
        "profile_fields": fields,
        "display": build_profile_dialogue_display(
            current_slot="confirm",
            missing_slots=[],
            extracted_fields=fields,
        ),
        "learning_style_character": get_student_learning_style_character(
            db,
            student_id=profile.student_id,
        ),
    }
