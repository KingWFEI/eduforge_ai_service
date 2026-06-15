from pydantic import BaseModel, Field


class ModelSettingsResponse(BaseModel):
    llm_provider: str = "deepseek"
    model_name: str = "deepseek-chat"
    temperature: float = 0.2
    max_tokens: int = 4096
    rag_top_k: int = 5
    safety_review_enabled: bool = True


class ModelSettingsUpdateRequest(BaseModel):
    llm_provider: str = Field(default="deepseek")
    model_name: str = Field(default="deepseek-chat")
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=4096, ge=256, le=32768)
    rag_top_k: int = Field(default=5, ge=1, le=20)
    safety_review_enabled: bool = True
