from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EnterSessionRequest(BaseModel):
    course_id: str | None = None
    section_id: str | None = None

    @field_validator("course_id", "section_id")
    @classmethod
    def empty_string_to_none(cls, value: str | None) -> str | None:
        value = value.strip() if value else None
        return value or None


class StreamChatRequest(EnterSessionRequest):
    message: str = Field(min_length=1, max_length=10000)
    context: str | None = Field(default=None, max_length=20000)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message must not be blank")
        return value

    @field_validator("context")
    @classmethod
    def blank_context_to_none(cls, value: str | None) -> str | None:
        value = value.strip() if value else None
        return value or None


class TutorMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class TutorSessionResponse(BaseModel):
    id: str
    title: str
    session_type: Literal["general", "tutoring"]
    course_id: str | None
    course_name: str | None
    status: Literal["active", "closed"]
    last_message: str | None
    created_at: datetime
    updated_at: datetime


class SessionListResponse(BaseModel):
    total: int
    items: list[TutorSessionResponse]


class EnterSessionResponse(BaseModel):
    session_id: str
    session_type: Literal["general", "tutoring"]
    course_id: str | None
    is_new: bool


class CloseSessionResponse(BaseModel):
    session_id: str
    status: Literal["closed"]
