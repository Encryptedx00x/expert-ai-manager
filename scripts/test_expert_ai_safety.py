"""Bounded resource usage and rest breaks, never fingerprint camouflage."""
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("expert_ai_safety", Path(__file__).with_name("expert_ai_safety.py"))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)

BASE = datetime(2026, 10, 8, 20, 0, tzinfo=timezone.utc)

class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.cfg = dict(s.DEFAULT_SAFETY)
        self.usage = s.new_ledger()

    def record(self, n, at=BASE, choose=None):
        self.usage = s.record_attempt(self.cfg, self.usage, f"id-{n}", at=at,
                                      choose_duration=choose)

    def test_default_caps_match_twelve_minute_cadence(self):
        self.assertEqual(self.cfg["min_minutes_between_requests"], 12)
        self.assertEqual(self.cfg["max_requests_per_hour"], 5)
        self.assertEqual(self.cfg["max_requests_per_24_hours"], 120)

    def test_defaults_are_safe_and_breaks_enabled(self):
        self.assertTrue(self.cfg["safe_mode_enabled"])
        self.assertTrue(self.cfg["breaks_enabled"])
        self.assertTrue(s.pace_status(self.cfg, self.usage, BASE)["allowed"])

    def test_minimum_gap_holds_despite_ready_checkpoint(self):
        self.record(1)
        verdict = s.pace_status(self.cfg, self.usage, BASE + timedelta(minutes=8))
        self.assertFalse(verdict["allowed"])
        self.assertEqual(verdict["reason"], "minimum gap")
        self.assertTrue(s.pace_status(self.cfg, self.usage, BASE + timedelta(minutes=12))["allowed"])

    def test_same_request_is_counted_only_once(self):
        self.record(1)
        self.record(1)
        self.assertEqual(self.usage["total_attempts"], 1)
        self.assertEqual(len(self.usage["attempts"]), 1)

    def test_short_break_is_sampled_once_each_three_requests(self):
        self.record(1, BASE)
        self.record(2, BASE + timedelta(minutes=20))
        self.record(3, BASE + timedelta(minutes=40), choose=lambda lo, hi: 6.5)
        self.assertEqual(self.usage["break_kind"], "short")
        self.assertEqual(self.usage["break_until"], (BASE + timedelta(minutes=46, seconds=30)).isoformat())
        self.assertFalse(s.pace_status(self.cfg, self.usage, BASE + timedelta(minutes=45))["allowed"])

    def test_long_break_is_sampled_every_nine_requests(self):
        for n in range(1, 10):
            self.record(n, BASE + timedelta(minutes=n * 30), choose=lambda lo, hi: 22)
        self.assertEqual(self.usage["total_attempts"], 9)
        self.assertEqual(self.usage["break_kind"], "long")
        self.assertEqual(self.usage["break_until"], (BASE + timedelta(minutes=270 + 22)).isoformat())

    def test_disabled_breaks_do_not_schedule_rest(self):
        self.cfg["breaks_enabled"] = False
        for n in range(1, 4):
            self.record(n, BASE + timedelta(minutes=n * 20))
        self.assertIsNone(self.usage["break_until"])

    def test_disabled_safe_mode_bypasses_pacing_but_tracks_usage(self):
        self.cfg["safe_mode_enabled"] = False
        self.record(1)
        self.record(2)
        self.assertTrue(s.pace_status(self.cfg, self.usage, BASE)["allowed"])
        self.assertEqual(self.usage["total_attempts"], 2)

    def test_hourly_cap_is_enforced(self):
        self.cfg["max_requests_per_hour"] = 4  # Isolate the cap test from new 5/hour defaults.
        self.cfg["short_break_every_requests"] = 9
        self.cfg["long_break_every_requests"] = 18
        for n in range(4):
            self.record(n, BASE + timedelta(minutes=n * 13))
        verdict = s.pace_status(self.cfg, self.usage, BASE + timedelta(minutes=53))
        self.assertEqual(verdict["reason"], "hourly cap")
        self.assertEqual(verdict["requests_last_hour"], 4)

    def test_24_hour_cap_and_expiration(self):
        self.cfg["max_requests_per_24_hours"] = 2
        self.cfg["breaks_enabled"] = False
        self.record(1, BASE)
        self.record(2, BASE + timedelta(hours=2))
        blocked = s.pace_status(self.cfg, self.usage, BASE + timedelta(hours=4))
        self.assertEqual(blocked["reason"], "24-hour cap")
        self.assertTrue(s.pace_status(self.cfg, self.usage, BASE + timedelta(hours=24, minutes=1))["allowed"])

    def test_invalid_config_is_not_silently_accepted(self):
        for field, value in (("max_requests_per_hour", 0), ("max_requests_per_24_hours", 0),
                             ("min_minutes_between_requests", -1), ("short_break_max_minutes", 300),
                             ("safe_mode_enabled", "true")):
            cfg = {**self.cfg, field: value}
            with self.subTest(field=field), self.assertRaises(ValueError):
                s.validate_safety(cfg)

    def test_corrupt_ledger_fails_closed(self):
        with self.assertRaises(ValueError):
            s.pace_status(self.cfg, {"attempts": [{"request_id": "bad", "at": "abc"}]}, BASE)

if __name__ == "__main__":
    unittest.main()
