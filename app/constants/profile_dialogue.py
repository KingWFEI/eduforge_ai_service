from enum import Enum


class ProfileDialogueSlot(str, Enum):
    BASIC_INFO = "basic_info"          # 专业、年级、目标课程
    LEARNING_GOAL = "learning_goal"    # 学习目标
    SKILL_LEVEL = "skill_level"        # 编程、数学、课程基础
    LEARNING_STYLE = "learning_style"  # 学习偏好、认知风格
    WEAK_POINTS = "weak_points"        # 薄弱点
    TIME_BUDGET = "time_budget"        # 每日学习时间
    CONFIRM = "confirm"                # 等待确认画像


PROFILE_DIALOGUE_SLOT_ORDER = [
    ProfileDialogueSlot.BASIC_INFO.value,
    ProfileDialogueSlot.LEARNING_GOAL.value,
    ProfileDialogueSlot.SKILL_LEVEL.value,
    ProfileDialogueSlot.LEARNING_STYLE.value,
    ProfileDialogueSlot.WEAK_POINTS.value,
    ProfileDialogueSlot.TIME_BUDGET.value,
]

PROFILE_SLOT_REQUIREMENTS = {
    "basic_info": ["major", "grade", "target_course"],
    "learning_goal": ["learning_goals"],
    "skill_level": ["coding_level", "math_level", "course_level"],
    "learning_style": ["learning_preferences", "cognitive_style"],
    "weak_points": ["weaknesses"],
    "time_budget": ["time_budget"],
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