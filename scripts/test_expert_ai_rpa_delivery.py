"""Retry semantics: popup and missing button must never duplicate a message."""
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("expert_ai_rpa", Path(__file__).with_name("expert_ai_rpa.py"))
rpa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rpa)

REQUEST = {"status": "pending_send", "request_id": "fixedid001", "round": 3,
           "draft_typed": True, "draft_started_at": rpa.now()}


class SendRetryTests(unittest.TestCase):
    def setUp(self):
        self.config = {**rpa.DEFAULTS, "calibrated": True}
        self.pending = ["APP-070"]

    def test_pending_send_can_retry_same_request(self):
        self.assertEqual(rpa.decision(REQUEST, self.config, self.pending, 4, 200, False),
                         "retry pending send")

    def test_pending_send_waits_for_user_idle(self):
        self.assertIn("user active",
                      rpa.decision(REQUEST, self.config, self.pending, 4, 23, False))

    def test_pending_send_respects_timeout(self):
        state = {**REQUEST, "draft_started_at": (
            datetime.now(timezone.utc) - timedelta(minutes=35)).isoformat()}
        self.assertEqual(rpa.decision(state, self.config, self.pending, 4, 200, False),
                         "pending send timed out")

    def test_pending_send_will_not_restart_when_paused(self):
        self.assertEqual(rpa.decision(REQUEST, self.config, self.pending, 4, 200, True),
                         "paused by PAUSE file")

    def test_popup_prevents_click_without_changing_checkpoint(self):
        with patch.object(rpa, "user_idle_seconds", return_value=200), \
             patch.object(rpa, "matching_windows", return_value=[88]), \
             patch.object(rpa.U, "ShowWindow", return_value=True), \
             patch.object(rpa.U, "SetForegroundWindow", return_value=False), \
             patch.object(rpa, "write_json") as save:
            with self.assertRaisesRegex(rpa.RpaDeferred, "Popup"):
                rpa.submit_pending_send(self.config, REQUEST)
            save.assert_not_called()

    def test_popup_hides_send_button_but_retains_draft(self):
        view = {"generating": False, "text_length": 170,
                "request_id_present": True, "send_button_enabled": False}
        with patch.object(rpa, "user_idle_seconds", return_value=200), \
             patch.object(rpa, "matching_windows", return_value=[88]), \
             patch.object(rpa.U, "ShowWindow", return_value=True), \
             patch.object(rpa.U, "SetForegroundWindow", return_value=True), \
             patch.object(rpa.U, "GetForegroundWindow", return_value=88), \
             patch.object(rpa, "composer_bounds", return_value=view), \
             patch.object(rpa.time, "sleep"), \
             patch.object(rpa, "send_text") as send_text, \
             patch.object(rpa, "write_json") as save:
            with self.assertRaisesRegex(rpa.RpaDeferred, "Send button"):
                rpa.submit_pending_send(self.config, REQUEST)
            send_text.assert_not_called()
            save.assert_not_called()

    def test_retry_invokes_send_with_same_id_exactly_once(self):
        view = {"generating": False, "text_length": 170,
                "request_id_present": True, "send_button_enabled": True}
        response = SimpleNamespace(returncode=0, stdout='{"invoked":true}', stderr="")
        with patch.object(rpa, "user_idle_seconds", return_value=200), \
             patch.object(rpa, "matching_windows", return_value=[88]), \
             patch.object(rpa.U, "ShowWindow", return_value=True), \
             patch.object(rpa.U, "SetForegroundWindow", return_value=True), \
             patch.object(rpa.U, "GetForegroundWindow", return_value=88), \
             patch.object(rpa, "composer_bounds", return_value=view), \
             patch.object(rpa.time, "sleep"), \
             patch.object(rpa.subprocess, "run", return_value=response) as run, \
             patch.object(rpa, "read_json", return_value=REQUEST), \
             patch.object(rpa, "write_json") as save:
            self.assertEqual(rpa.submit_pending_send(self.config, REQUEST), "invoked")
            self.assertEqual(run.call_count, 1)
            self.assertIn("fixedid001", run.call_args.args[0])
            self.assertEqual(save.call_args.args[1]["status"], "requested")
            self.assertEqual(save.call_args.args[1]["request_id"], "fixedid001")

    def test_empty_draft_never_retypes_same_message(self):
        view = {"generating": False, "text_length": 0,
                "request_id_present": False, "send_button_enabled": False}
        with patch.object(rpa, "user_idle_seconds", return_value=200), \
             patch.object(rpa, "matching_windows", return_value=[88]), \
             patch.object(rpa.U, "ShowWindow", return_value=True), \
             patch.object(rpa.U, "SetForegroundWindow", return_value=True), \
             patch.object(rpa.U, "GetForegroundWindow", return_value=88), \
             patch.object(rpa, "composer_bounds", return_value=view), \
             patch.object(rpa.time, "sleep"), \
             patch.object(rpa, "send_text") as send_text, \
             patch.object(rpa, "write_json") as save:
            self.assertEqual(rpa.submit_pending_send(self.config, REQUEST), "awaiting_ack")
            send_text.assert_not_called()
            self.assertEqual(save.call_args.args[1]["status"], "requested")

    def test_foreign_draft_never_overwritten(self):
        view = {"generating": False, "text_length": 100,
                "request_id_present": False, "send_button_enabled": True}
        with patch.object(rpa, "user_idle_seconds", return_value=200), \
             patch.object(rpa, "matching_windows", return_value=[88]), \
             patch.object(rpa.U, "ShowWindow", return_value=True), \
             patch.object(rpa.U, "SetForegroundWindow", return_value=True), \
             patch.object(rpa.U, "GetForegroundWindow", return_value=88), \
             patch.object(rpa, "composer_bounds", return_value=view), \
             patch.object(rpa.time, "sleep"), \
             patch.object(rpa, "write_json") as save:
            with self.assertRaises(rpa.RpaBlocked):
                rpa.submit_pending_send(self.config, REQUEST)
            save.assert_not_called()

    def test_already_requested_never_retries(self):
        state = {**REQUEST, "status": "requested", "requested_at": rpa.now()}
        self.assertEqual(rpa.decision(state, self.config, self.pending, 4, 200, False),
                         "awaiting GPT acknowledgement")


if __name__ == "__main__":
    unittest.main()
