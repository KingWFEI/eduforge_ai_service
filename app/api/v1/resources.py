from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.resource import RecommendedResourcesResponse, ResourceDetailResponse, ResourceFeedbackCreate, ResourceFeedbackResponse, ResourceViewResponse
from app.services.resource_service import get_recommended_resources, get_resource_detail, submit_resource_feedback, record_resource_view
from app.utils.response import ApiResponse, success

router = APIRouter(prefix="/resources", tags=["学习资源"])


@router.get("/recommend", response_model=ApiResponse[RecommendedResourcesResponse])
def recommend_resources(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    """
    阶段 3.3：获取当前学生推荐资源列表。

    Flutter 首页推荐资源区域调用：
    GET /api/resources/recommend
    """
    data = get_recommended_resources(db=db, current_user=current_user)
    return success(data)

@router.get("/{resource_id}", response_model=ApiResponse[ResourceDetailResponse])
def resource_detail(
    resource_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    """
    阶段 3.4：获取学习资源详情。

    Flutter 点击推荐资源卡片后调用：
    GET /api/resources/{resource_id}
    """
    data = get_resource_detail(
        db=db,
        current_user=current_user,
        resource_id=resource_id,
    )
    return success(data)

@router.post("/{resource_id}/feedback", response_model=ApiResponse[ResourceFeedbackResponse])
def create_resource_feedback(
    resource_id: str,
    payload: ResourceFeedbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    """
    阶段 3.5：提交学习资源反馈。

    Flutter 资源详情页点击喜欢、收藏、难度反馈时调用：
    POST /api/resources/{resource_id}/feedback
    """
    data = submit_resource_feedback(
        db=db,
        current_user=current_user,
        resource_id=resource_id,
        feedback_data=payload,
    )
    return success(data)

@router.post("/{resource_id}/view", response_model=ApiResponse[ResourceViewResponse])
def view_resource(
    resource_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.STUDENT)),
):
    """
    记录学生查看学习资源行为。

    Flutter 进入资源详情页时调用：
    POST /api/resources/{resource_id}/view
    """
    data = record_resource_view(
        db=db,
        current_user=current_user,
        resource_id=resource_id,
    )
    return success(data)