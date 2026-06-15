from __future__ import annotations

import os
from typing import Any

from sqlalchemy.orm import Session

from app.models.other import SystemSetting
from app.models.user import User


MODEL_SETTING_KEY = "model_config"


def _default_model_settings() -> dict[str, Any]:
    return {
        "llm_provider": os.getenv("LLM_PROVIDER", "deepseek"),
        "model_name": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        "temperature": float(os.getenv("LLM_TEMPERATURE", "0.2")),
        "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "4096")),
        "rag_top_k": int(os.getenv("RAG_TOP_K", "5")),
        "safety_review_enabled": os.getenv("SAFETY_REVIEW_ENABLED", "true").lower() != "false",
    }


def get_model_settings(db: Session) -> dict[str, Any]:
    setting = db.query(SystemSetting).filter(SystemSetting.setting_key == MODEL_SETTING_KEY).first()
    data = _default_model_settings()
    if setting and isinstance(setting.setting_value_json, dict):
        data.update(setting.setting_value_json)
    return data


def update_model_settings(db: Session, payload: dict[str, Any], current_user: User) -> dict[str, Any]:
    setting = db.query(SystemSetting).filter(SystemSetting.setting_key == MODEL_SETTING_KEY).first()
    if setting is None:
        setting = SystemSetting(
            id="setting_model_config",
            setting_key=MODEL_SETTING_KEY,
            description="LLM and RAG model configuration",
        )
        db.add(setting)
    setting.setting_value_json = payload
    setting.updated_by = str(current_user.id)
    db.commit()
    db.refresh(setting)
    return get_model_settings(db)
