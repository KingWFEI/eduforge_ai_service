# 集中导入所有 ORM 模型，确保 Base.metadata 能发现所有表
from app.models.user import User,UserOnboardingStatus
from app.models.verification_code import VerificationCode
from app.models.login_log import LoginLog
from app.models.course import Course
from app.models.course_structure import CourseChapter, KnowledgePoint, CourseDocument, KnowledgeChunk, VectorIndexRecord
from app.models.onboarding import OnboardingSurvey, OnboardingQuestion, OnboardingOption, OnboardingSubmission, OnboardingAnswer
from app.models.student_profile import StudentProfile
from app.models.learning_profile import StudentLearningProfile, StudentDomainCompetency, StudentLearningContext
from app.models.profile_analysis import ProfileVersion, ProfileAnalysis
from app.models.resource_agent import LearningResource, ResourceReference, ResourceFeedback, ResourceFavorite, ResourceReview, ResourceGenerationTask, AgentTask, AgentTaskStep
from app.models.chat import ChatSession, ChatMessage, ChatMessageSource, ChatFeedback
from app.models.learning_path import LearningPath, LearningPathTask
from app.models.exercise import ExerciseSet, ExerciseQuestion, ExerciseSubmission, ExerciseAnswer, WrongQuestion
from app.models.evaluation import EvaluationReport, MasteryRecord, WeakPointRecord
from app.models.other import StudyRecord, UserNotification, DashboardDailyStat, SystemSetting, PromptTemplate
from app.models.profile_dialogue_messages import ProfileDialogueMessage
from app.models.profile_dialogue_sessions import ProfileDialogueSession
from app.models.column_comments import apply_column_comments
from app.db.base import Base


apply_column_comments(Base.metadata)


__all__ = [
    "User",
    "UserOnboardingStatus",
    "VerificationCode",
    "LoginLog",
    "Course",
    "CourseChapter",
    "KnowledgePoint",
    "CourseDocument",
    "KnowledgeChunk",
    "VectorIndexRecord",
    "OnboardingSurvey",
    "OnboardingQuestion",
    "OnboardingOption",
    "OnboardingSubmission",
    "OnboardingAnswer",
    "StudentProfile",
    "StudentLearningProfile",
    "StudentDomainCompetency",
    "StudentLearningContext",
    "ProfileVersion",
    "ProfileAnalysis",
    "LearningResource",
    "ResourceReference",
    "ResourceFeedback",
    "ResourceFavorite",
    "ResourceReview",
    "ResourceGenerationTask",
    "AgentTask",
    "AgentTaskStep",
    "ChatSession",
    "ChatMessage",
    "ChatMessageSource",
    "ChatFeedback",
    "LearningPath",
    "LearningPathTask",
    "ExerciseSet",
    "ExerciseQuestion",
    "ExerciseSubmission",
    "ExerciseAnswer",
    "WrongQuestion",
    "EvaluationReport",
    "MasteryRecord",
    "WeakPointRecord",
    "StudyRecord",
    "UserNotification",
    "DashboardDailyStat",
    "SystemSetting",
    "PromptTemplate",
    "ProfileDialogueMessage",
    "ProfileDialogueSession",
]
