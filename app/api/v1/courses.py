from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.constants.role import Role
from app.core.dependencies import get_current_user, require_role
from app.db.session import get_db
from app.models.course import Course
from app.models.user import User
from app.schemas.course import CourseCreate, CourseResponse, CourseUploadResponse, CourseDocumentListResponse, DeleteCourseDocumentResponse, CourseKnowledgeChunkListResponse, CourseChapterCreate, CourseChapterCreateResponse, CourseChapterListResponse, KnowledgePointCreateResponse, KnowledgePointCreate, KnowledgePointListResponse, VectorIndexRecordListResponse, LinkCourseDocumentRequest, LinkCourseDocumentResponse, ReindexDocumentResponse, CourseStructureDraftGenerateRequest, CourseStructureDraftUpdateRequest, CourseStructureDraftConfirmRequest, CourseStructureDraftResponse, CourseStructureConfirmResponse
from app.services.course_service import list_course_documents, list_course_knowledge_chunks, delete_course_document, create_course_chapter, list_course_chapters, create_knowledge_point, list_knowledge_points, list_vector_index_records, link_course_document_to_chapter_and_knowledge_point, reindex_course_document
from app.services.course_structure_service import generate_course_structure_draft, get_course_structure_draft, update_course_structure_draft, confirm_course_structure_draft
from app.services.rag_service import upload_and_index_course_document
from app.schemas.common import PageResponse
from app.utils.response import ApiResponse, AppException, ErrorCode, success

router = APIRouter(prefix="/courses", tags=["课程"])


