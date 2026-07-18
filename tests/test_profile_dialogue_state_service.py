import unittest

from app.agents.dialogue_agent.DialogueGuideAgent import DialogueGuideAgent
from app.services.profile_dialogue_state_service import ProfileDialogueStateService


class ProfileDialogueStateServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = ProfileDialogueStateService()

    def test_global_updates_merge_multiple_slots_and_advance(self):
        updates = {
            "learning_style": {"preferred_content_formats": ["视频", "案例"]},
            "motivation": {"primary_learning_goal": "准备考试"},
            "pace_and_time": {
                "preferred_learning_period": "晚上",
                "session_duration": 60,
            },
        }
        profile = self.service.merge_profile_fields({}, updates)
        action, _ = self.service.build_dialogue_action(
            current_slot="learning_style",
            profile_data=profile,
            dialogue_state={},
            relevance_result={"is_relevant": True},
            slot_updates=updates,
            user_message="我喜欢视频和案例，晚上学一小时，主要为了考试。",
        )

        self.assertEqual(profile["motivation"]["primary_learning_goal"], "准备考试")
        self.assertEqual(profile["pace_and_time"]["session_duration"], 60)
        self.assertEqual(action.action, "advance")
        self.assertEqual(action.next_slot, "learning_habits")
        self.assertEqual(action.question_field, "planning_habit")

    def test_completed_future_slot_is_skipped_automatically(self):
        profile = self.service.merge_profile_fields(
            {},
            {
                "learning_style": {"preferred_content_formats": ["图解"]},
                "learning_habits": {"planning_habit": "会制定计划"},
                "motivation": {"primary_learning_goal": "准备考试"},
            },
        )
        action, _ = self.service.build_dialogue_action(
            current_slot="learning_style",
            profile_data=profile,
            dialogue_state={},
            relevance_result={"is_relevant": True},
            slot_updates=profile,
            user_message="",
        )

        self.assertEqual(action.next_slot, "strengths_challenges")
        self.assertEqual(action.question_field, "learning_strengths")

    def test_same_field_is_not_asked_more_than_once(self):
        state = {
            "asked_fields": {
                "learning_style.preferred_content_formats": {
                    "count": 1,
                    "last_question": "你更喜欢视频、图文还是案例？",
                }
            },
            "skipped_fields": [],
            "last_question_field": "learning_style.preferred_content_formats",
        }
        profile = self.service.merge_profile_fields({}, {})
        action, new_state = self.service.build_dialogue_action(
            current_slot="learning_style",
            profile_data=profile,
            dialogue_state=state,
            relevance_result={"is_relevant": False},
            slot_updates={},
            user_message="都可以",
        )

        self.assertIn(
            "learning_style.preferred_content_formats",
            new_state["skipped_fields"],
        )
        self.assertEqual(action.question_field, "theory_practice_preference")
        self.assertNotEqual(action.question_field, "preferred_content_formats")

    def test_refused_field_is_skipped_and_next_question_selected(self):
        state = {
            "asked_fields": {
                "learning_style.preferred_content_formats": {
                    "count": 1,
                    "last_question": "你更喜欢视频、图文还是案例？",
                }
            },
            "skipped_fields": [],
            "last_question_field": "learning_style.preferred_content_formats",
        }
        action, new_state = self.service.build_dialogue_action(
            current_slot="learning_style",
            profile_data=self.service.merge_profile_fields({}, {}),
            dialogue_state=state,
            relevance_result={"is_relevant": False},
            slot_updates={},
            user_message="这个我不想说",
        )

        self.assertIn(
            "learning_style.preferred_content_formats",
            new_state["skipped_fields"],
        )
        self.assertEqual(action.question_field, "theory_practice_preference")

    def test_invalid_values_do_not_complete_slot(self):
        for value in (None, "", [], "unknown", "不知道", "未提供"):
            with self.subTest(value=value):
                self.assertFalse(self.service.has_valid_value(value))

    def test_nested_or_unknown_llm_fields_are_removed(self):
        sanitized = self.service.sanitize_slot_updates(
            {
                "learning_style": {
                    "preferred_content_formats": [
                        "video",
                        {"unexpected": "object"},
                        ["nested"],
                    ],
                    "unknown_field": "must-not-pass",
                    "cognitive_preference": {"arbitrary": {"nested": True}},
                },
                "unknown_slot": {"anything": "must-not-pass"},
            }
        )

        self.assertEqual(
            sanitized,
            {"learning_style": {"preferred_content_formats": ["video"]}},
        )

    def test_all_sufficient_slots_produce_confirm_action(self):
        profile = self.service.merge_profile_fields(
            {},
            {
                "learning_style": {"preferred_content_formats": ["视频"]},
                "learning_habits": {"planning_habit": "会计划"},
                "motivation": {"primary_learning_goal": "考试"},
                "strengths_challenges": {"learning_strengths": "理解快"},
                "pace_and_time": {"available_learning_time": "每天一小时"},
            },
        )
        action, _ = self.service.build_dialogue_action(
            current_slot="pace_and_time",
            profile_data=profile,
            dialogue_state={},
            relevance_result={"is_relevant": True},
            slot_updates=profile,
            user_message="每天一小时",
        )
        self.assertEqual(action.action, "confirm_profile")
        self.assertEqual(action.next_slot, "confirm")


