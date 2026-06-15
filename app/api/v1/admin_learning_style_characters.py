from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import PageResponse
from app.schemas.learning_style_character import (
    LearningStyleCharacterCreateResponse,
    LearningStyleCharacterResponse,
    LearningStyleCharacterStatusUpdate,
    LearningStyleCharacterUpdate,
)
from app.services.learning_style_character_service import (
    create_character,
    disable_character,
    get_character_detail,
    list_characters,
    parse_json_array,
    update_character,
    update_character_image,
    update_character_status,
)
from app.utils.response import ApiResponse, success

router = APIRouter(prefix="/admin/learning-style-characters", tags=["Learning style characters"])


@router.post("", response_model=ApiResponse[LearningStyleCharacterCreateResponse])
def create_learning_style_character(
    name: str = Form(...),
    code: str = Form(...),
    image: UploadFile = File(...),
    description: str | None = Form(None),
    style_prompt: str | None = Form(None),
    feature_tags: str | None = Form(None),
    suitable_methods: str | None = Form(None),
    priority: int = Form(0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    data = create_character(
        db=db,
        name=name,
        code=code,
        image=image,
        description=description,
        style_prompt=style_prompt,
        feature_tags=parse_json_array(feature_tags, "feature_tags"),
        suitable_methods=parse_json_array(suitable_methods, "suitable_methods"),
        priority=priority,
        created_by=str(current_user.id),
    )
    return success(data, message="创建成功")


@router.get("", response_model=ApiResponse[PageResponse[LearningStyleCharacterResponse]])
def get_learning_style_characters(
    status: Literal["DRAFT", "PUBLISHED", "DISABLED"] | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    items, total = list_characters(db=db, status_value=status, page=page, page_size=page_size)
    return success(PageResponse[LearningStyleCharacterResponse](items=items, total=total, page=page, page_size=page_size))


@router.get("/{character_id}", response_model=ApiResponse[LearningStyleCharacterResponse])
def get_learning_style_character_detail(
    character_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    return success(get_character_detail(db=db, character_id=character_id))


@router.put("/{character_id}", response_model=ApiResponse[LearningStyleCharacterResponse])
def update_learning_style_character(
    character_id: str,
    payload: LearningStyleCharacterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    return success(update_character(db=db, character_id=character_id, payload=payload), message="更新成功")


@router.put("/{character_id}/image", response_model=ApiResponse[LearningStyleCharacterResponse])
def replace_learning_style_character_image(
    character_id: str,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    return success(update_character_image(db=db, character_id=character_id, image=image), message="图片更新成功")


@router.patch("/{character_id}/status", response_model=ApiResponse[LearningStyleCharacterResponse])
def patch_learning_style_character_status(
    character_id: str,
    payload: LearningStyleCharacterStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    return success(
        update_character_status(db=db, character_id=character_id, status_value=payload.status),
        message="状态更新成功",
    )


@router.delete("/{character_id}", response_model=ApiResponse[bool])
def delete_learning_style_character(
    character_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    return success(disable_character(db=db, character_id=character_id), message="人物已停用")
