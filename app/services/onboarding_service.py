from datetime import datetime
from typing import Optional

from fastapi import status
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.models.onboarding import OnboardingOption, OnboardingQuestion, OnboardingSurvey
from app.models.profile import OnboardingSubmission, StudentProfile
from app.models.user import User
from app.schemas.onboarding import (
    AdminOnboardingOption,
    AdminOnboardingQuestion,
    OnboardingOptionCreateRequest,
    OnboardingOptionCreateResponse,
    OnboardingOptionUpdateRequest,
    OnboardingQuestionCreateRequest,
    OnboardingQuestionCreateResponse,
    OnboardingQuestionUpdateRequest,
    OnboardingSurveyCreateRequest,
    OnboardingSurveyCreateResponse,
    OnboardingSurveyDetailResponse,
    OnboardingSurveyListItem,
    OnboardingSurveyPublishResponse,
    OnboardingSurveyResponse,
    OnboardingSurveyUpdateRequest,
    ProfileData,
    QuestionReorderRequest,
)
from app.utils.response import AppException, ErrorCode

# 需要配置选项的题目类型
CHOICE_TYPES = {"single", "multi", "scale"}

# 默认问卷数据（首次启动时填充）
DEFAULT_QUESTIONS = [
    {
        "question_id": "q_001",
        "step": 1,
        "title": "你最想学习哪个方向？",
        "subtitle": "我们会根据你的选择推荐课程和资源",
        "type": "single",
        "required": True,
        "options": [
            {
                "option_id": "opt_ai",
                "label": "人工智能基础",
                "value": "ai_basic",
                "description": "适合想入门 AI 和机器学习的同学",
                "sort_order": 1,
                "icon": "psychology",
                "color": "#7C4DFF",
                "profile_mapping": {
                    "target_course": "人工智能基础",
                    "interest_tags": ["AI", "机器学习"],
                    "resource_preference": ["document", "mind_map"],
                },
            },
            {
                "option_id": "opt_python",
                "label": "Python 程序设计",
                "value": "python",
                "description": "适合提升编程基础",
                "sort_order": 2,
                "icon": "code",
                "color": "#4D9CFF",
                "profile_mapping": {
                    "target_course": "Python 程序设计",
                    "interest_tags": ["Python", "编程基础"],
                    "resource_preference": ["code_case", "quiz"],
                },
            },
        ],
    },
    {
        "question_id": "q_002",
        "step": 2,
        "title": "你的学习目标是什么？",
        "subtitle": "可以选择多个目标",
        "type": "multi",
        "required": True,
        "options": [
            {
                "option_id": "opt_pass_exam",
                "label": "通过课程考试",
                "value": "pass_exam",
                "description": "系统会优先推荐基础知识和常考题",
                "sort_order": 1,
                "profile_mapping": {
                    "learning_goals": ["通过课程考试"],
                    "resource_preference": ["quiz", "document"],
                },
            },
            {
                "option_id": "opt_complete_lab",
                "label": "完成实验作业",
                "value": "complete_lab",
                "description": "系统会优先推荐代码案例和实验步骤",
                "sort_order": 2,
                "profile_mapping": {
                    "learning_goals": ["完成实验作业"],
                    "resource_preference": ["code_case"],
                },
            },
            {
                "option_id": "opt_competition",
                "label": "参加软件杯",
                "value": "competition",
                "description": "系统会推荐项目实践和综合任务",
                "sort_order": 3,
                "profile_mapping": {
                    "learning_goals": ["参加软件杯"],
                    "resource_preference": ["project_task"],
                },
            },
        ],
    },
    {
        "question_id": "q_003",
        "step": 3,
        "title": "你当前基础如何？",
        "subtitle": "请选择你对不同能力的掌握程度",
        "type": "skill_matrix",
        "required": True,
        "matrix_items": [
            {"key": "python", "label": "Python 基础", "levels": ["较弱", "一般", "较好"]},
            {"key": "math", "label": "数学基础", "levels": ["较弱", "一般", "较好"]},
            {"key": "course", "label": "课程理解", "levels": ["较弱", "一般", "较好"]},
        ],
    },
]


