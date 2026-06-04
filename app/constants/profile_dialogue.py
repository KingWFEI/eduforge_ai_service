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

PROFILE_SLOT_REQUIREMENTS = {
    "learning_style": ["learning_preferences", "cognitive_traits"],
    "learning_habits": ["learning_habits"],
    "motivation": ["motivation_factors"],
    "strengths_challenges": ["general_strengths", "general_challenges"],
    "pace_and_time": ["preferred_pace", "available_time"],
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
