from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.home import HomeSummaryResponse
from app.services.home_service import get_home_summary
from app.utils.response import ApiResponse, success

router = APIRouter(prefix="/home", tags=["学生首页"])


@router.get("/summary", response_model=ApiResponse[HomeSummaryResponse])
def get_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    """
    阶段 3.1：获取学生首页摘要。

    Flutter 首页初始化时调用：
    GET /api/home/summary
    """
    data = get_home_summary(db=db, current_user=current_user)
    return success(data)
