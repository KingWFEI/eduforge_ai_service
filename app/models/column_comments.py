"""Centralized Chinese comments for ORM columns.

The comments are applied to SQLAlchemy metadata at import time and reused by
the Alembic migration that writes comments into MySQL.
"""

from __future__ import annotations

from sqlalchemy import MetaData


TABLE_DESCRIPTIONS = {
    "users": "用户",
    "user_onboarding_status": "用户引导问卷状态",
    "verification_codes": "短信验证码",
    "login_logs": "登录日志",
    "courses": "课程",
    "course_chapters": "课程章节",
    "knowledge_points": "知识点",
    "course_documents": "课程资料",
    "knowledge_chunks": "知识块",
    "vector_index_records": "向量索引记录",
    "course_structure_drafts": "课程结构草稿",
    "onboarding_surveys": "引导问卷",
    "onboarding_questions": "问卷问题",
    "onboarding_options": "问卷选项",
    "onboarding_submissions": "问卷提交",
    "onboarding_answers": "问卷答案",
    "student_profiles": "学生学习画像",
    "student_learning_profiles": "学生综合学习画像",
    "student_domain_competencies": "学生领域能力画像",
    "student_learning_contexts": "学生学习上下文",
    "profile_versions": "学习画像版本",
    "profile_analyses": "画像分析任务",
    "profile_dialogue_sessions": "画像对话会话",
    "profile_dialogue_messages": "画像对话消息",
    "learning_resources": "学习资源",
    "resource_references": "资源引用来源",
    "resource_feedback": "资源反馈",
    "resource_favorites": "资源收藏",
    "resource_reviews": "资源审核",
    "resource_generation_tasks": "资源生成任务",
    "agent_tasks": "智能体任务",
    "agent_task_steps": "智能体任务步骤",
    "chat_sessions": "AI 对话会话",
    "chat_messages": "AI 对话消息",
    "chat_message_sources": "消息知识来源",
    "chat_feedback": "对话反馈",
    "learning_paths": "学习路径",
    "learning_path_tasks": "学习路径任务",
    "exercise_sets": "练习集合",
    "exercise_questions": "练习题",
    "exercise_submissions": "练习提交",
    "exercise_answers": "学生答题明细",
    "wrong_questions": "错题",
    "evaluation_reports": "学习评估报告",
    "mastery_records": "知识点掌握记录",
    "weak_point_records": "薄弱点记录",
    "study_records": "学习记录",
    "user_notifications": "用户通知",
    "dashboard_daily_stats": "仪表盘每日统计",
    "system_settings": "系统设置",
    "prompt_templates": "提示词模板",
}


