from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator

from app.constants.profile_dialogue import ProfileDialogueCloseReason


class CreateProfileDialogueSessionRequest(BaseModel):
    scene: str = "initial_profile"


class ProfileDialogueDisplayField(BaseModel):
    key: str
    label: str
    value: str


class ProfileDialogueDisplayData(BaseModel):
    current_slot: str
    missing_slots: List[str]
    fields: List[ProfileDialogueDisplayField]


class CreateProfileDialogueSessionData(BaseModel):
    session_id: int
    status: str
    current_slot: str
    progress: float
    opening_message: str
    missing_slots: List[str]
    extracted_fields: Dict[str, Any]
    display: ProfileDialogueDisplayData


class SendProfileDialogueMessageRequest(BaseModel):
    session_id: int
    message: Optional[str] = Field(default=None, max_length=10000)
    content: Optional[str] = Field(default=None, max_length=10000)
    client_message_id: Optional[str] = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def normalize_message(self):
        value = (self.message or self.content or "").strip()
        if not value:
            raise ValueError("message or content must not be blank")
        self.message = value
        return self

class ProfileDialogueMessageData(BaseModel):
    session_id: int
    status: str
    current_slot: str
    previous_slot: Optional[str] = None

    assistant_reply: str

    is_relevant: bool
    should_advance: bool

    extracted_fields: Dict[str, Any]
    collected_slots: List[str]
    missing_slots: List[str]
    progress: float
    display: ProfileDialogueDisplayData

    profile_preview: Optional[Dict[str, Any]] = None

class CloseDialogueReason(BaseModel):
    reason: ProfileDialogueCloseReason = ProfileDialogueCloseReason.USER_CLOSED

class ProfileDialogueHistoryMessageData(BaseModel):
    message_id: int
    role: str
    content: str
    created_at: Optional[datetime] = None
class ProfileDialogueSessionMessagesData(BaseModel):
    session_id: int
    status: str
    current_slot: str
    progress: float

    messages: List[ProfileDialogueHistoryMessageData]

    extracted_fields: Dict[str, Any]
    collected_slots: List[str]
    missing_slots: List[str]
    display: ProfileDialogueDisplayData
    profile_preview: Optional[Dict[str, Any]] = None
