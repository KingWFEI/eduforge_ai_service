from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


TAG_TRANSLATIONS = {
    "��֤": "认证",
    "�û�": "用户",
    "�γ�": "课程",
    "�γ̽ṹ�ݸ�": "课程结构草稿",
    "�׶�3-��ҳ�γ�": "首页课程",
    "ѧ���������ʾ�": "学生画像问卷",
    "�������ʾ�����": "管理端问卷配置",
    "Learning style characters": "管理端学习风格角色",
    "�������û�����": "管理端用户管理",
    "ѧ������": "学生画像",
    "ѧϰ·��": "学习路径",
    "��ϰ": "练习",
    "ѧϰ����": "学习评估",
    "ѧϰ��Դ": "学习资源",
    "������������": "智能体任务",
    "���������ݿ���": "管理端数据看板",
    "������ѧ������": "管理端学生管理",
    "ϵͳ����": "系统设置",
    "Student learning style": "学生学习风格",
    "Profile Dialogue": "画像对话",
    "RAG֪ʶ��": "知识库问答",
    "管理端用户管理": "管理端用户管理",
    "课程": "课程",
}


SUMMARY_TRANSLATIONS = {
    ("GET", "/"): "服务根路径",
    ("GET", "/api/health"): "服务健康检查",
    ("POST", "/api/auth/register-code"): "发送注册验证码",
    ("POST", "/api/auth/register"): "用户注册",
    ("POST", "/api/auth/login"): "账号密码登录",
    ("POST", "/api/auth/login-code"): "发送登录验证码",
    ("POST", "/api/auth/login/phone"): "手机号验证码登录",
    ("GET", "/api/auth/me"): "获取当前登录用户",
    ("POST", "/api/auth/logout"): "退出登录",
    ("POST", "/api/users/"): "创建用户",
    ("GET", "/api/users/"): "获取用户列表",
    ("GET", "/api/users/me"): "获取当前用户信息",
    ("PATCH", "/api/users/{user_id}/role"): "更新用户角色",
    ("GET", "/api/courses/{course_id}/syllabus"): "获取课程大纲和学习进度",
    ("GET", "/api/courses/{course_id}/overview"): "获取课程概览",
    ("GET", "/api/courses/{course_id}/resources/my"): "获取我在该课程下的资源",
    ("POST", "/api/courses"): "创建课程",
    ("GET", "/api/courses"): "获取课程列表",
    ("GET", "/api/courses/{course_id}"): "获取课程详情",
    ("DELETE", "/api/courses/{course_id}"): "删除或归档课程",
    ("POST", "/api/courses/{course_id}/upload"): "上传课程资料",
    ("GET", "/api/courses/{course_id}/documents"): "获取课程资料列表",
    ("GET", "/api/courses/{course_id}/documents/{document_id}/assets"): "获取课程资料图片",
    ("GET", "/api/courses/{course_id}/chunks"): "获取课程知识块列表",
    ("DELETE", "/api/courses/{course_id}/documents/{document_id}"): "删除课程资料",
    ("POST", "/api/courses/{course_id}/chapters"): "创建课程章节",
    ("GET", "/api/courses/{course_id}/chapters"): "获取课程章节列表",
    ("POST", "/api/courses/{course_id}/structure-drafts/generate"): "生成课程结构草稿",
    ("GET", "/api/courses/{course_id}/structure-drafts/{draft_id}"): "获取课程结构草稿",
    ("PUT", "/api/courses/{course_id}/structure-drafts/{draft_id}"): "更新课程结构草稿",
    ("GET", "/api/courses/{course_id}/chapters/{chapter_id}/content"): "获取章节正文内容",
    ("GET", "/api/courses/{course_id}/sections/{section_id}/recommendations"): "获取小节资源推荐",
    ("POST", "/api/courses/{course_id}/sections/{section_id}/exercises/submit"): "提交小节随堂练习",
    ("GET", "/api/courses/{course_id}/sections/{section_id}/exercises/latest"): "获取最近一次随堂练习提交",
    ("POST", "/api/courses/{course_id}/sections/{section_id}/complete"): "标记小节学习完成",
    ("POST", "/api/courses/{course_id}/chapters/{chapter_id}/knowledge-points"): "创建章节知识点",
    ("GET", "/api/courses/{course_id}/knowledge-points"): "获取课程知识点列表",
    ("GET", "/api/courses/{course_id}/index-records"): "获取课程索引记录",
    ("PATCH", "/api/courses/{course_id}/documents/{document_id}/link"): "关联课程资料到章节或知识点",
    ("POST", "/api/courses/{course_id}/documents/{document_id}/reindex"): "重建课程资料索引",
    ("POST", "/api/course-structure-drafts/{draft_id}/confirm"): "确认课程结构草稿",
    ("POST", "/api/course-structure-drafts/{draft_id}/generate-content"): "生成章节学习内容",
    ("POST", "/api/course-structure-drafts/{draft_id}/confirm-and-generate-content"): "确认结构并生成学习内容",
    ("GET", "/api/course-structure-drafts/content-generation-tasks/{task_id}"): "获取学习内容生成任务",
    ("GET", "/api/course-structure-drafts/content-generation-tasks/{task_id}/events"): "订阅学习内容生成进度",
    ("GET", "/api/course-structure-drafts/contents"): "获取小节学习内容列表",
    ("POST", "/api/course-structure-drafts/contents/resources/generate"): "生成小节资源详情",
    ("GET", "/api/home/courses"): "获取首页课程",
    ("POST", "/api/home/courses"): "添加首页课程",
    ("DELETE", "/api/home/courses/{course_id}"): "移除首页课程",
    ("GET", "/api/onboarding/questions"): "获取画像问卷题目",
    ("POST", "/api/onboarding/submit"): "提交画像问卷",
    ("GET", "/api/onboarding/profile"): "获取画像分析结果",
    ("GET", "/api/onboarding/status"): "获取画像问卷状态",
    ("POST", "/api/onboarding/skip"): "跳过画像问卷",
    ("GET", "/api/admin/onboarding/surveys"): "获取问卷列表",
    ("POST", "/api/admin/onboarding/surveys"): "创建问卷",
    ("GET", "/api/admin/onboarding/surveys/{survey_id}"): "获取问卷详情",
    ("PUT", "/api/admin/onboarding/surveys/{survey_id}"): "更新问卷",
    ("DELETE", "/api/admin/onboarding/surveys/{survey_id}"): "归档问卷",
    ("POST", "/api/admin/onboarding/surveys/{survey_id}/publish"): "发布问卷",
    ("POST", "/api/admin/onboarding/surveys/{survey_id}/duplicate"): "复制问卷",
    ("POST", "/api/admin/onboarding/surveys/{survey_id}/questions"): "创建问卷问题",
    ("PUT", "/api/admin/onboarding/questions/{question_id}"): "更新问卷问题",
    ("DELETE", "/api/admin/onboarding/questions/{question_id}"): "删除问卷问题",
    ("PUT", "/api/admin/onboarding/surveys/{survey_id}/questions/reorder"): "调整问卷问题顺序",
    ("POST", "/api/admin/onboarding/questions/{question_id}/options"): "创建问题选项",
    ("PUT", "/api/admin/onboarding/options/{option_id}"): "更新问题选项",
    ("DELETE", "/api/admin/onboarding/options/{option_id}"): "删除问题选项",
    ("POST", "/api/admin/learning-style-characters"): "创建学习风格角色",
    ("GET", "/api/admin/learning-style-characters"): "获取学习风格角色列表",
    ("GET", "/api/admin/learning-style-characters/{character_id}"): "获取学习风格角色详情",
    ("PUT", "/api/admin/learning-style-characters/{character_id}"): "更新学习风格角色",
    ("DELETE", "/api/admin/learning-style-characters/{character_id}"): "删除学习风格角色",
    ("PUT", "/api/admin/learning-style-characters/{character_id}/image"): "替换学习风格角色图片",
    ("PATCH", "/api/admin/learning-style-characters/{character_id}/status"): "更新学习风格角色状态",
    ("POST", "/api/admin/users/"): "管理端创建用户",
    ("GET", "/api/admin/users/students/learning-data"): "获取学生学习数据列表",
    ("GET", "/api/admin/users/students/{student_id}/learning-data"): "获取单个学生学习数据",
    ("GET", "/api/profile/me"): "获取我的学习画像",
    ("POST", "/api/profile/init-learning-data"): "初始化学生学习数据",
    ("POST", "/api/learning-path/generate"): "生成学习路径",
    ("GET", "/api/learning-path/my"): "获取我的学习路径",
    ("GET", "/api/learning-path/today"): "获取今日学习任务",
    ("PUT", "/api/learning-path/task/{task_id}/complete"): "完成学习任务",
    ("PUT", "/api/learning-path/tasks/{task_id}/complete"): "完成学习任务（兼容旧接口）",
    ("GET", "/api/exercises/{resource_id}"): "获取练习题",
    ("POST", "/api/exercise/submit"): "提交练习答案",
    ("GET", "/api/exercise/wrong-list"): "获取错题列表",
    ("GET", "/api/evaluation/report"): "获取学习评估报告",
    ("GET", "/api/evaluation/weak-points"): "获取薄弱知识点",
    ("GET", "/api/evaluation/mastery"): "获取知识掌握情况",
    ("POST", "/api/resources/generate"): "创建资源生成任务",
    ("GET", "/api/resources/task/{task_id}"): "获取资源生成任务",
    ("GET", "/api/resources/recommend"): "获取推荐资源",
    ("GET", "/api/resources/my"): "获取我的资源",
    ("GET", "/api/resources/favorites"): "获取收藏资源",
    ("GET", "/api/resources/review-list"): "获取资源审核列表",
    ("DELETE", "/api/resources/generated/all"): "清理生成资源",
    ("DELETE", "/api/resources/{resource_id}"): "删除学习资源",
    ("GET", "/api/resources/{resource_id}"): "获取学习资源详情",
    ("POST", "/api/resources/{resource_id}/review"): "审核学习资源",
    ("POST", "/api/resources/{resource_id}/regenerate"): "重新生成学习资源",
    ("POST", "/api/resources/{resource_id}/feedback"): "提交资源反馈",
    ("POST", "/api/resources/{resource_id}/favorite"): "收藏或取消收藏资源",
    ("POST", "/api/resources/{resource_id}/view"): "记录资源查看",
    ("GET", "/api/agent-tasks"): "获取智能体任务列表",
    ("GET", "/api/agent-tasks/{task_id}"): "获取智能体任务详情",
    ("POST", "/api/agent-tasks/{task_id}/retry"): "重试智能体任务",
    ("GET", "/api/tasks/{task_id}"): "获取任务详情（别名）",
    ("GET", "/api/dashboard/summary"): "获取看板汇总数据",
    ("GET", "/api/dashboard/resource-stats"): "获取资源统计数据",
    ("GET", "/api/dashboard/learning-stats"): "获取学习统计数据",
    ("GET", "/api/dashboard/agent-stats"): "获取智能体统计数据",
    ("GET", "/api/students"): "获取学生列表",
    ("GET", "/api/students/{student_id}/profile"): "获取学生画像",
    ("GET", "/api/students/{student_id}/learning-path"): "获取学生学习路径",
    ("GET", "/api/students/{student_id}/evaluation"): "获取学生评估数据",
    ("GET", "/api/settings/model"): "获取模型设置",
    ("PUT", "/api/settings/model"): "更新模型设置",
    ("GET", "/api/student/learning-style-character"): "获取我的学习风格角色",
    ("POST", "/api/profile/dialogue/sessions"): "创建画像对话会话",
    ("POST", "/api/profile/dialogue/messages"): "发送画像对话消息",
    ("POST", "/api/profile/dialogue/confirm"): "确认画像对话结果",
    ("POST", "/api/profile/dialogue/messages/stream"): "流式发送画像对话消息",
    ("POST", "/api/profile/dialogue/sessions/{session_id}/close"): "关闭画像对话会话",
    ("GET", "/api/profile/dialogue/active-session"): "获取当前画像对话会话",
    ("GET", "/api/profile/dialogue/sessions/{session_id}/messages"): "获取画像对话消息列表",
    ("POST", "/api/knowledge/search"): "检索知识库",
    ("POST", "/api/knowledge/ask"): "知识库问答",
    ("POST", "/api/tutor/sessions/enter"): "进入AI辅助问答会话",
    ("GET", "/api/tutor/sessions"): "获取AI辅助问答会话列表",
    ("GET", "/api/tutor/sessions/{session_id}/messages"): "获取AI辅助问答历史消息",
    ("POST", "/api/tutor/sessions/{session_id}/close"): "关闭AI辅助问答会话",
    ("POST", "/api/tutor/sessions/{session_id}/stream"): "发送AI辅助问答消息（流式）",
}


