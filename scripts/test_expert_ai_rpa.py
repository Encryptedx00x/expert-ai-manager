"""Unit tests for the RPA state machine. Never touches the ChatGPT UI."""
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("expert_ai_rpa", Path(__file__).with_name("expert_ai_rpa.py"))
rpa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rpa)


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.config = {**rpa.DEFAULTS, "calibrated": True}
        self.pending = ["APP-070"]

    def test_ready_with_idle_pc_sends(self):
        with patch.object(rpa, "read_json", return_value=rpa.new_ledger()):
            self.assertEqual(rpa.decision({"status": "ready"}, self.config, self.pending, 5.1, 200, False), "send")

    def test_blocks_if_user_is_active(self):
        result = rpa.decision({"status": "ready"}, self.config, self.pending, 5.1, 12, False)
        self.assertIn("user active", result)

    def test_blocks_if_low_memory(self):
        result = rpa.decision({"status": "ready"}, self.config, self.pending, 1.2, 200, False)
        self.assertIn("low RAM", result)

    def test_waits_for_running_and_requested(self):
        self.assertEqual(
            rpa.decision({"status": "running", "started_at": rpa.now()},
                         self.config, self.pending, 5, 200, False), "running"
        )
        self.assertEqual(
            rpa.decision({"status": "requested", "requested_at": rpa.now()},
                         self.config, self.pending, 5, 200, False),
            "awaiting GPT acknowledgement"
        )

    def test_halts_on_stale_unacknowledged_request(self):
        old = (datetime.now(timezone.utc) - timedelta(minutes=60)).isoformat()
        result = rpa.decision({"status": "requested", "requested_at": old},
                              self.config, self.pending, 5, 200, False)
        self.assertEqual(result, "missing GPT acknowledgement")

    def test_safe_mode_denies_send_until_minimum_gap(self):
        old = (datetime.now(timezone.utc) - timedelta(minutes=4)).isoformat()
        ledger = {"schema_version": 1,
                  "attempts": [{"request_id": "prior", "at": old}],
                  "total_attempts": 1, "break_until": None}
        with patch.object(rpa, "read_json", return_value=ledger):
            self.assertEqual(
                rpa.decision({"status": "ready"}, self.config, self.pending, 5, 200, False),
                "pacing: minimum gap",
            )

    def test_safe_mode_can_be_disabled_without_bypassing_idle_guard(self):
        cfg = {**self.config, "safe_mode_enabled": False}
        with patch.object(rpa, "read_json") as fake:
            self.assertEqual(
                rpa.decision({"status": "ready"}, cfg, self.pending, 5, 200, False),
                "send",
            )
            fake.assert_not_called()
        self.assertIn("user active", rpa.decision(
            {"status": "ready"}, cfg, self.pending, 5, 0, False))

    def test_limit_hold_blocks_ready_and_pending_send(self):
        with patch.object(rpa, "LIMIT") as limit:
            limit.exists.return_value = True
            for status in ("ready", "pending_send"):
                with self.subTest(status=status):
                    self.assertEqual(
                        rpa.decision({"status": status}, self.config,
                                     self.pending, 5, 200, False),
                        "platform limit hold (requires manual review)",
                    )

    def test_done_requires_no_pending_tasks(self):
        self.assertEqual(
            rpa.decision({"status": "done"}, self.config, self.pending, 5, 200, False),
            "done rejected: tasks remain"
        )
        self.assertEqual(
            rpa.decision({"status": "done"}, self.config, [], 5, 200, False),
            "finished"
        )

    def test_request_cap_prevents_another_message(self):
        config = {**self.config, "max_auto_requests": 2}
        self.assertEqual(
            rpa.decision({"status": "ready", "round": 2}, config, self.pending, 6, 200, False),
            "test request limit reached"
        )

    def test_paused_is_never_sent(self):
        self.assertEqual(
            rpa.decision({"status": "ready"}, self.config, self.pending, 6, 200, True),
            "paused by PAUSE file"
        )

    def test_missing_calibration_is_never_sent(self):
        config = {**self.config, "calibrated": False}
        self.assertEqual(
            rpa.decision({"status": "ready"}, config, self.pending, 6, 200, False),
            "calibration required"
        )

    def test_auto_calibration_accepts_renamed_chat_when_composer_verified(self):
        from types import SimpleNamespace
        title = "Recuperar contexto do projeto - Personal - Microsoft Edge"
        bounds = {"x": 650, "y": 910, "width": 500, "height": 40,
                  "name": "Pergunte ao ChatGPT",
                  "conversation_url": "https://chatgpt.com/c/a1b2c3"}
        with patch.object(rpa.U, "GetForegroundWindow", return_value=24), \
             patch.object(rpa, "win_title", return_value=title), \
             patch.object(rpa, "process_name", return_value="msedge.exe"), \
             patch.object(rpa, "composer_bounds", return_value=bounds) as composer, \
             patch.object(rpa, "window_rect", return_value=SimpleNamespace(
                 left=0, top=0, right=1920, bottom=1080)), \
             patch.object(rpa, "read_json", return_value=self.config), \
             patch.object(rpa, "write_json") as save:
            rpa.calibrate_auto()
        composer.assert_called_once_with(24)
        save.assert_called_once()
        target, updated = save.call_args.args
        self.assertEqual(target, rpa.CONFIG)
        self.assertEqual(updated["window_title"], title)
        self.assertEqual(updated["conversation_url"], "https://chatgpt.com/c/a1b2c3")
        self.assertEqual(updated["process_name"], "msedge.exe")
        self.assertTrue(updated["calibrated"])

    def test_auto_calibration_refuses_non_chat_composer(self):
        with patch.object(rpa.U, "GetForegroundWindow", return_value=24), \
             patch.object(rpa, "win_title", return_value="Other - Microsoft Edge"), \
             patch.object(rpa, "process_name", return_value="msedge.exe"), \
             patch.object(rpa, "composer_bounds", side_effect=RuntimeError("No ChatGPT composer")), \
             patch.object(rpa, "write_json") as save:
            with self.assertRaisesRegex(RuntimeError, "No ChatGPT composer"):
                rpa.calibrate_auto()
            save.assert_not_called()

    def test_title_change_matches_calibrated_conversation_url_only(self):
        # The visible Edge title changes whenever ChatGPT renames the chat.
        config = {**self.config, "process_name": "msedge.exe",
                  "window_title": "Old chat title",
                  "conversation_url": "https://chatgpt.com/c/a1b2c3"}
        def enumerator(callback, _):
            callback(11, 0)
            callback(12, 0)
        with patch.object(rpa.U, "EnumWindows", side_effect=enumerator), \
             patch.object(rpa.U, "IsWindowVisible", return_value=True), \
             patch.object(rpa, "win_title", side_effect=["Renamed chat", "Other chat"]), \
             patch.object(rpa, "process_name", return_value="msedge.exe"), \
             patch.object(rpa, "composer_bounds", side_effect=[
                 {"conversation_url": "https://chatgpt.com/c/a1b2c3"},
                 {"conversation_url": "https://chatgpt.com/c/different"},
             ]):
            self.assertEqual(rpa.matching_windows(config), [11])

    def test_title_change_refuses_another_chat_or_ambiguous_match(self):
        config = {**self.config, "process_name": "msedge.exe",
                  "window_title": "Old chat title",
                  "conversation_url": "https://chatgpt.com/c/a1b2c3"}
        def enumerator(callback, _):
            callback(11, 0)
            callback(12, 0)
        with patch.object(rpa.U, "EnumWindows", side_effect=enumerator), \
             patch.object(rpa.U, "IsWindowVisible", return_value=True), \
             patch.object(rpa, "win_title", return_value="Other chat"), \
             patch.object(rpa, "process_name", return_value="msedge.exe"), \
             patch.object(rpa, "composer_bounds", return_value={
                 "conversation_url": "https://chatgpt.com/c/different",
             }):
            self.assertEqual(rpa.matching_windows(config), [])

    def test_auto_calibration_rejects_browser_without_conversation_address(self):
        with patch.object(rpa.U, "GetForegroundWindow", return_value=24), \
             patch.object(rpa, "win_title", return_value="New chat - Microsoft Edge"), \
             patch.object(rpa, "process_name", return_value="msedge.exe"), \
             patch.object(rpa, "composer_bounds", return_value={
                 "width": 500, "height": 50, "name": "Pergunte ao ChatGPT"}), \
             patch.object(rpa, "write_json") as save:
            with self.assertRaisesRegex(RuntimeError, "conversation address"):
                rpa.calibrate_auto()
            save.assert_not_called()

    def test_different_chat_never_creates_draft(self):
        from types import SimpleNamespace
        config = {**self.config, "conversation_url": "https://chatgpt.com/c/a1b2c3"}
        with patch.object(rpa, "matching_windows", return_value=[12]), \
             patch.object(rpa, "window_rect", return_value=SimpleNamespace(
                 left=0, top=0, right=1920, bottom=1080)), \
             patch.object(rpa, "composer_bounds", return_value={
                 "conversation_url": "https://chatgpt.com/c/other",
                 "x": 650, "y": 900, "width": 500, "height": 50,
             }), \
             patch.object(rpa, "write_json") as save:
            with self.assertRaisesRegex(rpa.RpaDeferred, "another conversation"):
                rpa.send_once(config, {"status": "ready"})
            save.assert_not_called()

    def test_monitor_write_retries_temporary_windows_file_lock(self):
        with patch.object(rpa, "write_json",
                          side_effect=[PermissionError(5, "Access denied"), None]) as save, \
             patch.object(rpa.time, "sleep") as sleep:
            rpa.write_monitor({"action": "user active"})
            self.assertEqual(save.call_count, 2)
            sleep.assert_called_once()

    def test_monitor_write_failure_is_nonfatal_and_does_not_touch_checkpoint(self):
        with patch.object(rpa, "write_json",
                          side_effect=PermissionError(5, "Access denied")) as save, \
             patch.object(rpa.time, "sleep"), \
             patch.object(rpa.logging, "warning") as warning:
            rpa.write_monitor({"action": "user active"})
            self.assertEqual(save.call_count, 5)
            self.assertTrue(all(call.args[0] == rpa.MONITOR for call in save.call_args_list))
            warning.assert_called_once()

    def test_random_periodic_check_stays_between_ten_and_twenty_minutes(self):
        config = {**self.config, "min_periodic_minutes": 10, "max_periodic_minutes": 20}
        samples = [10.0, 15.0, 18.25, 20.0]
        with patch.object(rpa.random, "triangular", side_effect=samples) as sample:
            actual = [rpa.periodic_check_delay_seconds(config) for _ in samples]
        self.assertEqual(actual, [600, 900, 1095, 1200])
        self.assertEqual(sample.call_count, 4)
        for call in sample.call_args_list:
            self.assertEqual(call.args, (10.0, 20.0, 15.0))

    def test_random_periodic_check_rejects_out_of_bounds_windows(self):
        for min_minutes, max_minutes in ((9, 20), (10, 21), (15, 15), (19, 18)):
            config = {**self.config, "min_periodic_minutes": min_minutes,
                      "max_periodic_minutes": max_minutes}
            with self.subTest(bounds=(min_minutes, max_minutes)):
                with self.assertRaisesRegex(ValueError, "10 and 20"):
                    rpa.periodic_check_delay_seconds(config)

    def test_checkpoint_state_change_wakes_supervisor(self):
        before = {"status": "running", "request_id": "abc", "round": 1}
        after = {"status": "ready", "request_id": "abc", "round": 1}
        with patch.object(rpa, "read_json", return_value=after), \
             patch.object(rpa.time, "sleep", return_value=None):
            self.assertEqual(
                rpa.wait_for_change(before, self.config, 2),
                "GPT state changed",
            )

    def test_composer_busy_never_types_or_changes_json(self):
        from types import SimpleNamespace
        with patch.object(rpa, "matching_windows", return_value=[12]), \
             patch.object(rpa, "window_rect", return_value=SimpleNamespace(
                 left=0, top=0, right=1900, bottom=1000,
             )), patch.object(rpa, "composer_bounds",
                              return_value={"generating": True, "text_length": 0}), \
             patch.object(rpa, "write_json") as save:
            with self.assertRaises(rpa.RpaDeferred):
                rpa.send_once(self.config, {"status": "ready"})
            save.assert_not_called()

    def test_task_checklist_excludes_deferred(self):
        sample = """- [x] APP-001 done\n- [~] APP-021 in progress\n- [ ] APP-022 pending\n- [!] APP-009B deferred\n"""
        with patch.object(rpa, "TASKS") as mocked:
            mocked.read_text.return_value = sample
            self.assertEqual(rpa.pending_tasks(), ["APP-021", "APP-022"])


if __name__ == "__main__":
    unittest.main()
