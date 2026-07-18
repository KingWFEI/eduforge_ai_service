from __future__ import annotations

from typing import Any

from app.constants.profile_dialogue import (
    PROFILE_DIALOGUE_FIELD_LABELS,
    PROFILE_DIALOGUE_SLOT_LABELS,
    PROFILE_DIALOGUE_SLOT_ORDER,
    PROFILE_DIALOGUE_VALUE_LABELS,
    PROFILE_SLOT_CONFIG,
    localize_profile_dialogue_slots,
)
from app.services.profile_dialogue_state_service import ProfileDialogueStateService


def _display_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, str):
        return PROFILE_DIALOGUE_VALUE_LABELS.get(value.strip().lower(), value.strip())
    return str(value)


def display_value(value: Any) -> str:
    if isinstance(value, list):
        return "、".join(_display_scalar(item) for item in value)
    return _display_scalar(value)


def normalize_profile_dialogue_fields(extracted_fields: dict | None) -> dict[str, dict]:
    return ProfileDialogueStateService().normalize_profile_fields(extracted_fields)


def build_profile_dialogue_display(
    *,
    current_slot: str | None,
    missing_slots: list[str] | None,
    extracted_fields: dict | None,
) -> dict[str, Any]:
    """构建稳定、扁平、中文化的前端展示结构。"""
    normalized = normalize_profile_dialogue_fields(extracted_fields)
    fields: list[dict[str, str]] = []

    for slot in PROFILE_DIALOGUE_SLOT_ORDER:
        slot_fields = normalized.get(slot) or {}
        config = PROFILE_SLOT_CONFIG[slot]
        ordered_fields = config["required_fields"] + config["optional_fields"]
        for field in ordered_fields:
            if field not in slot_fields:
                continue
            fields.append(
                {
                    "key": f"{slot}.{field}",
                    "label": PROFILE_DIALOGUE_FIELD_LABELS[field],
                    "value": display_value(slot_fields[field]),
                }
            )

    return {
        "current_slot": PROFILE_DIALOGUE_SLOT_LABELS.get(current_slot, "未知阶段"),
        "missing_slots": localize_profile_dialogue_slots(missing_slots),
        "fields": fields,
    }