COMMON_COLUMN_COMMENTS = {
    "id": "主键ID",
    "student_id": "学生ID，关联学习者用户或学生标识",
    "user_id": "用户ID，关联 users.id",
    "username": "用户名，用于登录或展示",
    "password_hash": "加密后的登录密码哈希",
    "email": "邮箱地址",
    "name": "用户姓名或显示名称",
    "phone": "手机号",
    "is_phone_verified": "手机号是否已验证",
    "is_active": "账号是否启用",
    "avatar_url": "头像图片地址",
    "role": "用户角色，可选值如 student、teacher、admin",
    "status": "业务状态，具体可选值见接口或业务枚举",
    "created_at": "创建时间",
    "updated_at": "更新时间",
    "course_id": "课程业务ID，通常关联 courses.course_id",
    "parent_id": "父级ID，用于课程章/小节层级结构",
    "level": "层级，1 表示章，2 表示小节",
    "resource_id": "学习资源ID",
    "document_id": "课程资料ID",
    "chapter_id": "章节ID",
    "knowledge_point_id": "知识点ID",
    "question_id": "问题或练习题业务ID",
    "submission_id": "提交记录ID",
    "message_id": "对话消息ID",
    "session_id": "会话ID",
    "task_id": "任务ID",
    "title": "标题",
    "description": "说明描述",
    "content": "正文内容",
    "content_text": "文本形式的资源内容",
    "content_json": "JSON 格式的结构化资源内容",
    "type": "类型，具体可选值见接口或业务枚举",
    "source": "数据来源",
    "version": "版本号",
    "sort_order": "排序值，数值越小越靠前",
    "created_by": "创建人标识",
    "updated_by": "更新人标识",
    "confirmed_by": "确认人标识",
    "error_message": "错误信息",
    "progress": "进度值，通常为 0-100 或 0-1",
    "confidence": "置信度，通常为 0-1",
    "difficulty": "难度，可选值如 easy、medium、hard",
    "completed_at": "完成时间",
    "started_at": "开始时间",
    "finished_at": "结束时间",
    "last_updated": "最近更新时间",
    "last_active_at": "最近活跃时间",
    "ended_at": "会话结束时间",
    "index_type": "索引类型，可选值如 chroma",
    "collection_name": "向量数据库集合名称",
    "chunk_count": "知识块数量",
    "success_count": "成功数量",
    "failed_count": "失败数量",
    "filename": "原始文件名",
    "file_path": "文件存储路径",
    "file_type": "文件类型或扩展名",
    "file_size": "文件大小，单位字节",
    "uploaded_by": "上传人标识",
    "uploaded_at": "上传时间",
    "parse_status": "解析状态，可选值如 pending、processing、completed、failed",
    "index_status": "索引状态，可选值如 pending、processing、completed、failed",
    "deleted": "是否已逻辑删除",
    "indexed": "是否已写入向量索引，0 否 1 是",
    "section": "内容所属章节或小节",
    "page_no": "页码",
    "chunk_index": "知识块在文档内的序号",
    "vector_id": "向量数据库中的向量ID",
    "keywords_json": "JSON 数组，知识块关键词",
    "prerequisites_json": "JSON 数组，前置知识点",
    "learning_preferences_json": "JSON 对象，学习偏好",
    "cognitive_traits_json": "JSON 对象，认知特征",
    "cognitive_style_json": "JSON 对象，认知风格",
    "learning_habits_json": "JSON 对象，学习习惯",
    "motivation_factors_json": "JSON 对象，学习动机因素",
    "general_strengths_json": "JSON 数组，通用优势",
    "general_challenges_json": "JSON 数组，通用挑战或薄弱项",
    "strengths_json": "JSON 数组，优势项",
    "weaknesses_json": "JSON 数组，薄弱项",
    "available_time_json": "JSON 对象，可用学习时间",
    "time_budget_json": "JSON 对象，学习时间预算",
    "learning_goals_json": "JSON 数组，学习目标",
    "profile_dimensions_json": "JSON 对象，画像维度明细",
    "evidence_json": "JSON 对象，生成画像所依据的证据",
    "confidence_json": "JSON 对象，各维度置信度",
    "summary": "摘要说明",
    "current_step": "当前处理步骤",
    "input_json": "JSON 对象，任务输入参数",
    "output_json": "JSON 对象，任务输出结果",
    "agent_trace_json": "JSON 对象，智能体执行轨迹",
    "error_json": "JSON 对象，错误详情",
}


