from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.constants.profile_dialogue import (
    PROFILE_DIALOGUE_SLOT_ORDER,
    PROFILE_FIELD_QUESTIONS,
    PROFILE_SLOT_CONFIG,
)


INVALID_TEXT_VALUES = {
    "",
    "unknown",
    "不知道",
    "不清楚",
    "未提供",
    "没有",
    "无",
}

MAX_PROFILE_TEXT_LENGTH = 500
MAX_PROFILE_LIST_ITEMS = 20

REFUSAL_MARKERS = (
    "不想说",
    "不愿意说",
    "不方便说",
    "拒绝回答",
    "跳过",
    "不知道",
    "不清楚",
    "没想过",
)

LEGACY_FIELD_MAPPING = {
    "learning_preferences": ("learning_style", "preferred_content_formats"),
    "cognitive_traits": ("learning_style", "cognitive_preference"),
    "learning_habits": ("learning_habits", "planning_habit"),
    "motivation_factors": ("motivation", "primary_learning_goal"),
    "general_strengths": ("strengths_challenges", "learning_strengths"),
    "general_challenges": ("strengths_challenges", "learning_challenges"),
    "preferred_pace": ("pace_and_time", "preferred_learning_pace"),
    "available_time": ("pace_and_time", "available_learning_time"),
}


