from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.sql import func

from app.db.base import Base

# 保存每一轮用户和 AI 的消息，以及本轮智能体判断结果。
class ProfileDialogueMessage(Base):
    """学习画像对话消息表"""

    __tablename__ = "profile_dialogue_messages"

    id = Column(Integer, primary_key=True, index=True)

    session_id = Column(
        Integer,
        ForeignKey("profile_dialogue_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    student_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # user / assistant / system
    role = Column(String(20), nullable=False)

    content = Column(Text, nullable=False)

    # 本轮对话发生时的 slot
    slot = Column(String(50), nullable=True)

    # 用户回答是否和当前 slot 相关
    is_relevant = Column(Boolean, nullable=True)

    # 是否推进到下一个 slot
    should_advance = Column(Boolean, nullable=True)

    # 本轮抽取出的字段
    extracted_fields_json = Column(JSON, nullable=True)

    # 智能体调试信息
    agent_result_json = Column(JSON, nullable=True)
    # streaming / completed / interrupted / failed
    stream_status=Column(String(50), nullable=True)
    # SSE 中断时保存已经生成的部分回复
    partial_content=Column(Text, nullable=True)
    # AI 回复完成时间
    completed_at=Column(DateTime, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())