TABLE_COLUMN_COMMENTS = {
    "users": {
        "status": "账号状态，可选值如 normal、disabled、locked",
        "last_login_at": "最近一次登录时间",
    },
    "user_onboarding_status": {
        "status": "引导问卷状态，可选值：not_started、processing、completed、failed、skipped、reset_required",
        "survey_id": "当前使用的问卷业务ID",
        "profile_id": "引导问卷生成的学习画像ID",
        "need_onboarding": "是否需要进入引导问卷",
        "completed_at": "完成问卷时间",
        "skipped_at": "跳过问卷时间",
        "reset_at": "重置问卷时间",
        "reset_reason": "重置原因",
    },
    "verification_codes": {
        "code": "短信验证码",
        "scene": "验证码使用场景，可选值如 register、login、reset_password",
        "expires_at": "验证码过期时间",
        "is_used": "验证码是否已使用",
        "used_at": "验证码使用时间",
    },
    "login_logs": {
        "login_type": "登录方式，可选值如 password、sms_code",
        "success": "是否登录成功",
        "fail_reason": "登录失败原因",
        "client_type": "客户端类型，可选值如 web、mobile、admin",
        "ip_address": "登录来源 IP 地址",
        "user_agent": "浏览器或客户端 User-Agent",
    },
    "courses": {
        "course_id": "课程业务ID，对外使用的唯一标识",
        "name": "课程名称",
        "cover_url": "课程封面图地址",
        "semester": "开课学期",
        "status": "课程状态，可选值如 active、inactive、archived",
    },
    "knowledge_points": {
        "name": "知识点名称",
        "difficulty": "知识点难度，可选值如 easy、medium、hard",
    },
    "vector_index_records": {
        "status": "索引任务状态，可选值如 processing、completed、failed",
    },
    "course_structure_drafts": {
        "source_document_ids_json": "JSON 数组，生成草稿所使用的课程资料ID",
        "draft_json": "JSON 对象，AI 识别出的课程章节、小节和知识点草稿",
        "status": "草稿状态，可选值：draft、confirmed、cancelled",
        "confirmed_at": "确认草稿时间",
    },
    "onboarding_surveys": {
        "survey_id": "问卷业务ID，对外使用的唯一标识",
        "status": "问卷状态，可选值：draft、published、archived",
        "target_role": "目标用户角色，可选值如 student、teacher、admin",
        "target_course_id": "目标课程ID，为空表示不限定课程",
        "submit_count": "问卷提交次数",
    },
    "onboarding_questions": {
        "question_id": "问题业务ID，对外使用的唯一标识",
        "step": "问题步骤序号",
        "subtitle": "问题副标题或补充说明",
        "type": "题型，可选值如 single、multiple、text、scale",
        "required": "是否必填",
        "config_json": "JSON 对象，题目配置",
        "is_deleted": "是否已逻辑删除",
    },
    "onboarding_options": {
        "option_id": "选项业务ID，对外使用的唯一标识",
        "label": "选项展示文本",
        "value": "选项提交值",
        "icon": "选项图标标识",
        "color": "选项展示颜色",
        "profile_mapping_json": "JSON 对象，选项到画像字段的映射规则",
        "is_deleted": "是否已逻辑删除",
    },
    "onboarding_submissions": {
        "answers_json": "JSON 对象，问卷答案快照",
        "generated_profile_id": "提交后生成的学习画像ID",
        "status": "提交状态，可选值如 submitted、processing、completed、failed",
        "submitted_at": "提交时间",
    },
    "onboarding_answers": {
        "answer_json": "JSON 对象，单题答案内容",
    },
    "student_profiles": {
        "major": "专业",
        "grade": "年级",
        "target_course_id": "目标课程ID",
        "target_course": "目标课程名称",
        "coding_level": "编程水平，可选值由画像问卷或接口定义",
        "math_level": "数学基础水平，可选值由画像问卷或接口定义",
        "course_level": "目标课程基础水平，可选值由画像问卷或接口定义",
        "time_budget": "可投入学习时间的文字描述",
    },
    "student_domain_competencies": {
        "domain_type": "领域类型，可选值如 course、subject、skill",
        "domain_id": "领域ID，如课程ID或技能ID",
        "domain_name": "领域名称",
        "competency_level": "能力等级，可选值由画像分析规则定义",
        "knowledge_state_json": "JSON 对象，知识掌握状态",
    },
    "student_learning_contexts": {
        "course_name": "课程名称",
        "status": "学习上下文状态，可选值如 active、completed、paused",
    },
    "profile_versions": {
        "profile_id": "学习画像ID",
        "profile_snapshot_json": "JSON 对象，画像版本快照",
        "changed_fields_json": "JSON 对象，本版本变更字段",
    },
    "profile_analyses": {
        "analysis_type": "分析类型，可选值如 onboarding、dialogue、refresh",
        "status": "分析状态，可选值如 pending、processing、completed、failed",
        "analysis_text": "画像分析文本",
        "learning_suggestion": "学习建议文本",
        "resource_strategy_json": "JSON 对象，资源推荐策略",
        "weakness_analysis_json": "JSON 对象，薄弱点分析",
    },
    "profile_dialogue_sessions": {
        "scene": "对话场景，可选值：initial_profile、profile_update",
        "status": "会话状态，可选值：collecting、ready_to_confirm、completed、inactive、interrupted、cancelled",
        "current_slot": "当前正在采集的画像维度",
        "collected_slots_json": "JSON 数组，已完成采集的画像维度",
        "missing_slots_json": "JSON 数组，仍缺失的画像维度",
        "extracted_fields_json": "JSON 对象，已抽取的画像字段",
        "profile_preview_json": "JSON 对象，待确认的画像预览",
        "profile_id": "最终生成或更新的画像ID",
        "end_reason": "会话结束原因",
        "stream_status": "流式输出状态，可选值：streaming、completed、interrupted、failed",
    },
    "profile_dialogue_messages": {
        "role": "消息角色，可选值：user、assistant、system",
        "slot": "本轮对话对应的画像维度",
        "is_relevant": "用户回答是否与当前维度相关",
        "should_advance": "是否推进到下一个画像维度",
        "agent_result_json": "JSON 对象，智能体判断和调试信息",
        "stream_status": "流式输出状态，可选值：streaming、completed、interrupted、failed",
        "partial_content": "SSE 中断时已生成的部分回复",
    },
    "learning_resources": {
        "type": "资源类型，可选值如 article、exercise、video、summary、quiz",
        "review_status": "审核状态，可选值：pending、approved、rejected",
        "safety_score": "安全评分，通常为 0-1",
        "hallucination_risk": "幻觉风险等级，可选值如 low、medium、high",
        "generated_by_task_id": "生成该资源的智能体任务ID",
        "reason": "推荐或生成该资源的原因",
    },
    "resource_feedback": {
        "liked": "是否点赞，1 是 0 否",
        "favorite": "是否收藏，1 是 0 否",
        "difficulty_feedback": "用户反馈的难度，可选值如 too_easy、suitable、too_hard",
        "comment": "反馈备注",
    },
    "resource_reviews": {
        "reviewer_id": "审核人ID",
        "action": "审核动作，可选值如 approve、reject、revise",
        "reviewed_at": "审核时间",
    },
    "resource_generation_tasks": {
        "knowledge_point": "目标知识点名称",
        "goal": "资源生成目标",
        "resource_types_json": "JSON 数组，需要生成的资源类型",
        "status": "生成任务状态，可选值如 pending、processing、completed、failed",
        "result_resource_ids_json": "JSON 数组，生成出的资源ID列表",
    },
    "agent_tasks": {
        "task_type": "智能体任务类型",
        "related_task_id": "关联业务任务ID",
        "status": "任务状态，可选值如 pending、running、completed、failed、cancelled",
    },
    "agent_task_steps": {
        "agent_name": "执行该步骤的智能体名称",
        "step_order": "步骤序号",
        "status": "步骤状态，可选值如 pending、running、completed、failed",
        "input_summary": "步骤输入摘要",
        "output_summary": "步骤输出摘要",
        "duration_ms": "步骤耗时，单位毫秒",
    },
    "chat_sessions": {
        "mode": "对话模式，可选值如 tutor、qa、review",
        "last_message": "最近一条消息摘要",
        "last_message_at": "最近消息时间",
        "message_count": "会话消息数量",
        "status": "会话状态，可选值如 active、archived、deleted",
    },
    "chat_messages": {
        "role": "消息角色，可选值：user、assistant、system",
        "content_type": "内容类型，可选值如 text、markdown、json",
        "status": "消息状态，可选值如 streaming、completed、failed",
        "agent_task_id": "生成该回复的智能体任务ID",
        "token_count": "消息消耗或生成的 token 数",
    },
    "chat_message_sources": {
        "source_title": "引用来源标题",
        "source_page": "引用来源页码",
    },
    "chat_feedback": {
        "rating": "评分，通常为 1-5",
        "liked": "是否点赞，1 是 0 否",
        "comment": "反馈备注",
    },
    "learning_paths": {
        "goal": "学习路径目标",
        "duration_days": "计划持续天数",
        "daily_minutes": "每日计划学习分钟数",
        "status": "路径状态，可选值如 active、completed、paused、cancelled",
        "plan_json": "JSON 对象，学习路径计划详情",
        "created_by_task_id": "创建该路径的智能体任务ID",
    },
    "learning_path_tasks": {
        "path_id": "学习路径ID",
        "day_no": "计划第几天",
        "topic": "学习主题",
        "estimated_minutes": "预计学习分钟数",
        "resource_ids_json": "JSON 数组，关联资源ID列表",
        "status": "任务状态，可选值：not_started、in_progress、completed、skipped",
    },
    "exercise_questions": {
        "exercise_set_id": "练习集合ID",
        "question": "题干内容",
        "options_json": "JSON 数组，题目选项",
        "correct_answer_json": "JSON 对象或数组，标准答案",
        "explanation": "答案解析",
        "related_knowledge": "关联知识点名称",
    },
    "exercise_submissions": {
        "score": "得分",
        "accuracy": "正确率，通常为 0-1",
        "correct_count": "答对题目数",
        "total_count": "总题目数",
        "duration_seconds": "作答耗时，单位秒",
        "weak_points_json": "JSON 数组，本次练习暴露的薄弱点",
        "analysis_json": "JSON 对象，本次练习分析结果",
        "submitted_at": "提交时间",
    },
    "exercise_answers": {
        "student_answer_json": "JSON 对象或数组，学生答案",
        "is_correct": "是否正确，1 是 0 否",
        "explanation": "本题解析或批改说明",
    },
    "wrong_questions": {
        "wrong_count": "累计答错次数",
        "last_wrong_at": "最近一次答错时间",
        "mastered": "是否已掌握，1 是 0 否",
    },
    "evaluation_reports": {
        "report_range": "报告范围，可选值如 daily、weekly、monthly、course",
        "completion_rate": "学习完成率，通常为 0-1",
        "accuracy_rate": "练习正确率，通常为 0-1",
        "study_hours": "学习时长，单位小时",
        "mastery_json": "JSON 对象，掌握度统计",
        "good_points_json": "JSON 数组，表现较好的知识点",
        "weak_points_json": "JSON 数组，薄弱知识点",
        "recommendations_json": "JSON 数组，推荐行动",
        "next_suggestion": "下一步学习建议",
    },
    "mastery_records": {
        "knowledge_point": "知识点名称",
        "score": "掌握度分数，通常为 0-1",
    },
    "weak_point_records": {
        "knowledge_point": "薄弱知识点名称",
        "mastery_score": "掌握度分数，通常为 0-1",
        "wrong_count": "相关错题次数",
        "reason": "形成薄弱点的原因",
        "suggested_action": "建议补救动作",
    },
    "study_records": {
        "path_task_id": "学习路径任务ID",
        "action_type": "学习行为类型，可选值如 view、complete、practice、review",
        "study_minutes": "学习时长，单位分钟",
        "progress_delta": "本次学习带来的进度变化",
    },
    "user_notifications": {
        "title": "通知标题",
        "content": "通知内容",
        "type": "通知类型，可选值如 system、learning、task、resource",
        "related_id": "关联业务对象ID",
        "is_read": "是否已读",
        "read_at": "阅读时间",
    },
    "dashboard_daily_stats": {
        "stat_date": "统计日期",
        "student_count": "学生数量",
        "course_count": "课程数量",
        "generated_resource_count": "生成资源数量",
        "agent_task_count": "智能体任务数量",
        "average_accuracy": "平均正确率，通常为 0-1",
        "learning_path_completion_rate": "学习路径完成率，通常为 0-1",
        "agent_task_success_rate": "智能体任务成功率，通常为 0-1",
    },
    "system_settings": {
        "setting_key": "配置键名",
        "setting_value_json": "JSON 对象，配置值",
    },
    "prompt_templates": {
        "name": "提示词模板名称",
        "scene": "适用场景",
        "content": "提示词内容",
        "enabled": "是否启用",
    },
}


