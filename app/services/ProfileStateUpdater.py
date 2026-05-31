from app.constants.profile_dialogue import PROFILE_DIALOGUE_SLOT_ORDER


class ProfileStateUpdater:
    """画像对话状态更新器"""

    def merge_fields(self, old_fields: dict, new_fields: dict) -> dict:
        merged = dict(old_fields or {})

        for key, value in (new_fields or {}).items():
            if value is None:
                continue
            if isinstance(value, list):
                old_list = merged.get(key, [])
                if not isinstance(old_list, list):
                    old_list = []
                merged[key] = list(dict.fromkeys(old_list + value))
            else:
                merged[key] = value

        return merged

    def get_next_slot(self, current_slot: str) -> str | None:
        if current_slot not in PROFILE_DIALOGUE_SLOT_ORDER:
            return None

        index = PROFILE_DIALOGUE_SLOT_ORDER.index(current_slot)

        if index + 1 >= len(PROFILE_DIALOGUE_SLOT_ORDER):
            return None

        return PROFILE_DIALOGUE_SLOT_ORDER[index + 1]

    def calculate_progress(self, collected_slots: list[str]) -> float:
        total = len(PROFILE_DIALOGUE_SLOT_ORDER)
        return round(len(collected_slots) / total, 2)

    def calculate_missing_slots(self, collected_slots: list[str]) -> list[str]:
        return [
            slot for slot in PROFILE_DIALOGUE_SLOT_ORDER
            if slot not in collected_slots
        ]