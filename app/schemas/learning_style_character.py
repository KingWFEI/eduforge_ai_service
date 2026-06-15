from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


CharacterStatus = Literal["DRAFT", "PUBLISHED", "DISABLED"]
MatchStatus = Literal[
    "MATCHED",
    "PROFILE_REQUIRED",
    "MATCHING",
    "STYLE_UNAVAILABLE",
    "MATCH_FAILED",
]


class LearningStyleCharacterBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None
    style_prompt: Optional[str] = None
    feature_tags: list[str] = Field(default_factory=list)
    suitable_methods: list[str] = Field(default_factory=list)
    priority: int = 0


class LearningStyleCharacterUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = None
    style_prompt: Optional[str] = None
    feature_tags: Optional[list[str]] = None
    suitable_methods: Optional[list[str]] = None
    priority: Optional[int] = None


class LearningStyleCharacterStatusUpdate(BaseModel):
    status: CharacterStatus


class LearningStyleCharacterResponse(BaseModel):
    id: str
    name: str
    code: str
    image_url: str
    description: Optional[str] = None
    style_prompt: Optional[str] = None
    feature_tags: list[str] = Field(default_factory=list)
    suitable_methods: list[str] = Field(default_factory=list)
    status: CharacterStatus
    priority: int
    version: int
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class LearningStyleCharacterCreateResponse(BaseModel):
    id: str
    name: str
    code: str
    image_url: str
    status: CharacterStatus


class MatchedCharacterResponse(BaseModel):
    id: str
    code: str
    name: str
    image_url: str
    description: Optional[str] = None
    match_score: float
    match_reason: Optional[str] = None
    matched_features: list[str] = Field(default_factory=list)
    suitable_methods: list[str] = Field(default_factory=list)


class LearningStyleCharacterMatchResponse(BaseModel):
    status: MatchStatus
    profile_required: bool = False
    character: Optional[MatchedCharacterResponse] = None
    matched_at: Optional[str] = None
    action: Optional[dict[str, Any]] = None