@dataclass(frozen=True)
class DialogueAction:
    action: str
    current_slot: str
    next_slot: str
    question_field: str | None
    question_text: str | None
    acknowledgement: str
    need_summary: bool
    profile_completed: bool
    question_attempt_count: int = 0

    @property
    def should_advance(self) -> bool:
        return self.action in {"advance", "skip_and_advance", "confirm_profile"}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProfileDialogueStateService:
    """Deterministic profile coverage, deduplication, and dialogue decisions."""

    def normalize_profile_fields(self, profile_data: dict | None) -> dict[str, dict]:
        source = profile_data if isinstance(profile_data, dict) else {}
        normalized = {slot: {} for slot in PROFILE_DIALOGUE_SLOT_ORDER}
        sanitized_source = self.sanitize_slot_updates(
            {slot: source.get(slot) for slot in PROFILE_DIALOGUE_SLOT_ORDER}
        )
        for slot, fields in sanitized_source.items():
            normalized[slot].update(fields)
        for field, value in source.items():
            if field in PROFILE_DIALOGUE_SLOT_ORDER:
                continue
            mapping = LEGACY_FIELD_MAPPING.get(field)
            normalized_value = self.normalize_field_value(value)
            if mapping and normalized_value is not None:
                slot, new_field = mapping
                normalized[slot].setdefault(new_field, normalized_value)
        return normalized

    def sanitize_slot_updates(self, slot_updates: dict | None) -> dict[str, dict]:
        sanitized: dict[str, dict] = {}
        for slot, fields in (slot_updates or {}).items():
            if slot not in PROFILE_SLOT_CONFIG or not isinstance(fields, dict):
                continue
            allowed = set(PROFILE_SLOT_CONFIG[slot]["required_fields"])
            allowed.update(PROFILE_SLOT_CONFIG[slot]["optional_fields"])
            valid_fields = {}
            for field, value in fields.items():
                if field not in allowed:
                    continue
                normalized_value = self.normalize_field_value(value)
                if normalized_value is not None:
                    valid_fields[field] = normalized_value
            if valid_fields:
                sanitized[slot] = valid_fields
        return sanitized

    def merge_profile_fields(
        self,
        existing_profile: dict | None,
        slot_updates: dict | None,
    ) -> dict[str, dict]:
        merged = self.normalize_profile_fields(existing_profile)
        for slot, fields in self.sanitize_slot_updates(slot_updates).items():
            for field, value in fields.items():
                merged[slot][field] = value
        return merged

    @staticmethod
    def has_valid_value(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return value.strip().lower() not in INVALID_TEXT_VALUES
        if isinstance(value, (list, tuple, set, dict)):
            return bool(value)
        return True

    @classmethod
    def normalize_field_value(cls, value: Any) -> Any | None:
        """只接受可预测的标量或标量列表，拒绝 LLM 任意嵌套对象。"""
        if value is None or isinstance(value, dict):
            return None
        if isinstance(value, str):
            normalized = value.strip()
            if not cls.has_valid_value(normalized):
                return None
            return normalized[:MAX_PROFILE_TEXT_LENGTH]
        if isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, (list, tuple, set)):
            normalized_items = []
            for item in list(value)[:MAX_PROFILE_LIST_ITEMS]:
                if isinstance(item, (dict, list, tuple, set)):
                    continue
                normalized_item = cls.normalize_field_value(item)
                if normalized_item is not None and normalized_item not in normalized_items:
                    normalized_items.append(normalized_item)
            return normalized_items or None
        return None

    def calculate_slot_coverage(self, slot: str, slot_data: dict | None) -> float:
        config = PROFILE_SLOT_CONFIG[slot]
        required = config["required_fields"]
        completed = sum(
            1 for field in required if self.has_valid_value((slot_data or {}).get(field))
        )
        return round(completed / len(required), 2) if required else 1.0

    def is_slot_sufficient(self, slot: str, slot_data: dict | None) -> bool:
        config = PROFILE_SLOT_CONFIG[slot]
        completed = sum(
            1
            for field in config["required_fields"]
            if self.has_valid_value((slot_data or {}).get(field))
        )
        return completed >= config["min_required_fields"]

    def calculate_all_slot_states(self, profile_data: dict) -> dict[str, dict]:
        return {
            slot: {
                "coverage": self.calculate_slot_coverage(slot, profile_data.get(slot)),
                "sufficient": self.is_slot_sufficient(slot, profile_data.get(slot)),
                "present_fields": sorted(
                    field
                    for field, value in profile_data.get(slot, {}).items()
                    if self.has_valid_value(value)
                ),
            }
            for slot in PROFILE_DIALOGUE_SLOT_ORDER
        }

    @staticmethod
    def get_question_attempt_count(dialogue_state: dict, slot: str, field: str) -> int:
        key = f"{slot}.{field}"
        return int((dialogue_state.get("asked_fields") or {}).get(key, {}).get("count", 0))

    def increase_question_attempt(
        self,
        dialogue_state: dict,
        slot: str,
        field: str,
        question: str,
    ) -> int:
        key = f"{slot}.{field}"
        asked_fields = dialogue_state.setdefault("asked_fields", {})
        count = self.get_question_attempt_count(dialogue_state, slot, field) + 1
        asked_fields[key] = {"count": count, "last_question": question}
        dialogue_state["last_question_field"] = key
        return count

    @staticmethod
    def mark_field_skipped(dialogue_state: dict, slot: str, field: str) -> None:
        key = f"{slot}.{field}"
        skipped = dialogue_state.setdefault("skipped_fields", [])
        if key not in skipped:
            skipped.append(key)
        if dialogue_state.get("last_question_field") == key:
            dialogue_state["last_question_field"] = None

    def has_field_been_asked(self, dialogue_state: dict, slot: str, field: str) -> bool:
        return self.get_question_attempt_count(dialogue_state, slot, field) > 0

    @staticmethod
    def is_refusal(user_message: str) -> bool:
        normalized = (user_message or "").strip().lower()
        return any(marker in normalized for marker in REFUSAL_MARKERS)

    def _consume_unanswered_last_question(
        self,
        dialogue_state: dict,
        profile_data: dict,
    ) -> None:
        key = dialogue_state.get("last_question_field")
        if not key or "." not in key:
            return
        slot, field = key.split(".", 1)
        if not self.has_valid_value(profile_data.get(slot, {}).get(field)):
            self.mark_field_skipped(dialogue_state, slot, field)
        else:
            dialogue_state["last_question_field"] = None

    def find_next_question_field(
        self,
        slot: str,
        profile_data: dict,
        dialogue_state: dict,
    ) -> str | None:
        skipped = set(dialogue_state.get("skipped_fields") or [])
        for field in PROFILE_SLOT_CONFIG[slot]["question_order"]:
            key = f"{slot}.{field}"
            if self.has_valid_value(profile_data.get(slot, {}).get(field)):
                continue
            if key in skipped:
                continue
            if self.get_question_attempt_count(dialogue_state, slot, field) >= 1:
                continue
            return field
        return None

    def find_next_incomplete_slot(
        self,
        profile_data: dict,
        dialogue_state: dict,
        start_after: str | None = None,
    ) -> str | None:
        slots = PROFILE_DIALOGUE_SLOT_ORDER
        start_index = slots.index(start_after) + 1 if start_after in slots else 0
        for slot in slots[start_index:]:
            if self.is_slot_sufficient(slot, profile_data.get(slot)):
                continue
            if self.find_next_question_field(slot, profile_data, dialogue_state):
                return slot
        return None

    def build_dialogue_action(
        self,
        current_slot: str,
        profile_data: dict,
        dialogue_state: dict | None,
        relevance_result: dict | None,
        slot_updates: dict | None,
        user_message: str,
    ) -> tuple[DialogueAction, dict]:
        state = {
            "asked_fields": dict((dialogue_state or {}).get("asked_fields") or {}),
            "skipped_fields": list((dialogue_state or {}).get("skipped_fields") or []),
            "last_question_field": (dialogue_state or {}).get("last_question_field"),
        }
        self._consume_unanswered_last_question(state, profile_data)

        current_sufficient = self.is_slot_sufficient(
            current_slot, profile_data.get(current_slot)
        )
        useful = bool(self.sanitize_slot_updates(slot_updates))
        relevant = bool((relevance_result or {}).get("is_relevant", False))

        if current_sufficient:
            target_slot = self.find_next_incomplete_slot(
                profile_data, state, start_after=current_slot
            )
            if target_slot is None:
                target_slot = self.find_next_incomplete_slot(profile_data, state)
            action_name = "advance"
        else:
            target_slot = current_slot
            action_name = "follow_up" if relevant or useful else "recover_from_irrelevant"

        if target_slot is None:
            return (
                DialogueAction(
                    action="confirm_profile",
                    current_slot=current_slot,
                    next_slot="confirm",
                    question_field=None,
                    question_text=None,
                    acknowledgement="画像信息已整理完成",
                    need_summary=False,
                    profile_completed=True,
                ),
                state,
            )

        question_field = self.find_next_question_field(target_slot, profile_data, state)
        if question_field is None:
            next_slot = self.find_next_incomplete_slot(
                profile_data, state, start_after=target_slot
            )
            if next_slot is None:
                next_slot = self.find_next_incomplete_slot(profile_data, state)
            target_slot = next_slot
            if target_slot is None:
                return (
                    DialogueAction(
                        action="confirm_profile",
                        current_slot=current_slot,
                        next_slot="confirm",
                        question_field=None,
                        question_text=None,
                        acknowledgement="画像信息已整理完成",
                        need_summary=False,
                        profile_completed=True,
                    ),
                    state,
                )
            question_field = self.find_next_question_field(target_slot, profile_data, state)
            action_name = "skip_and_advance"

        question_text = PROFILE_FIELD_QUESTIONS[f"{target_slot}.{question_field}"]
        attempt_count = self.increase_question_attempt(
            state, target_slot, question_field, question_text
        )
        acknowledgement = (
            "已记录你提供的信息"
            if useful
            else "这个话题我们稍后也可以聊"
            if action_name == "recover_from_irrelevant"
            else "知道了"
        )
        return (
            DialogueAction(
                action=action_name,
                current_slot=current_slot,
                next_slot=target_slot,
                question_field=question_field,
                question_text=question_text,
                acknowledgement=acknowledgement,
                need_summary=False,
                profile_completed=False,
                question_attempt_count=attempt_count,
            ),
            state,
        )
