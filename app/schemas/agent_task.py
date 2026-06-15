from typing import Any, List, Optional

from pydantic import BaseModel, Field


class AgentTaskListItem(BaseModel):
    task_id: str
    task_type: str
    status: str
    progress: int = 0
    student_name: Optional[str] = None
    course: Optional[str] = None
    knowledge_point: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class AgentTaskListResponse(BaseModel):
    items: List[AgentTaskListItem] = Field(default_factory=list)
    total: int
    page: int
    page_size: int


class AgentTaskStepItem(BaseModel):
    agent: str
    status: str
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None


class AgentTaskDetailResponse(BaseModel):
    task_id: str
    task_type: str
    status: str
    progress: int = 0
    input: dict[str, Any] = Field(default_factory=dict)
    agent_steps: List[AgentTaskStepItem] = Field(default_factory=list)
    output: dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None


class RetryAgentTaskRequest(BaseModel):
    retry_from_step: Optional[str] = None


class RetryAgentTaskResponse(BaseModel):
    new_task_id: str
    status: str
