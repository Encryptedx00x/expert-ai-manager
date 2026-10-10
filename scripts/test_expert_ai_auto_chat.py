"""Offline regression cases for the guarded autonomous conversation switch."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import expert_ai_auto_chat as auto
import expert_ai_context as context
import expert_ai_rpa as rpa


class ConversationWarningTests(unittest.TestCase):
    def test_explicit_conversation_limit(self):
        self.assertEqual(auto.classify_visible_warnings([
            "This conversation has reached its maximum length. Start a new chat."
        ]), "conversation_length")

    def test_portuguese_conversation_limit(self):
        self.assertEqual(auto.classify_visible_warnings([
            "Esta conversa atingiu o limite de tamanho."
        ]), "conversation_length")

    def test_timeout_can_prepare_recovery(self):
        self.assertEqual(auto.classify_visible_warnings([
            "Message delivery timed out. Please try again."
        ]), "delivery_timeout")

    def test_generic_timeout_does_not_count(self):
        self.assertIsNone(auto.classify_visible_warnings(["A request took a long time"]))

    def test_account_limits_override_conversation_warnings(self):
        self.assertEqual(auto.classify_visible_warnings([
            "Message delivery timed out. Please try again.",
            "You've reached your limit of messages for your plan."
        ]), "account_limit")

    def test_usage_not_treated_as_conversation_limit(self):
        self.assertEqual(auto.classify_visible_warnings([
            "Too many requests. Please try again later."
        ]), "account_limit")

    def test_mentions_in_development_instruction_not_triggered(self):
        self.assertIsNone(auto.classify_visible_warnings([
            "CONTINUAR CRM: Review checkpoint, tests, and Git diff."
        ]))

    def test_navigation_inspection_never_attempts_click(self):
        fake_result = SimpleNamespace(
            returncode=0, stdout='{"url":"https://chatgpt.com/c/abc","invoked":false}',
            stderr="")
        with patch.object(auto.subprocess, "run", return_value=fake_result) as runner:
            answer = auto.browser_navigation(Path("safe.ps1"), 123, action="inspect")
        self.assertFalse(answer["invoked"])
        args = runner.call_args.args[0]
        self.assertIn("inspect", args)
        self.assertNotIn("-InvokeSend", args)

    def test_invalid_browser_navigation_action_rejected(self):
        with self.assertRaisesRegex(ValueError, "operation"):
            auto.browser_navigation(Path("safe.ps1"), 123, action="force-send")


class HandoffPolicyTests(unittest.TestCase):
    def setUp(self):
        self.state = {"status": "ready", "round": 108, "request_id": "preserved"}
        self.session = {"start_round": 100, "baseline_known": True}
        self.config = {"automatic_conversation_handoff": True,
                       "handoff_after_rounds": 8}

    def verdict(self, **kw):
        config = {**self.config, **kw.pop("config", {})}
        return context.handoff_policy(
            kw.pop("state", self.state), config,
            kw.pop("session", self.session),
            pending_count=kw.pop("pending_count", 2),
            paused=kw.pop("paused", False),
            migration_pending=kw.pop("migration_pending", False),
            limit_hold=kw.pop("limit_hold", False),
        )

    def test_exact_threshold_prepares(self):
        self.assertTrue(self.verdict()["should_prepare"])
        self.assertEqual(self.verdict()["rounds"], 8)

    def test_below_threshold_keeps_working(self):
        self.assertFalse(self.verdict(state={**self.state, "round": 107})["should_prepare"])

    def test_no_automatic_handoff_during_running_or_pending(self):
        for name in ("running", "pending_send", "requested", "blocked"):
            self.assertFalse(self.verdict(state={**self.state, "status": name})["should_prepare"])

    def test_pause_limit_migration_and_no_tasks_block(self):
        for scenario in ({"paused": True}, {"limit_hold": True},
                         {"migration_pending": True}, {"pending_count": 0}):
            self.assertFalse(self.verdict(**scenario)["should_prepare"])

    def test_invalid_unknown_baseline_never_triggers(self):
        self.assertFalse(self.verdict(session={})["should_prepare"])
        self.assertFalse(self.verdict(session={"start_round": 100,
                                              "baseline_known": False})["should_prepare"])
        self.assertFalse(self.verdict(session={"start_round": 200,
                                              "baseline_known": True})["should_prepare"])

    def test_disabled_and_invalid_thresholds(self):
        self.assertFalse(self.verdict(config={"automatic_conversation_handoff": False})["should_prepare"])
        for value in (3, 101, "8", True):
            self.assertFalse(self.verdict(config={"handoff_after_rounds": value})["should_prepare"])


class BrowserGuardTests(unittest.TestCase):
    def test_migration_stays_paused_without_exact_original_window(self):
        handoff = {
            "phase": "awaiting_new_chat", "trigger": "delivery_timeout",
            "request_id": "req1", "round": 11, "previous_conversation_url": "https://chatgpt.com/c/old",
        }
        cfg = {**rpa.DEFAULTS, "process_name": "brave.exe"}
        state = {"status": "ready", "request_id": "req1", "round": 11}
        with patch.object(rpa, "migration_status", return_value=handoff), \
             patch.object(rpa, "PAUSE", SimpleNamespace(exists=lambda: True)), \
             patch.object(rpa, "LIMIT", SimpleNamespace(exists=lambda: False)), \
             patch.object(rpa, "pace_status", return_value={"allowed": True}), \
             patch.object(rpa, "read_json", return_value=rpa.new_ledger()), \
             patch.object(rpa, "browsers_at_url", return_value=[]), \
             patch.object(rpa, "inspect_browser") as inspect:
            result = rpa.auto_open_new_chat(cfg, state, 6.0, 150)
        self.assertIn("exact original browser", result)
        inspect.assert_not_called()

    def test_pending_draft_blocks_new_chat_even_with_timeout(self):
        handoff = {
            "phase": "awaiting_new_chat", "trigger": "delivery_timeout",
            "request_id": "req1", "round": 11, "previous_conversation_url": "https://chatgpt.com/c/old",
        }
        cfg = {**rpa.DEFAULTS, "process_name": "brave.exe"}
        state = {"status": "pending_send", "request_id": "req1", "round": 11}
        with patch.object(rpa, "migration_status", return_value=handoff), \
             patch.object(rpa, "PAUSE", SimpleNamespace(exists=lambda: True)):
            self.assertEqual(rpa.auto_open_new_chat(cfg, state, 6, 200),
                             "migration safety block")

    def test_successful_new_chat_bootstrap_is_sent_exactly_once(self):
        import expert_ai_control as control
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "chat-migration.json"
            pause = Path(directory) / "PAUSE"
            limit = Path(directory) / "LIMIT"
            usage = Path(directory) / "rpa-usage.json"
            pause.touch()
            handoff = {
                "phase": "awaiting_new_chat", "trigger": "round_budget",
                "migration_id": "0123456789abcdef",
                "request_id": "req1", "round": 11,
                "previous_conversation_url": "https://chatgpt.com/c/old",
                "previous_window_title": "Old - Brave",
            }
            control.atomic_save(marker, handoff)
            config = {**rpa.DEFAULTS, "process_name": "brave.exe",
                      "conversation_url": handoff["previous_conversation_url"]}
            state = {"status": "ready", "request_id": "req1", "round": 11}
            before = {"url": handoff["previous_conversation_url"],
                      "new_chat_count": 1, "composer_count": 1}
            snapshots = [
                {"invoked": True},
                {"url": "https://chatgpt.com", "composer_count": 1},
                {"invoked": True},
            ]
            with patch.object(rpa, "MIGRATION", marker), \
                 patch.object(rpa, "PAUSE", pause), \
                 patch.object(rpa, "LIMIT", limit), \
                 patch.object(rpa, "USAGE", usage), \
                 patch.object(rpa, "migration_status", side_effect=lambda: control.load(marker)), \
                 patch.object(rpa, "pace_status", return_value={"allowed": True}), \
                 patch.object(rpa, "browsers_at_url", return_value=[(42, before)]), \
                 patch.object(rpa, "inspect_browser", side_effect=snapshots) as inspect, \
                 patch.object(rpa.U, "GetForegroundWindow", return_value=42), \
                 patch.object(rpa, "user_idle_seconds", return_value=180), \
                 patch.object(rpa, "composer_bounds", return_value={
                     "x": 100, "y": 100, "width": 360, "height": 40,
                     "text_length": 0, "generating": False,
                 }), \
                 patch.object(rpa, "click_at"), \
                 patch.object(rpa, "send_text") as send, \
                 patch.object(rpa.time, "sleep"):
                answer = rpa.auto_open_new_chat(config, state, 6.0, 180)
                self.assertIn("bootstrap sent", answer)
                send.assert_called_once()
                inspect.assert_called()
            after = control.load(marker)
            self.assertEqual(after["phase"], "bootstrap_sent")
            self.assertEqual(after["request_id"], "req1")
            self.assertEqual(after["round"], 11)
            self.assertEqual(after["initial_new_url"], "https://chatgpt.com")
            self.assertTrue(pause.exists())
            self.assertEqual(len(control.load(usage)["attempts"]), 1)
            # A second pass must never click again once a draft was sent.
            with patch.object(rpa, "MIGRATION", marker), \
                 patch.object(rpa, "migration_status", side_effect=lambda: control.load(marker)), \
                 patch.object(rpa, "inspect_browser") as inspect:
                result = rpa.auto_open_new_chat(config, state, 6.0, 180)
                self.assertIn("manual conversation migration", result)
                inspect.assert_not_called()

    def test_limit_blocks_automatic_migration(self):
        handoff = {
            "phase": "awaiting_new_chat", "trigger": "round_budget",
            "request_id": "req1", "round": 11,
        }
        with patch.object(rpa, "migration_status", return_value=handoff), \
             patch.object(rpa, "PAUSE", SimpleNamespace(exists=lambda: True)), \
             patch.object(rpa, "LIMIT", SimpleNamespace(exists=lambda: True)), \
             patch.object(rpa, "inspect_browser") as inspect:
            result = rpa.auto_open_new_chat(rpa.DEFAULTS, {
                "status": "ready", "request_id": "req1", "round": 11
            }, 6.0, 200)
        self.assertEqual(result, "migration safety block")
        inspect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