class FakeTextLLM:
    def __init__(self, reply):
        self.reply = reply

    async def generate_text(self, **kwargs):
        return self.reply


class RaisingTextLLM:
    async def generate_text(self, **kwargs):
        raise RuntimeError("LLM 返回内容为空")


class DialogueGuideRuleTests(unittest.IsolatedAsyncioTestCase):
    async def test_llm_error_uses_deterministic_fallback(self):
        agent = DialogueGuideAgent(RaisingTextLLM())
        reply = await agent.generate_reply(
            {
                "dialogue_action": {
                    "action": "recover_from_irrelevant",
                    "question_field": "review_habit",
                    "question_text": "你会定期复习学过的内容吗？",
                }
            }
        )

        self.assertEqual(reply, "这个话题稍后也可以聊。你会定期复习学过的内容吗？")

    async def test_long_multi_question_reply_falls_back_to_one_short_question(self):
        agent = DialogueGuideAgent(
            FakeTextLLM(
                "为了更好地了解你，请详细介绍学习计划好吗？另外你会复习吗？还会记笔记吗？"
            )
        )
        reply = await agent.generate_reply(
            {
                "dialogue_action": {
                    "action": "advance",
                    "question_field": "planning_habit",
                    "question_text": "平时学习会提前做计划吗？",
                }
            }
        )

        self.assertLessEqual(len(reply), 45)
        self.assertEqual(reply.count("？") + reply.count("?"), 1)
        self.assertNotIn("为了更好地了解你", reply)

    async def test_twenty_replies_stay_within_length_and_question_limits(self):
        action = {
            "action": "follow_up",
            "question_field": "review_habit",
            "question_text": "你会定期复习学过的内容吗？",
        }
        candidates = [
            "好的？",
            "明白了，你会复习吗？你会记笔记吗？",
            "为了更好地了解你，你会定期复习学过的内容吗？",
            "这是一段明显过长的回复，它会反复解释用户刚刚说过的信息，并且继续添加很多不必要的内容。你会复习吗？",
            "知道了，我们继续补充这一点。你会定期复习学过的内容吗？",
        ] * 4
        for candidate in candidates:
            agent = DialogueGuideAgent(FakeTextLLM(candidate))
            reply = await agent.generate_reply({"dialogue_action": action})
            self.assertGreaterEqual(len(reply), 20)
            self.assertLessEqual(len(reply), 45)
            self.assertLessEqual(reply.count("？") + reply.count("?"), 1)


if __name__ == "__main__":
    unittest.main()
