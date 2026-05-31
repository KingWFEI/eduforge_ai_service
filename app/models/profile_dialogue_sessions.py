
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, JSON
from sqlalchemy.sql import func
from app.db.base import Base


# 保存当前画像构建状态
class ProfileDialogueSession(Base):
    __tablename__ = 'profile_dialogue_sessions'
    id =Column(Integer,primary_key=True,index=True)
    student_id=Column(Integer,ForeignKey('users.id',ondelete='CASCADE'),index=True,nullable=False)
    # initial_profile / profile_update
    scene = Column(String(50), default="initial_profile", nullable=False)

    # collecting          正在采集
    # ready_to_confirm    等待确认
    # completed           已保存画像
    # inactive            长时间未活动
    # interrupted         SSE 中断
    # cancelled           用户主动取消
    status = Column(String(30), default="collecting", index=True, nullable=False)

    # 当前正在采集哪个画像维度
    current_slot = Column(String(50), default="basic_info", nullable=False)

    # 已完成的 slot，例如 ["basic_info", "learning_goal"]
    collected_slots_json = Column(JSON, default=list, nullable=False)

    # 还缺哪些 slot
    missing_slots_json = Column(JSON, default=list, nullable=False)

    # 已抽取出的画像字段
    extracted_fields_json = Column(JSON, default=dict, nullable=False)

    # 画像预览，ready_to_confirm 后生成
    profile_preview_json = Column(JSON, nullable=True)

    # 画像完成度 0-1
    progress = Column(Float, default=0.0, nullable=False)

    # 最终生成的 profile_id
    profile_id = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    last_active_at= Column(DateTime(timezone=True), server_default=func.now(), server_onupdate=func.now())
    ended_at= Column(DateTime(timezone=True), server_default=func.now(), server_onupdate=func.now())
    end_reason= Column(String(50), nullable=True)
    # streaming / completed / interrupted / failed
    stream_status=Column(String(50), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )