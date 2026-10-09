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

    def test_auto_calibration_accepts_a_different_project_chat_title(self):
        from types import SimpleNamespace

        bounds = {
            "x": 720, "y": 880, "width": 470, "height": 90,
            "name": "Pergunte ao ChatGPT",
        }
        rect = SimpleNamespace(left=0, top=0, right=1920, bottom=1080)
        with patch.object(rpa.U, "GetForegroundWindow", return_value=100), \
             patch.object(rpa, "win_title", return_value="Projeto CRM - Personal - Microsoft Edge"), \
             patch.object(rpa, "process_name", return_value="msedge.exe"), \
             patch.object(rpa, "composer_bounds", return_value=bounds), \
             patch.object(rpa, "window_rect", return_value=rect), \
             patch.object(rpa, "read_json", return_value={}), \
             patch.object(rpa, "write_json") as save:
            rpa.calibrate_auto()

        saved = save.call_args.args[1]
        self.assertTrue(saved["calibrated"])
        self.assertEqual(saved["window_title"], "Projeto CRM - Personal - Microsoft Edge")
        self.assertEqual(saved["process_name"], "msedge.exe")

    def test_auto_calibration_rejects_an_unrecognized_composer(self):
        with patch.object(rpa.U, "GetForegroundWindow", return_value=100), \
             patch.object(rpa, "win_title", return_value="Some other app - Edge"), \
             patch.object(rpa, "process_name", return_value="msedge.exe"), \
             patch.object(rpa, "composer_bounds", return_value={
                 "x": 720, "y": 880, "width": 470, "height": 90,
                 "name": "Some other website input",
             }), \
             patch.object(rpa, "write_json") as save:
            with self.assertRaisesRegex(RuntimeError, "ChatGPT message composer"):
                rpa.calibrate_auto()
            save.assert_not_called()

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