PARAMETER_TRANSLATIONS = {
    "keyword": "搜索关键词",
    "status": "状态",
    "page": "页码",
    "page_size": "每页数量",
    "course_id": "课程 ID",
    "chapter_id": "章节 ID",
    "section_id": "小节 ID",
    "document_id": "文档 ID",
    "knowledge_point": "知识点",
    "type": "类型",
    "difficulty": "难度",
    "resource_id": "资源 ID",
    "task_id": "任务 ID",
    "student_id": "学生 ID",
    "refresh": "是否强制刷新",
}


def install_chinese_openapi(app: FastAPI) -> None:
    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title="EduForge AI 服务接口文档",
            version=app.version,
            description="EduForge AI 后端服务接口文档",
            routes=app.routes,
        )
        for path, methods in schema.get("paths", {}).items():
            for method, operation in methods.items():
                if method.upper() not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                    continue
                operation["tags"] = [_tag_for_path(path)]
                summary = SUMMARY_TRANSLATIONS.get((method.upper(), path))
                if (
                    not summary
                    and method.upper() == "POST"
                    and path == "/api/courses/{course_id}/sections/{section_id}/resources/generate"
                ):
                    summary = "生成小节资源详情"
                if summary:
                    operation["summary"] = summary
                if operation.get("description"):
                    operation["description"] = operation["summary"]
                for parameter in operation.get("parameters", []) or []:
                    name = parameter.get("name")
                    if name in PARAMETER_TRANSLATIONS:
                        parameter["description"] = PARAMETER_TRANSLATIONS[name]
                if path.startswith("/api/tutor"):
                    operation.get("responses", {}).pop("422", None)
                    operation.setdefault("responses", {})["400"] = _standard_error_response()

        schema["tags"] = _build_tags(schema)
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi


