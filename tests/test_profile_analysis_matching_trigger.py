import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.learning_profile import StudentLearningProfile
from app.models.profile_analysis import ProfileAnalysis
from app.services.profile_analysis_service import run_profile_analysis


class ProfileAnalysisMatchingTriggerTests(unittest.IsolatedAsyncioTestCase):
    async def test_onboarding_profile_save_triggers_character_match(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        StudentLearningProfile.__table__.create(engine)
        ProfileAnalysis.__table__.create(engine)
        Session = sessionmaker(bind=engine)
        db = Session()

        agent = MagicMock()
        agent.run.return_value = {
            "profile": {
                "learning_preferences": ["视频"],
                "cognitive_traits": ["视觉型"],
                "learning_habits": ["制定计划"],
                "motivation_factors": ["提升能力"],
                "general_strengths": ["理解图示较快"],
                "general_challenges": ["容易分心"],
                "preferred_pace": "稳步",
                "available_time": {"minutes_per_day": 60},
                "summary": "偏好视频学习，能够按计划稳步推进。",
                "analysis": "画像分析",
                "learning_suggestion": "学习建议",
                "profile_dimensions": {},
                "evidence": [],
                "confidence": {"overall": 0.9},
            },
            "agent_used": "test",
            "skill_used": True,
            "skill_name": "test",
            "llm_used": False,
            "llm_provider": None,
            "llm_error": None,
        }

        try:
            with (
                patch(
                    "app.services.profile_analysis_service.SessionLocal",
                    return_value=db,
                ),
                patch(
                    "app.services.profile_analysis_service.OnboardingProfileAgent",
                    return_value=agent,
                ),
                patch(
                    "app.services.profile_analysis_service.match_and_persist_character"
                ) as match,
            ):
                await run_profile_analysis(
                    analysis_id="missing-analysis",
                    submission_id="missing-submission",
                    user_id=7,
                    student_id="7",
                    answers={"q1": "视频"},
                )

            verify_db = Session()
            try:
                profile = verify_db.query(StudentLearningProfile).one()
                self.assertEqual(profile.student_id, "7")
                self.assertEqual(profile.version, 1)
                match.assert_called_once()
                call = match.call_args.kwargs
                self.assertEqual(call["student_id"], "7")
                self.assertEqual(call["profile"].id, profile.id)
            finally:
                verify_db.close()
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
