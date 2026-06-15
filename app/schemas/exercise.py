from typing import Any, List, Optional

from pydantic import BaseModel, Field


class ExerciseQuestionItem(BaseModel):
    question_id: str
    type: str
    question: str
    options: Optional[Any] = None
    related_knowledge: Optional[str] = None
    sort_order: int = 0


class ExerciseListResponse(BaseModel):
    resource_id: str
    exercise_set_id: str
    title: str
    course_id: str
    difficulty: Optional[str] = None
    questions: List[ExerciseQuestionItem] = Field(default_factory=list)
    total: int = 0


class ExerciseAnswerSubmitItem(BaseModel):
    question_id: str
    answer: Any = None


class ExerciseSubmitRequest(BaseModel):
    resource_id: Optional[str] = None
    exercise_set_id: Optional[str] = None
    answers: List[ExerciseAnswerSubmitItem] = Field(..., min_length=1)
    duration_seconds: Optional[int] = Field(None, ge=0)


class ExerciseAnswerResult(BaseModel):
    question_id: str
    is_correct: bool
    correct_answer: Optional[Any] = None
    student_answer: Optional[Any] = None
    explanation: Optional[str] = None
    related_knowledge: Optional[str] = None


class ExerciseSubmitResponse(BaseModel):
    submission_id: str
    resource_id: Optional[str] = None
    exercise_set_id: str
    score: float
    accuracy: float
    correct_count: int
    total_count: int
    weak_points: List[dict[str, Any]] = Field(default_factory=list)
    analysis: dict[str, Any] = Field(default_factory=dict)
    results: List[ExerciseAnswerResult] = Field(default_factory=list)


class WrongQuestionItem(BaseModel):
    wrong_id: str
    question_id: str
    course_id: Optional[str] = None
    knowledge_point: Optional[str] = None
    question: Optional[str] = None
    options: Optional[Any] = None
    correct_answer: Optional[Any] = None
    explanation: Optional[str] = None
    wrong_count: int = 0
    last_wrong_at: Optional[str] = None
    mastered: bool = False


class WrongQuestionListResponse(BaseModel):
    items: List[WrongQuestionItem] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
