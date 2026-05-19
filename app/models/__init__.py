# 集中导入所有 ORM 模型，确保 Base.metadata 能发现所有表
from app.models.user import User
from app.models.course import Course, CourseFile
from app.models.onboarding import OnboardingSurvey, OnboardingQuestion, OnboardingOption, OnboardingSubmission
from app.models.student_profile import StudentProfile
from app.models.profile_analysis import ProfileAnalysis

__all__ = [
    "User",
    "Course",
    "CourseFile",
    "OnboardingSurvey",
    "OnboardingQuestion",
    "OnboardingOption",
    "OnboardingSubmission",
    "StudentProfile",
    "ProfileAnalysis",
]
