from enum import Enum


class ProfileDialogueSlot(str, Enum):
    LEARNING_STYLE = "learning_style"
    LEARNING_HABITS = "learning_habits"
    MOTIVATION = "motivation"
    STRENGTHS_CHALLENGES = "strengths_challenges"
    PACE_AND_TIME = "pace_and_time"
    CONFIRM = "confirm"


PROFILE_DIALOGUE_SLOT_ORDER = [
    ProfileDialogueSlot.LEARNING_STYLE.value,
    ProfileDialogueSlot.LEARNING_HABITS.value,
    ProfileDialogueSlot.MOTIVATION.value,
    ProfileDialogueSlot.STRENGTHS_CHALLENGES.value,
    ProfileDialogueSlot.PACE_AND_TIME.value,
]

PROFILE_DIALOGUE_SLOT_LABELS = {
    ProfileDialogueSlot.LEARNING_STYLE.value: "学习偏好",
    ProfileDialogueSlot.LEARNING_HABITS.value: "学习习惯",
    ProfileDialogueSlot.MOTIVATION.value: "学习动机",
    ProfileDialogueSlot.STRENGTHS_CHALLENGES.value: "优势与挑战",
    ProfileDialogueSlot.PACE_AND_TIME.value: "学习节奏与时间",
    ProfileDialogueSlot.CONFIRM.value: "确认画像",
}

PROFILE_DIALOGUE_FIELD_LABELS = {
    "preferred_content_formats": "偏好的内容形式",
    "theory_practice_preference": "理论与实践偏好",
    "interaction_preference": "互动偏好",
    "cognitive_preference": "认知偏好",
    "planning_habit": "学习计划习惯",
    "review_habit": "复习习惯",
    "note_taking_habit": "笔记习惯",
    "focus_environment": "专注环境",
    "primary_learning_goal": "主要学习目标",
    "motivation_source": "学习动力来源",
    "expected_outcome": "期望学习成果",
    "learning_strengths": "学习优势",
    "learning_challenges": "学习挑战",
    "difficult_knowledge_types": "困难知识类型",
    "available_learning_time": "可用学习时间",
    "preferred_learning_pace": "偏好的学习节奏",
    "preferred_learning_period": "偏好的学习时段",
    "session_duration": "单次学习时长",
}

PROFILE_DIALOGUE_VALUE_LABELS = {
    "video": "视频",
    "text": "图文",
    "article": "文章",
    "image": "图片",
    "diagram": "图解",
    "case": "案例",
    "examples": "示例",
    "theory": "理论",
    "practice": "实践",
    "interactive": "互动学习",
    "independent": "独立学习",
    "visual": "视觉型",
    "auditory": "听觉型",
    "reading_writing": "读写型",
    "kinesthetic": "实践型",
    "fast": "较快",
    "steady": "稳步",
    "slow": "较慢",
    "morning": "上午",
    "afternoon": "下午",
    "evening": "晚上",
}


def localize_profile_dialogue_slots(slots: list[str] | None) -> list[str]:
    """将内部状态键转换为面向前端展示的中文名称。"""
    return [
        PROFILE_DIALOGUE_SLOT_LABELS[slot]
        for slot in (slots or [])
        if slot in PROFILE_DIALOGUE_SLOT_LABELS
    ]

PROFILE_SLOT_REQUIREMENTS = {
    "learning_style": ["learning_preferences", "cognitive_traits"],
    "learning_habits": ["learning_habits"],
    "motivation": ["motivation_factors"],
    "strengths_challenges": ["general_strengths", "general_challenges"],
    "pace_and_time": ["preferred_pace", "available_time"],
}


PROFILE_SLOT_CONFIG = {
    "learning_style": {
        "required_fields": [
            "preferred_content_formats",
            "theory_practice_preference",
        ],
        "optional_fields": [
            "interaction_preference",
            "cognitive_preference",
        ],
        "min_required_fields": 1,
        "question_order": [
            "preferred_content_formats",
            "theory_practice_preference",
            "interaction_preference",
        ],
    },
    "learning_habits": {
        "required_fields": ["planning_habit", "review_habit"],
        "optional_fields": ["note_taking_habit", "focus_environment"],
        "min_required_fields": 1,
        "question_order": ["planning_habit", "review_habit", "note_taking_habit"],
    },
    "motivation": {
        "required_fields": ["primary_learning_goal"],
        "optional_fields": ["motivation_source", "expected_outcome"],
        "min_required_fields": 1,
        "question_order": ["primary_learning_goal", "expected_outcome"],
    },
    "strengths_challenges": {
        "required_fields": ["learning_strengths", "learning_challenges"],
        "optional_fields": ["difficult_knowledge_types"],
        "min_required_fields": 1,
        "question_order": ["learning_strengths", "learning_challenges"],
    },
    "pace_and_time": {
        "required_fields": ["available_learning_time", "preferred_learning_pace"],
        "optional_fields": ["preferred_learning_period", "session_duration"],
        "min_required_fields": 1,
        "question_order": [
            "available_learning_time",
            "preferred_learning_pace",
            "preferred_learning_period",
        ],
    },
}


PROFILE_FIELD_QUESTIONS = {
    "learning_style.preferred_content_formats": "你更喜欢视频、图文还是案例？",
    "learning_style.theory_practice_preference": "你更偏好理论讲解还是动手实践？",
    "learning_style.interaction_preference": "你更喜欢独立学习还是互动讨论？",
    "learning_habits.planning_habit": "平时学习会提前做计划吗？",
    "learning_habits.review_habit": "你会定期复习学过的内容吗？",
    "learning_habits.note_taking_habit": "你平时有整理学习笔记的习惯吗？",
    "motivation.primary_learning_goal": "你目前最主要的学习目标是什么？",
    "motivation.expected_outcome": "你希望这段学习最终带来什么结果？",
    "strengths_challenges.learning_strengths": "你觉得自己学习时最擅长什么？",
    "strengths_challenges.learning_challenges": "你目前学习中最大的困难是什么？",
    "pace_and_time.available_learning_time": "你通常每天能安排多少学习时间？",
    "pace_and_time.preferred_learning_pace": "你更喜欢集中学习还是分段推进？",
    "pace_and_time.preferred_learning_period": "你通常在什么时段学习？",
}

class ProfileDialogueCloseReason(str, Enum):
    USER_CLOSED = "user_closed"              # 用户点击返回/关闭页面
    APP_BACKGROUND = "app_background"        # App 进入后台
    APP_TERMINATED = "app_terminated"        # App 被关闭/销毁，前端尽力通知
    ROUTE_CHANGED = "route_changed"          # 用户跳转到其他页面

    SSE_DISCONNECTED = "sse_disconnected"    # SSE 连接断开
    NETWORK_ERROR = "network_error"          # 网络异常
    CLIENT_CANCELLED = "client_cancelled"    # 前端主动 cancel 当前流式请求

    TIMEOUT = "timeout"                      # 后端检测长时间无活动
    SYSTEM_EXPIRED = "system_expired"        # 会话超过最大有效期
    NEW_SESSION_STARTED = "new_session_started"  # 用户选择重新开始，旧会话关闭

    COMPLETED = "completed"                  # 用户确认保存画像，正常完成
    CANCELLED = "cancelled"                  # 用户主动取消画像构建
