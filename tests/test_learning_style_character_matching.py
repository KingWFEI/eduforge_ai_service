import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.learning_profile import StudentLearningProfile
from app.models.learning_style_character import LearningStyleCharacter, StudentStyleMatch
from app.services.learning_style_character_service import (
    get_student_learning_style_character,
    match_and_persist_character,
)


class LearningStyleCharacterMatchingTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        StudentLearningProfile.__table__.create(self.engine)
        LearningStyleCharacter.__table__.create(self.engine)
        StudentStyleMatch.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.profile = StudentLearningProfile(
            id="profile-1",
            student_id="7",
            learning_preferences_json=["视频", "图解"],
            summary="喜欢视频和图解学习",
            version=1,
            source="profile_dialogue",
        )
        self.character = LearningStyleCharacter(
            id="character-1",
            name="视觉探索者",
            code="visual_explorer",
            image_url="/uploads/visual.png",
            description="适合视频与图解学习",
            feature_tags=["视频", "图解"],
            suitable_methods=["可视化学习"],
            status="PUBLISHED",
            priority=10,
            version=1,
        )
        self.db.add_all([self.profile, self.character])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    @patch(
        "app.services.learning_style_character_service._match_with_deepseek",
        side_effect=RuntimeError("model unavailable"),
    )
    def test_match_is_persisted_at_profile_build_time(self, mocked_match):
        match = match_and_persist_character(
            self.db,
            student_id="7",
            profile=self.profile,
        )
        self.db.commit()

        self.assertIsNotNone(match)
        self.assertEqual(match.character_id, self.character.id)
        self.assertEqual(match.profile_version, 1)
        self.assertEqual(match.matching_source, "rule_fallback")
        self.assertEqual(self.db.query(StudentStyleMatch).count(), 1)
        mocked_match.assert_called_once()

        with patch(
            "app.services.learning_style_character_service._match_with_deepseek"
        ) as query_model:
            response = get_student_learning_style_character(self.db, student_id="7")
        self.assertEqual(response["status"], "MATCHED")
        self.assertEqual(response["character"]["id"], self.character.id)
        query_model.assert_not_called()

    def test_query_without_persisted_match_returns_matching_without_model_call(self):
        with patch(
            "app.services.learning_style_character_service._match_with_deepseek"
        ) as query_model:
            response = get_student_learning_style_character(self.db, student_id="7")

        self.assertEqual(response["status"], "MATCHING")
        self.assertFalse(response["profile_required"])
        self.assertIsNone(response["character"])
        query_model.assert_not_called()

    @patch(
        "app.services.learning_style_character_service._match_with_deepseek",
        side_effect=RuntimeError("model unavailable"),
    )
    def test_profile_version_update_replaces_existing_match(self, _mocked_match):
        first = match_and_persist_character(
            self.db,
            student_id="7",
            profile=self.profile,
        )
        self.db.commit()
        first_id = first.id

        self.profile.version = 2
        updated = match_and_persist_character(
            self.db,
            student_id="7",
            profile=self.profile,
        )
        self.db.commit()

        self.assertEqual(updated.id, first_id)
        self.assertEqual(updated.profile_version, 2)
        self.assertEqual(self.db.query(StudentStyleMatch).count(), 1)


if __name__ == "__main__":
    unittest.main()
