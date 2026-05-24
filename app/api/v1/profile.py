from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.profile import StudentProfileMeResponse
from app.services.profile_service import get_my_profile, init_my_learning_data
from app.utils.response import ApiResponse, success

router = APIRouter(prefix="/profile", tags=["学生画像"])


@router.get("/me", response_model=ApiResponse[StudentProfileMeResponse])
def read_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    """
    获取当前登录学生的学习画像。

    Flutter 个人中心、画像页、资源生成页、AI 辅导页都可以调用：
    GET /api/profile/me
    """
    data = get_my_profile(db=db, current_user=current_user)
    return success(data)

@router.post("/init-learning-data")
def init_learning_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    """
    根据当前学生画像，补生成学习路径、学习任务和推荐资源。

    测试阶段使用：
    POST /api/profile/init-learning-data
    """
    data = init_my_learning_data(db=db, current_user=current_user)
    return success(data)