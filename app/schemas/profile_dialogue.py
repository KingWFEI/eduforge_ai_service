from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from app.constants.profile_dialogue import ProfileDialogueCloseReason


class CreateProfileDialogueSessionRequest(BaseModel):
    scene: str = "initial_profile"


class CreateProfileDialogueSessionData(BaseModel):
    session_id: int
    status: str
    current_slot: str
    progress: float
    opening_message: str
    missing_slots: List[str]


class SendProfileDialogueMessageRequest(BaseModel):
    session_id: int
    message: str

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
    profile_preview: Optional[Dict[str, Any]] = None