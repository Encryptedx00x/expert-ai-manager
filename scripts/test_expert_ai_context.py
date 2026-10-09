"""Conversation-size hints: these are round estimates, never token measurements."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import expert_ai_context as context


class ContextTests(unittest.TestCase):
    def test_compact_prompt_keeps_request_id_once_and_stays_single_line(self):
        result = context.compact_message(
            "CONTINUAR CRM:\nRevisar estado e testes.", "abcdef123456"
        )
        self.assertIn("[request_id: abcdef123456]", result)
        self.assertEqual(result.count("[request_id:"), 1)
        self.assertNotIn("\n", result)
        self.assertIn("2 a 4 tarefas", result)
        self.assertIn("Preserve testes completos", result)

    def test_compact_mode_can_be_disabled(self):
        result = context.compact_message("CONTINUAR CRM", "abc", enabled=False)
        self.assertEqual(result, "CONTINUAR CRM [request_id: abc]")

    def test_new_conversation_starts_from_current_round(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "conversation-session.json"
            session = context.start_session(93, "Dev CRM 2", known_new=True, path=file)
            self.assertEqual(session["start_round"], 93)
            self.assertTrue(session["baseline_known"])
            self.assertEqual(context.read_session(file), session)
            self.assertEqual(context.context_budget(93, session)["level"], "ok")
            self.assertEqual(context.context_budget(97, session)["rounds"], 4)

    def test_soft_warning_and_strong_advice_do_not_block(self):
        data = {"start_round": 93, "baseline_known": True}
        self.assertEqual(context.context_budget(97, data)["level"], "ok")
        self.assertEqual(context.context_budget(98, data)["level"], "suggest")
        self.assertEqual(context.context_budget(101, data)["level"], "recommend")
        self.assertIn("migrar", context.context_budget(105, data)["label"])
        self.assertEqual(context.context_budget(105, data)["rounds"], 12)

    def test_existing_conversation_has_unknown_prior_history(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "conversation-session.json"
            session = context.initialize_if_missing(93, "Old chat", path=file)
            self.assertFalse(session["baseline_known"])
            self.assertEqual(context.context_budget(120, session)["level"], "unknown")
            self.assertIn("desconhecido", context.context_budget(120, session)["label"])
            self.assertEqual(context.initialize_if_missing(120, "changed title", path=file),
                             session)

    def test_invalid_marker_is_not_misreported_as_safe(self):
        self.assertEqual(context.context_budget(20, {})["level"], "unknown")
        self.assertEqual(context.context_budget(20, {"start_round": -1})["level"], "unknown")
        self.assertEqual(context.context_budget(19, {"start_round": 20})["level"], "unknown")
        with self.assertRaisesRegex(ValueError, "threshold"):
            context.context_budget(20, {"start_round": 1}, soft_rounds=8,
                                   strong_rounds=8)

    def test_corrupted_session_falls_back_to_unknown_without_crashing(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "conversation-session.json"
            file.write_text("{broken json", encoding="utf-8")
            self.assertEqual(context.read_session(file), {})
            self.assertEqual(context.context_budget(93, context.read_session(file))["level"],
                             "unknown")

    def test_writing_session_does_not_touch_checkpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            state = project / "chat-state.json"
            state.write_text('{"status":"running","request_id":"unmodified"}', encoding="utf-8")
            context.start_session(11, "New chat", known_new=True,
                                  path=project / "conversation-session.json")
            self.assertEqual(state.read_text(encoding="utf-8"),
                             '{"status":"running","request_id":"unmodified"}')


if __name__ == "__main__":
    unittest.main()
