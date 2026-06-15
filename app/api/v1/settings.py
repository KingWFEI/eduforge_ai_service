from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.settings import ModelSettingsResponse, ModelSettingsUpdateRequest
from app.services.settings_service import get_model_settings, update_model_settings
from app.utils.response import ApiResponse, success

router = APIRouter(prefix="/settings", tags=["系统设置"])


@router.get("/model", response_model=ApiResponse[ModelSettingsResponse])
def model_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    return success(get_model_settings(db))


@router.put("/model", response_model=ApiResponse[ModelSettingsResponse])
def update_model_config(
    payload: ModelSettingsUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    payload_data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    data = update_model_settings(
        db=db,
        payload=payload_data,
        current_user=current_user,
    )
    return success(data)