def seed_default_survey(db: Session) -> None:
    """如果数据库中没有问卷，插入默认问卷数据"""
    if db.query(OnboardingSurvey).first():
        return

    survey = OnboardingSurvey(
        survey_id="survey_001",
        title="学生首次兴趣问卷",
        description="用于学生首次进入 App 时构建初始学习画像",
        version=2,
        status="published",
        target_role=Role.STUDENT.value,
        target_course_id="course_ai_basic",
        submit_count=128,
        created_by="teacher001",
    )
    db.add(survey)
    db.flush()

    for question_data in DEFAULT_QUESTIONS:
        question = OnboardingQuestion(
            question_id=question_data["question_id"],
            survey_id=survey.survey_id,
            step=question_data["step"],
            title=question_data["title"],
            subtitle=question_data.get("subtitle", ""),
            type=question_data["type"],
            required=question_data.get("required", True),
            matrix_items=question_data.get("matrix_items", []),
        )
        db.add(question)
        db.flush()

        for option_data in question_data.get("options", []):
            db.add(
                OnboardingOption(
                    option_id=option_data["option_id"],
                    question_id=question.question_id,
                    label=option_data["label"],
                    value=option_data["value"],
                    description=option_data.get("description", ""),
                    sort_order=option_data.get("sort_order", 0),
                    icon=option_data.get("icon"),
                    color=option_data.get("color"),
                    profile_mapping=option_data.get("profile_mapping", {}),
                )
            )

    db.commit()


# ─── 工具函数 ─────────────────────────────────────────

def next_code(db: Session, model, field_name: str, prefix: str) -> str:
    """生成自增编码（如 survey_003），避免主键冲突"""
    max_id = db.query(model.id).order_by(model.id.desc()).first()
    next_id = (max_id[0] if max_id else 0) + 1
    value = f"{prefix}_{next_id:03d}"

    while db.query(model).filter(getattr(model, field_name) == value).first():
        next_id += 1
        value = f"{prefix}_{next_id:03d}"

    return value


def get_survey_or_404(db: Session, survey_id: str) -> OnboardingSurvey:
    """按 survey_id 查找问卷，不存在则抛出 404"""
    survey = db.query(OnboardingSurvey).filter(OnboardingSurvey.survey_id == survey_id).first()
    if survey is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="问卷不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return survey


def get_question_or_404(db: Session, question_id: str) -> OnboardingQuestion:
    """按 question_id 查找题目，不存在则抛出 404"""
    question = (
        db.query(OnboardingQuestion)
        .filter(
            OnboardingQuestion.question_id == question_id,
            OnboardingQuestion.is_deleted.is_(False),
        )
        .first()
    )
    if question is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="问题不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return question


def get_option_or_404(db: Session, option_id: str) -> OnboardingOption:
    """按 option_id 查找选项，不存在则抛出 404"""
    option = (
        db.query(OnboardingOption)
        .filter(
            OnboardingOption.option_id == option_id,
            OnboardingOption.is_deleted.is_(False),
        )
        .first()
    )
    if option is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="选项不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return option


# ─── 数据转换 ─────────────────────────────────────────

def option_to_admin_response(option: OnboardingOption) -> AdminOnboardingOption:
    """将选项 ORM 转换为管理端响应"""
    return AdminOnboardingOption(
        option_id=option.option_id,
        label=option.label,
        value=option.value,
        description=option.description or "",
        sort_order=option.sort_order,
        icon=option.icon,
        color=option.color,
        profile_mapping=option.profile_mapping or {},
    )


def question_to_admin_response(db: Session, question: OnboardingQuestion) -> AdminOnboardingQuestion:
    """将题目 ORM 转换为管理端响应（含选项列表）"""
    options = (
        db.query(OnboardingOption)
        .filter(
            OnboardingOption.question_id == question.question_id,
            OnboardingOption.is_deleted.is_(False),
        )
        .order_by(OnboardingOption.sort_order.asc(), OnboardingOption.id.asc())
        .all()
    )
    return AdminOnboardingQuestion(
        question_id=question.question_id,
        step=question.step,
        title=question.title,
        subtitle=question.subtitle or "",
        type=question.type,
        required=question.required,
        options=[option_to_admin_response(option) for option in options],
        matrix_items=question.matrix_items or [],
    )


# ─── 问卷 CRUD ────────────────────────────────────────

