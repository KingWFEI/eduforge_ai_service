import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.profile_dialogue import (
    create_profile_dialogue_session,
    get_dialogue_session_messages,
)
from app.models.profile_dialogue_messages import ProfileDialogueMessage
from app.models.profile_dialogue_sessions import ProfileDialogueSession
from app.schemas.profile_dialogue import CreateProfileDialogueSessionRequest
from app.services.profile_dialogue_presenter import build_profile_dialogue_display


class ProfileDialoguePresenterTests(unittest.TestCase):
    def test_display_is_flattened_and_localized(self):
        display = build_profile_dialogue_display(
            current_slot="learning_style",
            missing_slots=["learning_habits", "motivation"],
            extracted_fields={
                "learning_style": {"preferred_content_formats": ["video"]}
            },
        )

        self.assertEqual(display["current_slot"], "学习偏好")
        self.assertEqual(display["missing_slots"], ["学习习惯", "学习动机"])
        self.assertEqual(
            display["fields"],
            [
                {
                    "key": "learning_style.preferred_content_formats",
                    "label": "偏好的内容形式",
                    "value": "视频",
                }
            ],
        )


class ProfileDialogueEndpointDisplayTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        ProfileDialogueSession.__table__.create(self.engine)
        ProfileDialogueMessage.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.current_user = SimpleNamespace(id=7)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    async def test_create_and_history_share_display_contract(self):
        created = create_profile_dialogue_session(
            CreateProfileDialogueSessionRequest(),
            db=self.db,
            current_user=self.current_user,
        )["data"]

        self.assertEqual(created["current_slot"], "learning_style")
        self.assertEqual(created["missing_slots"][0], "learning_style")
        self.assertEqual(created["display"]["current_slot"], "学习偏好")
        self.assertEqual(created["display"]["missing_slots"][0], "学习偏好")
        self.assertEqual(created["display"]["fields"], [])

        history = await get_dialogue_session_messages(
            created["session_id"],
            db=self.db,
            current_user=self.current_user,
        )
        data = history["data"]
        self.assertEqual(data["missing_slots"][0], "learning_style")
        self.assertEqual(data["display"]["current_slot"], "学习偏好")
        self.assertEqual(data["display"]["missing_slots"][0], "学习偏好")
        self.assertEqual(data["display"]["fields"], [])


if __name__ == "__main__":
    unittest.main()
