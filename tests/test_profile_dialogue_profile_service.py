import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.learning_profile import StudentLearningProfile
from app.models.learning_style_character import LearningStyleCharacter, StudentStyleMatch
from app.models.profile_analysis import ProfileVersion
from app.models.profile_dialogue_sessions import ProfileDialogueSession
from app.models.user import User, UserOnboardingStatus
from app.services.learning_style_character_service import (
    get_student_learning_style_character,
)
from app.services.profile_dialogue_profile_service import confirm_dialogue_profile


class ProfileDialogueProfileServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        for table in (
            User.__table__,
            UserOnboardingStatus.__table__,
            StudentLearningProfile.__table__,
            ProfileVersion.__table__,
            ProfileDialogueSession.__table__,
            LearningStyleCharacter.__table__,
            StudentStyleMatch.__table__,
        ):
            table.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.user = User(
            username="dialogue_student",
            password_hash="hashed",
            name="对话学生",
            role="student",
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _create_ready_session(self, content_format="video"):
        session = ProfileDialogueSession(
            student_id=self.user.id,
            scene="initial_profile",
            status="ready_to_confirm",
            current_slot="confirm",
            collected_slots_json=[
                "learning_style",
                "learning_habits",
                "motivation",
                "strengths_challenges",
                "pace_and_time",
            ],
            missing_slots_json=[],
            extracted_fields_json={
                "learning_style": {
                    "preferred_content_formats": [content_format],
                    "cognitive_preference": "visual",
                },
                "learning_habits": {"planning_habit": "会制定计划"},
                "motivation": {"primary_learning_goal": "提升能力"},
                "strengths_challenges": {
                    "learning_strengths": "理解图示较快",
                    "learning_challenges": "容易分心",
                },
                "pace_and_time": {
                    "preferred_learning_pace": "steady",
                    "available_learning_time": "每天一小时",
                    "preferred_learning_period": "evening",
                    "session_duration": 60,
                },
            },
            dialogue_state={},
            profile_preview_json={
                "summary": "偏好视频与图示，学习计划较稳定。",
                "confidence": 0.9,
            },
            progress=1.0,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def test_confirm_creates_formal_profile_and_clears_profile_required(self):
        session = self._create_ready_session()

        result = confirm_dialogue_profile(
            self.db,
            session_id=session.id,
            student_id=self.user.id,
        )

        profile = self.db.query(StudentLearningProfile).one()
        self.db.refresh(session)
        onboarding = self.db.query(UserOnboardingStatus).one()
        version = self.db.query(ProfileVersion).one()

        self.assertEqual(result["profile_id"], profile.id)
        self.assertEqual(result["learning_style_character"]["status"], "MATCHING")
        self.assertEqual(session.status, "completed")
        self.assertEqual(session.profile_id, profile.id)
        self.assertEqual(profile.student_id, str(self.user.id))
        self.assertEqual(profile.learning_preferences_json, ["video"])
        self.assertEqual(profile.cognitive_traits_json, ["visual"])
        self.assertEqual(profile.preferred_pace, "steady")
        self.assertEqual(profile.available_time_json["session_duration"], 60)
        self.assertEqual(profile.source, "profile_dialogue")
        self.assertEqual(version.profile_id, profile.id)
        self.assertEqual(onboarding.status, "completed")
        self.assertFalse(onboarding.need_onboarding)
        self.assertEqual(onboarding.profile_id, profile.id)

        character_result = get_student_learning_style_character(
            self.db,
            student_id=str(self.user.id),
        )
        self.assertEqual(character_result["status"], "MATCHING")
        self.assertFalse(character_result["profile_required"])

    def test_confirm_is_idempotent_and_new_session_updates_profile_version(self):
        first_session = self._create_ready_session("video")
        first = confirm_dialogue_profile(
            self.db,
            session_id=first_session.id,
            student_id=self.user.id,
        )
        replay = confirm_dialogue_profile(
            self.db,
            session_id=first_session.id,
            student_id=self.user.id,
        )
        self.assertEqual(replay["profile_id"], first["profile_id"])
        self.assertEqual(replay["profile_version"], 1)
        self.assertEqual(self.db.query(ProfileVersion).count(), 1)

        second_session = self._create_ready_session("text")
        updated = confirm_dialogue_profile(
            self.db,
            session_id=second_session.id,
            student_id=self.user.id,
        )
        profile = self.db.query(StudentLearningProfile).one()
        self.assertEqual(updated["profile_id"], first["profile_id"])
        self.assertEqual(updated["profile_version"], 2)
        self.assertEqual(profile.learning_preferences_json, ["text"])
        self.assertEqual(self.db.query(ProfileVersion).count(), 2)

    def test_legacy_completed_session_without_profile_is_repaired(self):
        session = self._create_ready_session()
        session.status = "completed"
        session.profile_id = None
        self.db.commit()

        result = confirm_dialogue_profile(
            self.db,
            session_id=session.id,
            student_id=self.user.id,
        )

        self.db.refresh(session)
        self.assertTrue(result["profile_id"])
        self.assertEqual(session.profile_id, result["profile_id"])
        self.assertEqual(self.db.query(StudentLearningProfile).count(), 1)


if __name__ == "__main__":
    unittest.main()