def list_surveys(
    db: Session,
    status_value: Optional[str],
    keyword: Optional[str],
    page: int,
    page_size: int,
) -> tuple[list[OnboardingSurveyListItem], int]:
    """分页查询问卷列表，支持按状态和关键词过滤"""
    seed_default_survey(db)

    query = db.query(OnboardingSurvey)
    if status_value:
        query = query.filter(OnboardingSurvey.status == status_value)
    if keyword:
        query = query.filter(OnboardingSurvey.title.contains(keyword))

    total = query.count()
    surveys = (
        query.order_by(OnboardingSurvey.updated_at.desc(), OnboardingSurvey.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for survey in surveys:
        question_count = (
            db.query(OnboardingQuestion)
            .filter(
                OnboardingQuestion.survey_id == survey.survey_id,
                OnboardingQuestion.is_deleted.is_(False),
            )
            .count()
        )
        items.append(
            OnboardingSurveyListItem(
                survey_id=survey.survey_id,
                title=survey.title,
                description=survey.description or "",
                version=survey.version,
                status=survey.status,
                question_count=question_count,
                submit_count=survey.submit_count,
                created_by=survey.created_by,
                created_at=survey.created_at,
                updated_at=survey.updated_at,
            )
        )

    return items, total


def create_survey(
    db: Session,
    payload: OnboardingSurveyCreateRequest,
    created_by: str,
) -> OnboardingSurveyCreateResponse:
    """创建新问卷"""
    seed_default_survey(db)
    survey_id = next_code(db, OnboardingSurvey, "survey_id", "survey")
    survey = OnboardingSurvey(
        survey_id=survey_id,
        title=payload.title,
        description=payload.description,
        version=1,
        status="draft",
        target_role=payload.target_role.value,
        target_course_id=payload.target_course_id,
        submit_count=0,
        created_by=created_by,
    )
    db.add(survey)
    db.commit()
    db.refresh(survey)

    return OnboardingSurveyCreateResponse(
        survey_id=survey.survey_id,
        title=survey.title,
        status="draft",
    )


def get_survey_detail(db: Session, survey_id: str) -> OnboardingSurveyDetailResponse:
    """获取问卷详情（含所有题目和选项）"""
    seed_default_survey(db)
    survey = get_survey_or_404(db, survey_id)
    questions = (
        db.query(OnboardingQuestion)
        .filter(
            OnboardingQuestion.survey_id == survey.survey_id,
            OnboardingQuestion.is_deleted.is_(False),
        )
        .order_by(OnboardingQuestion.step.asc(), OnboardingQuestion.id.asc())
        .all()
    )

    return OnboardingSurveyDetailResponse(
        survey_id=survey.survey_id,
        title=survey.title,
        description=survey.description or "",
        version=survey.version,
        status=survey.status,
        target_role=survey.target_role,
        target_course_id=survey.target_course_id,
        questions=[question_to_admin_response(db, question) for question in questions],
    )


def update_survey(
    db: Session,
    survey_id: str,
    payload: OnboardingSurveyUpdateRequest,
) -> None:
    """更新问卷基本信息"""
    survey = get_survey_or_404(db, survey_id)
    update_data = payload.model_dump(exclude_unset=True)
    if "target_role" in update_data and update_data["target_role"] is not None:
        update_data["target_role"] = update_data["target_role"].value

    for key, value in update_data.items():
        setattr(survey, key, value)

    db.commit()


def archive_survey(db: Session, survey_id: str, current_username: str, current_role: str) -> None:
    """归档问卷（仅管理员或创建者可操作）"""
    survey = get_survey_or_404(db, survey_id)
    if current_role != Role.ADMIN.value and survey.created_by != current_username:
        raise AppException(
            code=ErrorCode.FORBIDDEN,
            message="当前角色没有权限",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    survey.status = "archived"
    db.commit()


def validate_survey_for_publish(db: Session, survey: OnboardingSurvey) -> None:
    """发布前校验：问卷至少有一道题，且各题配置完整"""
    questions = (
        db.query(OnboardingQuestion)
        .filter(
            OnboardingQuestion.survey_id == survey.survey_id,
            OnboardingQuestion.is_deleted.is_(False),
        )
        .order_by(OnboardingQuestion.step.asc())
        .all()
    )
    if not questions:
        raise AppException(
            code=ErrorCode.CONFLICT,
            message="问卷至少需要一道问题",
            status_code=status.HTTP_409_CONFLICT,
        )

    for question in questions:
        if not question.title or not question.type:
            raise AppException(
                code=ErrorCode.PARAM_ERROR,
                message="必填问题配置不完整",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if question.type in CHOICE_TYPES:
            option_count = (
                db.query(OnboardingOption)
                .filter(
                    OnboardingOption.question_id == question.question_id,
                    OnboardingOption.is_deleted.is_(False),
                )
                .count()
            )
            if option_count == 0:
                raise AppException(
                    code=ErrorCode.PARAM_ERROR,
                    message="单选、多选或量表题必须配置选项",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
        if question.type == "skill_matrix" and not question.matrix_items:
            raise AppException(
                code=ErrorCode.PARAM_ERROR,
                message="技能矩阵题必须配置矩阵项",
                status_code=status.HTTP_400_BAD_REQUEST,
            )


def publish_survey(
    db: Session,
    survey_id: str,
) -> OnboardingSurveyPublishResponse:
    """发布问卷，同一 target_role 下只能有一份已发布的问卷"""
    survey = get_survey_or_404(db, survey_id)

    if survey.status == "archived":
        raise AppException(
            code=ErrorCode.CONFLICT,
            message="已归档问卷无法发布，请先复制一份再发布",
            status_code=status.HTTP_409_CONFLICT,
        )

    validate_survey_for_publish(db, survey)

    # 将同一角色下其他已发布的问卷取消发布（设回草稿）
    (
        db.query(OnboardingSurvey)
        .filter(
            OnboardingSurvey.target_role == survey.target_role,
            OnboardingSurvey.survey_id != survey.survey_id,
            OnboardingSurvey.status == "published",
        )
        .update({"status": "draft"})
    )

    if survey.status == "published":
        db.commit()
        return OnboardingSurveyPublishResponse(
            survey_id=survey.survey_id,
            status="published",
            version=survey.version,
        )

    survey.status = "published"
    survey.version += 1
    db.commit()
    db.refresh(survey)

    return OnboardingSurveyPublishResponse(
        survey_id=survey.survey_id,
        status="published",
        version=survey.version,
    )


def duplicate_survey(db: Session, survey_id: str, created_by: str) -> OnboardingSurveyCreateResponse:
    """复制问卷（含所有题目和选项）"""
    source = get_survey_or_404(db, survey_id)
    new_survey_id = next_code(db, OnboardingSurvey, "survey_id", "survey")
    new_survey = OnboardingSurvey(
        survey_id=new_survey_id,
        title=f"{source.title} - 副本",
        description=source.description,
        version=1,
        status="draft",
        target_role=source.target_role,
        target_course_id=source.target_course_id,
        submit_count=0,
        created_by=created_by,
    )
    db.add(new_survey)
    db.flush()

    questions = (
        db.query(OnboardingQuestion)
        .filter(
            OnboardingQuestion.survey_id == source.survey_id,
            OnboardingQuestion.is_deleted.is_(False),
        )
        .order_by(OnboardingQuestion.step.asc(), OnboardingQuestion.id.asc())
        .all()
    )
    for question in questions:
        new_question_id = next_code(db, OnboardingQuestion, "question_id", "q")
        db.add(
            OnboardingQuestion(
                question_id=new_question_id,
                survey_id=new_survey.survey_id,
                step=question.step,
                title=question.title,
                subtitle=question.subtitle,
                type=question.type,
                required=question.required,
                matrix_items=question.matrix_items,
            )
        )
        db.flush()
        options = (
            db.query(OnboardingOption)
            .filter(
                OnboardingOption.question_id == question.question_id,
                OnboardingOption.is_deleted.is_(False),
            )
            .order_by(OnboardingOption.sort_order.asc(), OnboardingOption.id.asc())
            .all()
        )
        for option in options:
            db.add(
                OnboardingOption(
                    option_id=next_code(db, OnboardingOption, "option_id", "opt"),
                    question_id=new_question_id,
                    label=option.label,
                    value=option.value,
                    description=option.description,
                    sort_order=option.sort_order,
                    icon=option.icon,
                    color=option.color,
                    profile_mapping=option.profile_mapping,
                )
            )
            db.flush()

    db.commit()
    return OnboardingSurveyCreateResponse(
        survey_id=new_survey.survey_id,
        title=new_survey.title,
        status="draft",
    )


# ─── 题目 CRUD ────────────────────────────────────────

def create_question(
    db: Session,
    survey_id: str,
    payload: OnboardingQuestionCreateRequest,
) -> OnboardingQuestionCreateResponse:
    """在问卷中创建新题目"""
    get_survey_or_404(db, survey_id)
    if payload.type in CHOICE_TYPES and not payload.options:
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message="单选、多选或量表题必须配置选项",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if payload.type == "skill_matrix" and not payload.matrix_items:
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message="技能矩阵题必须配置矩阵项",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    question_id = next_code(db, OnboardingQuestion, "question_id", "q")
    question = OnboardingQuestion(
        question_id=question_id,
        survey_id=survey_id,
        step=payload.step,
        title=payload.title,
        subtitle=payload.subtitle,
        type=payload.type,
        required=payload.required,
        matrix_items=[item.model_dump() for item in payload.matrix_items],
    )
    db.add(question)
    db.flush()

    for option_payload in payload.options:
        create_option_model(db, question_id, option_payload)

    db.commit()
    return OnboardingQuestionCreateResponse(question_id=question_id)


def update_question(
    db: Session,
    question_id: str,
    payload: OnboardingQuestionUpdateRequest,
) -> None:
    """更新题目信息"""
    question = get_question_or_404(db, question_id)
    update_data = payload.model_dump(exclude_unset=True)
    if "matrix_items" in update_data and update_data["matrix_items"] is not None:
        update_data["matrix_items"] = [
            item.model_dump() if hasattr(item, "model_dump") else item
            for item in payload.matrix_items
        ]
    for key, value in update_data.items():
        setattr(question, key, value)
    db.commit()


def delete_question(db: Session, question_id: str) -> None:
    """软删除题目及其所有选项"""
    question = get_question_or_404(db, question_id)
    question.is_deleted = True
    (
        db.query(OnboardingOption)
        .filter(OnboardingOption.question_id == question.question_id)
        .update({"is_deleted": True})
    )
    db.commit()


def reorder_questions(db: Session, survey_id: str, payload: QuestionReorderRequest) -> None:
    """批量调整题目顺序"""
    get_survey_or_404(db, survey_id)
    question_ids = [item.question_id for item in payload.question_orders]
    questions = (
        db.query(OnboardingQuestion)
        .filter(
            OnboardingQuestion.survey_id == survey_id,
            OnboardingQuestion.question_id.in_(question_ids),
            OnboardingQuestion.is_deleted.is_(False),
        )
        .all()
    )
    question_map = {question.question_id: question for question in questions}
    if len(question_map) != len(question_ids):
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message="问题顺序参数错误",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    for item in payload.question_orders:
        question_map[item.question_id].step = item.step
    db.commit()


# ─── 选项 CRUD ────────────────────────────────────────

def create_option_model(
    db: Session,
    question_id: str,
    payload: OnboardingOptionCreateRequest,
) -> OnboardingOption:
    """内部：创建选项 ORM 对象（不提交事务）"""
    option = OnboardingOption(
        option_id=next_code(db, OnboardingOption, "option_id", "opt"),
        question_id=question_id,
        label=payload.label,
        value=payload.value,
        description=payload.description,
        sort_order=payload.sort_order,
        icon=payload.icon,
        color=payload.color,
        profile_mapping=payload.profile_mapping,
    )
    db.add(option)
    db.flush()
    return option


def create_option(
    db: Session,
    question_id: str,
    payload: OnboardingOptionCreateRequest,
) -> OnboardingOptionCreateResponse:
    """为题目创建新选项"""
    question = get_question_or_404(db, question_id)
    if question.type == "skill_matrix":
        raise AppException(
            code=ErrorCode.PARAM_ERROR,
            message="技能矩阵题不能新增选项",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    option = create_option_model(db, question_id, payload)
    db.commit()
    db.refresh(option)
    return OnboardingOptionCreateResponse(option_id=option.option_id)


def update_option(
    db: Session,
    option_id: str,
    payload: OnboardingOptionUpdateRequest,
) -> None:
    """更新选项信息"""
    option = get_option_or_404(db, option_id)
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(option, key, value)
    db.commit()


def delete_option(db: Session, option_id: str) -> None:
    """软删除选项"""
    option = get_option_or_404(db, option_id)
    option.is_deleted = True
    db.commit()


# ─── 学生端问卷获取 ──────────────────────────────────

def get_default_published_student_survey(db: Session) -> Optional[OnboardingSurveyResponse]:
    """获取面向学生的已发布问卷"""
    seed_default_survey(db)
    survey = (
        db.query(OnboardingSurvey)
        .filter(
            OnboardingSurvey.status == "published",
            OnboardingSurvey.target_role == Role.STUDENT.value,
        )
        .order_by(OnboardingSurvey.updated_at.desc(), OnboardingSurvey.id.desc())
        .first()
    )
    if survey is None:
        return None

    questions = (
        db.query(OnboardingQuestion)
        .filter(
            OnboardingQuestion.survey_id == survey.survey_id,
            OnboardingQuestion.is_deleted.is_(False),
        )
        .order_by(OnboardingQuestion.step.asc(), OnboardingQuestion.id.asc())
        .all()
    )
    admin_questions = [question_to_admin_response(db, question) for question in questions]

    return OnboardingSurveyResponse(
        survey_id=survey.survey_id,
        title=survey.title,
        description=survey.description or "",
        version=survey.version,
        questions=[
            {
                "id": question.question_id,
                "step": question.step,
                "title": question.title,
                "subtitle": question.subtitle,
                "type": question.type,
                "required": question.required,
                "options": [
                    {
                        "value": option.value,
                        "label": option.label,
                        "description": option.description or "",
                        "icon": option.icon,
                        "color": option.color,
                    }
                    for option in question.options
                ],
                "matrix_items": question.matrix_items,
            }
            for question in admin_questions
        ],
    )


# ─── 资源偏好 → 学习偏好中文映射 ────────────────────

_RESOURCE_PREFERENCE_MAP = {
    "document": "文档阅读",
    "mind_map": "图解讲解",
    "code_case": "代码实操",
    "quiz": "习题练习",
    "project_task": "项目实践",
    "video": "视频学习",
    "case": "生活案例",
}

_SKILL_LEVEL_MAP: dict[str, dict[str, str]] = {
    "python": {"weak": "较弱", "normal": "一般", "good": "较好", "beginner": "入门"},
    "math": {"weak": "较弱", "normal": "一般", "good": "较好", "beginner": "入门"},
    "course": {"weak": "较弱", "normal": "一般", "good": "较好", "beginner": "入门"},
}

_STYLE_MAP = {
    "图解讲解": "图解型学习者",
    "生活案例": "案例驱动型",
    "代码实操": "实践操作型",
    "习题练习": "巩固练习型",
    "项目实践": "项目驱动型",
}


# ─── 问卷提交与画像生成 ──────────────────────────────

def _merge_profile_mapping(
    profile: dict,
    mapping: dict,
    resource_prefs: set,
) -> None:
    """将选项的 profile_mapping 合并到画像字典中"""
    if mapping.get("target_course"):
        profile["target_course"] = mapping["target_course"]

    for goal in mapping.get("learning_goals", []):
        if goal not in profile["learning_goals"]:
            profile["learning_goals"].append(goal)

    resource_prefs.update(mapping.get("resource_preference", []))


def _build_profile_from_answers(
    db: Session,
    survey_id: str,
    answers: dict,
    student: User,
) -> dict:
    """根据问卷答案聚合选项的 profile_mapping，生成画像字典"""
    profile: dict = {
        "name": student.nickname or student.username,
        "major": "",
        "grade": "",
        "target_course": "",
        "learning_goals": [],
        "coding_level": "",
        "math_level": "",
        "course_level": "",
        "learning_preferences": [],
        "weaknesses": [],
        "cognitive_style": [],
        "time_budget": "",
        "summary": "",
        "confidence": 0.70,
    }
    resource_prefs: set[str] = set()

    for question_id, answer_value in answers.items():
        question = (
            db.query(OnboardingQuestion)
            .filter(
                OnboardingQuestion.question_id == question_id,
                OnboardingQuestion.survey_id == survey_id,
                OnboardingQuestion.is_deleted.is_(False),
            )
            .first()
        )
        if not question:
            continue

        if question.type == "single" and isinstance(answer_value, str):
            option = (
                db.query(OnboardingOption)
                .filter(
                    OnboardingOption.question_id == question_id,
                    OnboardingOption.value == answer_value,
                    OnboardingOption.is_deleted.is_(False),
                )
                .first()
            )
            if option and option.profile_mapping:
                _merge_profile_mapping(profile, option.profile_mapping, resource_prefs)

        elif question.type == "multi" and isinstance(answer_value, list):
            options = (
                db.query(OnboardingOption)
                .filter(
                    OnboardingOption.question_id == question_id,
                    OnboardingOption.value.in_(answer_value),
                    OnboardingOption.is_deleted.is_(False),
                )
                .all()
            )
            for option in options:
                if option.profile_mapping:
                    _merge_profile_mapping(profile, option.profile_mapping, resource_prefs)

        elif question.type == "skill_matrix" and isinstance(answer_value, dict):
            for key, level in answer_value.items():
                level_map = _SKILL_LEVEL_MAP.get(key, {})
                display = level_map.get(str(level), str(level))
                if key == "python":
                    profile["coding_level"] = display
                elif key == "math":
                    profile["math_level"] = display
                elif key == "course":
                    profile["course_level"] = display

    # resource_preference → learning_preferences 中文映射
    seen: set[str] = set()
    for r in resource_prefs:
        cn = _RESOURCE_PREFERENCE_MAP.get(r, r)
        if cn not in seen:
            profile["learning_preferences"].append(cn)
            seen.add(cn)

    # 根据 learning_preferences 推导 cognitive_style
    styles: set[str] = set()
    for pref in profile["learning_preferences"]:
        if pref in _STYLE_MAP:
            styles.add(_STYLE_MAP[pref])
    profile["cognitive_style"] = sorted(styles)

    # 生成默认 summary（不调用智能体）
    profile["summary"] = _generate_default_summary(profile)

    return profile


def _generate_default_summary(profile: dict) -> str:
    """在不调用画像智能体的情况下生成基础总结"""
    parts = []
    if profile.get("target_course"):
        parts.append(f"你对「{profile['target_course']}」方向感兴趣")
    if profile.get("learning_goals"):
        goals = "、".join(profile["learning_goals"])
        parts.append(f"学习目标包括{goals}")
    if profile.get("learning_preferences"):
        prefs = "、".join(profile["learning_preferences"][:3])
        parts.append(f"偏好{prefs}等学习方式")
    if parts:
        return "，".join(parts) + "。系统将持续根据你的学习行为优化画像。"
    return "请完成问卷以获得个性化学习推荐。"


def submit_survey(
    db: Session,
    survey_id: str,
    answers: dict,
    student: User,
) -> tuple[OnboardingSubmission, StudentProfile, ProfileData]:
    """提交问卷答案，生成／更新学生学习画像"""
    survey = get_survey_or_404(db, survey_id)
    if survey.status != "published":
        raise AppException(
            code=ErrorCode.CONFLICT,
            message="当前问卷未发布，无法提交",
            status_code=status.HTTP_409_CONFLICT,
        )

    # 1. 保存提交记录
    submission_id = next_code(db, OnboardingSubmission, "submission_id", "sub")
    submission = OnboardingSubmission(
        submission_id=submission_id,
        survey_id=survey_id,
        student_id=student.username,
        answers=answers,
    )
    db.add(submission)
    db.flush()

    # 2. 从答案生成画像数据
    raw = _build_profile_from_answers(db, survey_id, answers, student)

    # 3. 创建或更新学生画像
    profile = db.query(StudentProfile).filter(StudentProfile.student_id == student.username).first()
    if profile:
        for key, value in raw.items():
            setattr(profile, key, value)
        profile.last_updated = datetime.now()
    else:
        raw["profile_id"] = next_code(db, StudentProfile, "profile_id", "profile")
        raw["student_id"] = student.username
        profile = StudentProfile(**raw)
        db.add(profile)

    db.commit()
    db.refresh(profile)

    # 4. 递增问卷提交计数
    survey.submit_count = OnboardingSurvey.submit_count + 1
    db.commit()

    return submission, profile, ProfileData(
        profile_id=profile.profile_id,
        student_id=profile.student_id,
        name=profile.name,
        major=profile.major or "",
        grade=profile.grade or "",
        target_course=profile.target_course or "",
        learning_goals=profile.learning_goals or [],
        coding_level=profile.coding_level or "",
        math_level=profile.math_level or "",
        course_level=profile.course_level or "",
        learning_preferences=profile.learning_preferences or [],
        weaknesses=profile.weaknesses or [],
        cognitive_style=profile.cognitive_style or [],
        time_budget=profile.time_budget or "",
        summary=profile.summary or "",
        confidence=profile.confidence or 0.0,
        last_updated=profile.last_updated,
    )