def _comment_for_column(table_name: str, column_name: str) -> str:
    table_desc = TABLE_DESCRIPTIONS.get(table_name, table_name)
    if column_name in TABLE_COLUMN_COMMENTS.get(table_name, {}):
        return TABLE_COLUMN_COMMENTS[table_name][column_name]
    if column_name.endswith("_json") and column_name not in COMMON_COLUMN_COMMENTS:
        base_name = column_name.removesuffix("_json")
        return f"JSON 格式字段：{base_name}"
    if column_name in COMMON_COLUMN_COMMENTS:
        return COMMON_COLUMN_COMMENTS[column_name]
    return f"{table_desc}字段：{column_name}"


def get_column_comments(metadata: MetaData) -> dict[str, dict[str, str]]:
    """Build comments for all columns present in the given metadata."""

    comments: dict[str, dict[str, str]] = {}
    for table_name, table in metadata.tables.items():
        comments[table_name] = {
            column.name: _comment_for_column(table_name, column.name)
            for column in table.columns
        }
    return comments


def apply_column_comments(metadata: MetaData) -> None:
    """Attach comments to SQLAlchemy Column objects."""

    comments = get_column_comments(metadata)
    for table_name, column_comments in comments.items():
        table = metadata.tables.get(table_name)
        if table is None:
            continue
        for column_name, comment in column_comments.items():
            if column_name in table.c:
                table.c[column_name].comment = comment