def _build_tags(schema: dict[str, Any]) -> list[dict[str, str]]:
    names = []
    for methods in schema.get("paths", {}).values():
        for operation in methods.values():
            for tag in operation.get("tags", []):
                if tag not in names:
                    names.append(tag)
    return [{"name": name} for name in names]


def _tag_for_path(path: str) -> str:
    if path.startswith("/api/auth"):
        return "认证"
    if path.startswith("/api/users"):
        return "用户"
    if path.startswith("/api/courses"):
        return "课程"
    if path.startswith("/api/course-structure-drafts"):
        return "课程结构草稿"
    if path.startswith("/api/home"):
        return "首页课程"
    if path.startswith("/api/onboarding"):
        return "学生画像问卷"
    if path.startswith("/api/admin/onboarding"):
        return "管理端问卷配置"
    if path.startswith("/api/admin/learning-style-characters"):
        return "管理端学习风格角色"
    if path.startswith("/api/admin/users"):
        return "管理端用户管理"
    if path.startswith("/api/profile/dialogue"):
        return "画像对话"
    if path.startswith("/api/profile"):
        return "学生画像"
    if path.startswith("/api/learning-path"):
        return "学习路径"
    if path.startswith("/api/exercise") or path.startswith("/api/exercises"):
        return "练习"
    if path.startswith("/api/evaluation"):
        return "学习评估"
    if path.startswith("/api/resources"):
        return "学习资源"
    if path.startswith("/api/agent-tasks") or path.startswith("/api/tasks"):
        return "智能体任务"
    if path.startswith("/api/dashboard"):
        return "管理端数据看板"
    if path.startswith("/api/students"):
        return "管理端学生管理"
    if path.startswith("/api/settings"):
        return "系统设置"
    if path.startswith("/api/student/learning-style-character"):
        return "学生学习风格"
    if path.startswith("/api/knowledge"):
        return "知识库问答"
    if path.startswith("/api/tutor"):
        return "AI辅助问答"
    if path.startswith("/api/health") or path == "/":
        return "系统"
    return "其他"


def _standard_error_response() -> dict[str, Any]:
    """Document the error envelope produced by the global exception handlers."""
    return {
        "description": "参数或业务校验失败",
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["code", "message", "data"],
                    "properties": {
                        "code": {"type": "integer", "example": 40000},
                        "message": {"type": "string", "example": "参数错误"},
                        "data": {},
                    },
                }
            }
        },
    }
