import unittest

from pydantic import ValidationError

from app.constants.profile_dialogue import localize_profile_dialogue_slots
from app.schemas.profile_dialogue import SendProfileDialogueMessageRequest


class ProfileDialogueSchemaTests(unittest.TestCase):
    def test_content_alias_and_client_message_id_are_supported(self):
        payload = SendProfileDialogueMessageRequest(
            session_id=1,
            content="  我喜欢视频课程  ",
            client_message_id="request-uuid",
        )
        self.assertEqual(payload.message, "我喜欢视频课程")
        self.assertEqual(payload.client_message_id, "request-uuid")

    def test_blank_message_is_rejected(self):
        with self.assertRaises(ValidationError):
            SendProfileDialogueMessageRequest(session_id=1, content="  ")

    def test_missing_slots_are_localized_for_client_response(self):
        self.assertEqual(
            localize_profile_dialogue_slots(
                [
                    "learning_style",
                    "learning_habits",
                    "motivation",
                    "strengths_challenges",
                    "pace_and_time",
                ]
            ),
            [
                "学习偏好",
                "学习习惯",
                "学习动机",
                "优势与挑战",
                "学习节奏与时间",
            ],
        )


if __name__ == "__main__":
    unittest.main()
