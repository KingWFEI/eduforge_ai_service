from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.learning_style_character import LearningStyleCharacterMatchResponse
from app.services.learning_style_character_service import get_student_learning_style_character
from app.utils.response import ApiResponse, success

router = APIRouter(prefix="/student", tags=["Student learning style"])


@router.get("/learning-style-character", response_model=ApiResponse[LearningStyleCharacterMatchResponse])
def read_my_learning_style_character(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    data = get_student_learning_style_character(db=db, student_id=str(current_user.id))
    messages = {
        "PROFILE_REQUIRED": "请先生成学习画像",
        "MATCHING": "画像风格人物正在匹配中",
        "STYLE_UNAVAILABLE": "暂无可用的画像风格人物",
        "MATCHED": "获取成功",
    }
    message = messages.get(data["status"], "获取成功")
    return success(data, message=message)
