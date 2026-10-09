"""Read-only HUD progress and settings regressions; no Tk window required."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import expert_ai_control as control
import expert_ai_hud_data as data


class HudTests(unittest.TestCase):
    def test_task_counts_and_prefix(self):
        sample = (
            "- [x] DEMO-001 Entregue\n"
            "- [~] DEMO-002 Em andamento\n"
            "- [ ] DEMO-003 Pendente\n"
            "- [!] DEMO-004 Bloqueada\n"
            "- [ ] OTHER-005 Separada\n"
        )
        result = data.list_tasks(sample, "DEMO")
        self.assertEqual(result["counts"], {
            "done": 1, "active": 1, "todo": 1, "deferred": 1,
        })
        self.assertEqual([r["id"] for r in result["pending"]],
                         ["DEMO-002", "DEMO-003"])

    def test_check_countdown_never_negative(self):
        now = datetime(2026, 10, 8, 20, tzinfo=timezone.utc)
        self.assertEqual(
            data.remaining_seconds((now + timedelta(seconds=123)).isoformat(), now), 123
        )
        self.assertEqual(
            data.remaining_seconds((now - timedelta(seconds=10)).isoformat(), now), 0
        )
        self.assertIsNone(data.remaining_seconds(None, now))

    def test_invalid_prefix_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "prefix"):
            data.list_tasks("", "../OTHER")

    def test_config_switches_do_not_mutate_other_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "config.json"
            original = {
                **control.read_settings(),
                "calibrated": True,
                "message": "CUSTOM MESSAGE",
                "window_title": "CURRENT WINDOW",
            }
            control.atomic_save(target, original)
            with patch.object(control, "CONFIG", target):
                result = control.set_option("safe_mode_enabled", False)
                self.assertFalse(result["safe_mode_enabled"])
                saved = control.load(target)
                self.assertEqual(saved["message"], "CUSTOM MESSAGE")
                self.assertEqual(saved["window_title"], "CURRENT WINDOW")
                self.assertTrue(saved["calibrated"])
                control.set_option("breaks_enabled", False)
                self.assertFalse(control.load(target)["breaks_enabled"])

    def test_idle_readout_counts_up_without_exposing_ten_second_poll(self):
        sample = {
            "paused": False, "limit_hold": False, "supervisor_live": True,
            "state": "ready", "idle_seconds": 34.8, "idle_required_seconds": 90,
            "next_check_seconds": 3, "next_check_kind": "interactive",
            "pacing_seconds": None,
        }
        view = data.timing_view(sample)
        self.assertEqual(view["decision"], "Aguardando você terminar")
        self.assertEqual(view["check"], "Sem usar o PC: 00:34 de 01:30")
        self.assertTrue(view["idle_visible"])
        self.assertAlmostEqual(view["idle_percent"], 34.8 / 90 * 100)
        self.assertNotIn("3s", view["check"])

    def test_idle_timer_resets_when_user_moves(self):
        original = {
            "paused": False, "limit_hold": False, "supervisor_live": True,
            "state": "ready", "idle_seconds": 82, "idle_required_seconds": 90,
            "next_check_seconds": 1, "next_check_kind": "interactive",
            "pacing_seconds": None,
        }
        before = data.timing_view(original)
        after = data.timing_view({**original, "idle_seconds": 1})
        self.assertGreater(before["idle_percent"], after["idle_percent"])
        self.assertEqual(after["check"], "Sem usar o PC: 00:01 de 01:30")

    def test_no_fake_idle_timer_during_running_or_pause(self):
        base = {
            "paused": False, "limit_hold": False, "supervisor_live": True,
            "state": "running", "idle_seconds": 5, "idle_required_seconds": 90,
            "next_check_seconds": 8, "next_check_kind": "interactive",
            "pacing_seconds": None,
        }
        self.assertFalse(data.timing_view(base)["idle_visible"])
        self.assertNotIn("8s", data.timing_view(base)["check"])
        paused = data.timing_view({**base, "paused": True, "state": "ready"})
        self.assertEqual(paused["decision"], "Supervisor pausado")
        self.assertFalse(paused["idle_visible"])

    def test_shows_real_periodic_check_and_hides_technical_interactive_poll(self):
        base = {
            "paused": False, "limit_hold": False, "supervisor_live": True,
            "state": "running", "idle_seconds": 120, "idle_required_seconds": 90,
            "next_check_seconds": 780, "next_check_kind": "periodic",
            "pacing_seconds": None,
        }
        self.assertIn("13m", data.timing_view(base)["check"])
        hidden = data.timing_view({**base, "next_check_seconds": 10, "next_check_kind": "interactive"})
        self.assertNotIn("10s", hidden["check"])
        self.assertIn("segundo plano", hidden["check"])
        ready = data.timing_view({**base, "state": "ready"})
        self.assertIn("13m", ready["check"])

    def test_invalid_settings_are_not_written(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "config.json"
            control.atomic_save(target, dict(control.read_settings()))
            before = control.load(target)
            with patch.object(control, "CONFIG", target):
                with self.assertRaises(ValueError):
                    control.set_option("max_requests_per_hour", 0)
            self.assertEqual(control.load(target), before)


if __name__ == "__main__":
    unittest.main()