@router.post("/", response_model=ApiResponse[CourseResponse], include_in_schema=False)
@router.post("", response_model=ApiResponse[CourseResponse])
def create_course(
    course: CourseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """创建课程（教师/管理员权限）"""
    new_course = Course(
        course_id=course.course_id,
        name=course.name,
        description=course.description,
        created_by=current_user.id,
    )

    db.add(new_course)
    db.commit()
    db.refresh(new_course)

    return success(new_course)


@router.get("/", response_model=ApiResponse[PageResponse[CourseResponse]], include_in_schema=False)
@router.get("", response_model=ApiResponse[PageResponse[CourseResponse]])
def get_courses(
    keyword: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """分页查询课程列表"""
    query = db.query(Course)
    if keyword:
        query = query.filter(Course.name.like(f"%{keyword}%"))
    if status_filter:
        query = query.filter(Course.status == status_filter)
    total = query.count()
    courses = query.offset((page - 1) * page_size).limit(page_size).all()

    return success(
        PageResponse[CourseResponse](
            items=courses,
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/{course_id}", response_model=ApiResponse[CourseResponse])
def get_course(
    course_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取课程详情"""
    course = db.query(Course).filter(Course.course_id == course_id).first()
    if course is None and course_id.isdigit():
        course = db.query(Course).filter(Course.id == int(course_id)).first()

    if course is None:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="课程不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return success(course)


@router.post("/{course_id}/upload", response_model=ApiResponse[CourseUploadResponse])
async def upload_course_file(
    course_id: str,
    file: UploadFile = File(...),
    chapter_id: str | None = Form(None),
    description: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """
    上传课程资料。
    POST /api/courses/{course_id}/upload
    当前实现会在上传后同步解析、切块并写入向量索引。
    """
    data = upload_and_index_course_document(
        db=db,
        course_id=course_id,
        file=file,
        current_user_id=str(current_user.id),
        chapter_id=chapter_id,
        description=description,
    )
    return success(data)


@router.get(
    "/{course_id}/documents",
    response_model=ApiResponse[CourseDocumentListResponse],
)
def get_course_documents(
    course_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """
    获取课程资料列表。

    Vue 知识库管理页调用：
    GET /api/courses/{course_id}/documents
    """
    data = list_course_documents(
        db=db,
        course_id=course_id,
    )
    return success(data)


@router.get(
    "/{course_id}/chunks",
    response_model=ApiResponse[CourseKnowledgeChunkListResponse],
)
def get_course_chunks(
    course_id: str,
    document_id: str | None = Query(None, description="文件ID"),
    keyword: str | None = Query(None, description="搜索关键词"),
    chapter_id: str | None = Query(None, description="章节ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """
    查看课程知识块列表。
    阶段 6 标准入口：GET /api/courses/{course_id}/chunks
    """
    data = list_course_knowledge_chunks(
        db=db,
        course_id=course_id,
        document_id=document_id,
        keyword=keyword,
        chapter_id=chapter_id,
        page=page,
        page_size=page_size,
    )
    return success(data)


@router.delete(
    "/{course_id}/documents/{document_id}",
    response_model=ApiResponse[DeleteCourseDocumentResponse],
)
def remove_course_document(
    course_id: str,
    document_id: str,
    delete_vectors: bool = Query(True, description="是否同时删除向量库索引"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """
    删除课程资料及其知识块。

    Vue 知识库管理页调用：
    DELETE /api/courses/{course_id}/documents/{document_id}
    """
    data = delete_course_document(
        db=db,
        course_id=course_id,
        document_id=document_id,
        current_user_id=current_user.id,
        current_user_role=current_user.role,
        delete_vectors=delete_vectors,
    )
    return success(data, message="课程资料删除成功")


@router.post(
    "/{course_id}/chapters",
    response_model=ApiResponse[CourseChapterCreateResponse],
)
def create_chapter(
    course_id: str,
    payload: CourseChapterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """
    新增课程章节。

    Vue 课程章节管理页调用：
    POST /api/courses/{course_id}/chapters
    """
    data = create_course_chapter(
        db=db,
        course_id=course_id,
        title=payload.title,
        sort_order=payload.sort_order,
        description=payload.description,
        parent_id=payload.parent_id,
        level=payload.level,
    )
    return success(data)


@router.post(
    "/{course_id}/structure-drafts/generate",
    response_model=ApiResponse[CourseStructureDraftResponse],
)
def generate_structure_draft(
    course_id: str,
    payload: CourseStructureDraftGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """
    AI 根据课程资料自动识别章节、小节、知识点，生成课程结构草稿。
    """
    data = generate_course_structure_draft(
        db=db,
        course_id=course_id,
        document_ids=payload.document_ids,
        created_by=str(current_user.id),
    )
    return success(data)


@router.get(
    "/{course_id}/structure-drafts/{draft_id}",
    response_model=ApiResponse[CourseStructureDraftResponse],
)
def get_structure_draft(
    course_id: str,
    draft_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """获取课程结构草稿，供 Vue 管理端展示和编辑。"""
    data = get_course_structure_draft(
        db=db,
        course_id=course_id,
        draft_id=draft_id,
    )
    return success(data)


@router.put(
    "/{course_id}/structure-drafts/{draft_id}",
    response_model=ApiResponse[CourseStructureDraftResponse],
)
def update_structure_draft(
    course_id: str,
    draft_id: str,
    payload: CourseStructureDraftUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """保存教师在 Vue 管理端编辑后的课程结构草稿。"""
    data = update_course_structure_draft(
        db=db,
        course_id=course_id,
        draft_id=draft_id,
        draft=payload.draft,
    )
    return success(data)


@router.post(
    "/{course_id}/structure-drafts/{draft_id}/confirm",
    response_model=ApiResponse[CourseStructureConfirmResponse],
)
def confirm_structure_draft(
    course_id: str,
    draft_id: str,
    payload: CourseStructureDraftConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """
    教师确认课程结构草稿后，写入正式章节/小节/知识点，并按结构重建知识块索引。
    """
    data = confirm_course_structure_draft(
        db=db,
        course_id=course_id,
        draft_id=draft_id,
        confirmed_by=str(current_user.id),
        draft=payload.draft,
        rebuild_index=payload.rebuild_index,
    )
    return success(data)


@router.get(
    "/{course_id}/chapters",
    response_model=ApiResponse[CourseChapterListResponse],
)
def get_course_chapters(
    course_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """
    获取课程章节列表。

    Vue 课程章节管理页调用：
    GET /api/courses/{course_id}/chapters
    """
    data = list_course_chapters(
        db=db,
        course_id=course_id,
    )
    return success(data)


@router.post(
    "/{course_id}/chapters/{chapter_id}/knowledge-points",
    response_model=ApiResponse[KnowledgePointCreateResponse],
)
def create_chapter_knowledge_point(
    course_id: str,
    chapter_id: str,
    payload: KnowledgePointCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """
    给课程章节新增知识点。

    Vue 课程知识点管理页调用：
    POST /api/courses/{course_id}/chapters/{chapter_id}/knowledge-points
    """
    data = create_knowledge_point(
        db=db,
        course_id=course_id,
        chapter_id=chapter_id,
        name=payload.name,
        description=payload.description,
        difficulty=payload.difficulty,
        sort_order=payload.sort_order,
    )
    return success(data)


@router.get(
    "/{course_id}/knowledge-points",
    response_model=ApiResponse[KnowledgePointListResponse],
)
def get_course_knowledge_points(
    course_id: str,
    chapter_id: str | None = Query(None, description="章节ID，可选"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """
    获取课程知识点列表。

    Vue 课程知识点管理页调用：
    GET /api/courses/{course_id}/knowledge-points

    可选：
    GET /api/courses/{course_id}/knowledge-points?chapter_id=ch_xxx
    """
    data = list_knowledge_points(
        db=db,
        course_id=course_id,
        chapter_id=chapter_id,
    )
    return success(data)


@router.get(
    "/{course_id}/index-records",
    response_model=ApiResponse[VectorIndexRecordListResponse],
)
def get_course_index_records(
    course_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """
    获取课程向量索引任务记录。

    Vue 知识库管理页调用：
    GET /api/courses/{course_id}/index-records
    """
    data = list_vector_index_records(
        db=db,
        course_id=course_id,
    )
    return success(data)


@router.patch(
    "/{course_id}/documents/{document_id}/link",
    response_model=ApiResponse[LinkCourseDocumentResponse],
)
def link_course_document(
    course_id: str,
    document_id: str,
    payload: LinkCourseDocumentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """
    将课程资料关联到章节 / 知识点。

    Vue 知识库管理页调用：
    PATCH /api/courses/{course_id}/documents/{document_id}/link
    """
    data = link_course_document_to_chapter_and_knowledge_point(
        db=db,
        course_id=course_id,
        document_id=document_id,
        chapter_id=payload.chapter_id,
        knowledge_point_id=payload.knowledge_point_id,
    )
    return success(data)


@router.post(
    "/{course_id}/documents/{document_id}/reindex",
    response_model=ApiResponse[ReindexDocumentResponse],
)
def reindex_document(
    course_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.TEACHER, Role.ADMIN)),
):
    """
    重新索引指定文档（RAG向量索引）。

    调用场景：
    - Chroma 数据丢失
    - embedding 模型升级
    - 重建知识库
    """
    record = reindex_course_document(
        db=db,
        course_id=course_id,
        document_id=document_id,
        created_by=str(current_user.id),
    )
    return success({"index_record": record})
