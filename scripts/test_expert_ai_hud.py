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
