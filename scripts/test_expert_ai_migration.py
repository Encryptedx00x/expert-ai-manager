"""Safe conversation handoff; no browser, live supervisor or real project changes."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import expert_ai_control as control
import expert_ai_migration as migration
import expert_ai_hud_data as hud_data
import expert_ai_rpa as rpa
import expert_ai_context as context


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        folder = Path(self.tmp.name)
        self.state = folder / "chat-state.json"
        self.config = folder / "rpa-config.json"
        self.marker = folder / "chat-migration.json"
        self.pause = folder / "PAUSE"
        self.limit = folder / "LIMIT"
        self.state_value = {
            "status": "running", "round": 13, "request_id": "old-request",
            "last_commit": "abcdef1",
        }
        self.config_value = {
            **control.read_settings(),
            "window_title": "Old Chat - Microsoft Edge",
            "conversation_url": "",  # Isolate fixture from live project calibration.
            "calibrated": True,
        }
        control.atomic_save(self.state, self.state_value)
        control.atomic_save(self.config, self.config_value)
        for target, changes in (
            (migration, {"STATE": self.state, "CONFIG": self.config,
                         "MIGRATION": self.marker, "PAUSE": self.pause, "LIMIT": self.limit}),
            (control, {"STATE": self.state, "CONFIG": self.config, "PAUSE": self.pause,
                       "LIMIT": self.limit}),
            (rpa, {"MIGRATION": self.marker, "STATE": self.state,
                   "CONFIG": self.config, "PAUSE": self.pause}),
        ):
            for key, value in changes.items():
                patcher = patch.object(target, key, value)
                patcher.start()
                self.addCleanup(patcher.stop)

    def test_prepare_pauses_without_mutating_running_request_or_config(self):
        before = control.load(self.state)
        config_before = control.load(self.config)
        handoff = migration.prepare_migration()
        self.assertTrue(self.pause.exists())
        self.assertEqual(handoff["phase"], "awaiting_new_chat")
        self.assertEqual((handoff["round"], handoff["request_id"]), (13, "old-request"))
        self.assertEqual(control.load(self.state), before)
        self.assertEqual(control.load(self.config), config_before)
        prompt = migration.recovery_prompt(handoff)
        self.assertIn("old-request", prompt)
        self.assertIn("não", prompt.lower())
        self.assertIn("AGENTS.md", prompt)
        with self.assertRaisesRegex(RuntimeError, "pendente"):
            migration.prepare_migration()

    def test_prepare_rejects_pending_draft_without_pausing(self):
        control.atomic_save(self.state, {**self.state_value, "status": "pending_send"})
        with self.assertRaisesRegex(RuntimeError, "rascunho"):
            migration.prepare_migration()
        self.assertFalse(self.marker.exists())
        self.assertFalse(self.pause.exists())

    def test_normal_resume_cannot_skip_pending_migration(self):
        migration.prepare_migration()
        with self.assertRaisesRegex(RuntimeError, "Finalize a migração"):
            control.command("resume")
        self.assertTrue(self.pause.exists())

    def test_supervisor_guard_blocks_send_even_if_pause_removed_accidentally(self):
        migration.prepare_migration()
        self.pause.unlink()
        cfg = {**rpa.DEFAULTS, "calibrated": True}
        self.assertEqual(
            rpa.decision({"status": "ready"}, cfg, ["APP-070"], 5.0, 200.0, False),
            "conversation migration pending",
        )

    def test_attach_requires_another_calibrated_window(self):
        migration.prepare_migration()
        with self.assertRaisesRegex(RuntimeError, "conversa anterior"):
            migration.attach_migration("Old Chat - Microsoft Edge")
        with self.assertRaisesRegex(RuntimeError, "calibrad"):
            migration.attach_migration("New Chat - Microsoft Edge")
        self.assertEqual(migration.migration_status()["phase"], "awaiting_new_chat")

    def test_attach_does_not_finish_running_work_and_resumes_only_when_ready(self):
        migration.prepare_migration()
        control.atomic_save(
            self.config, {**self.config_value, "window_title": "New Chat - Microsoft Edge"}
        )
        attached = migration.attach_migration("New Chat - Microsoft Edge")
        self.assertEqual(attached["phase"], "attached")
        self.assertTrue(self.pause.exists())
        self.assertEqual(control.load(self.state), self.state_value)
        with self.assertRaisesRegex(RuntimeError, "ready"):
            migration.finish_migration()
        self.assertTrue(self.pause.exists())
        control.atomic_save(self.state, {**self.state_value, "status": "ready"})
        finished = migration.finish_migration()
        self.assertEqual(finished["phase"], "finished")
        self.assertTrue(finished["resumed"])
        self.assertFalse(self.pause.exists())
        self.assertFalse(self.marker.exists())
        self.assertEqual(control.load(self.state)["request_id"], "old-request")
        session = context.read_session(self.marker.with_name("conversation-session.json"))
        self.assertTrue(session["baseline_known"])
        self.assertEqual(session["start_round"], 13)
        self.assertEqual(context.context_budget(18, session)["level"], "suggest")

    def test_cancel_only_before_attach_preserves_original_pause(self):
        self.pause.touch()
        migration.prepare_migration()
        migration.cancel_migration()
        self.assertTrue(self.pause.exists())
        self.assertFalse(self.marker.exists())
        migration.prepare_migration()
        control.atomic_save(
            self.config, {**self.config_value, "window_title": "New Chat - Microsoft Edge"}
        )
        migration.attach_migration("New Chat - Microsoft Edge")
        with self.assertRaisesRegex(RuntimeError, "não é seguro voltar"):
            migration.cancel_migration()
        self.assertTrue(self.marker.exists())

    def test_new_request_during_migration_refuses_attach_and_finish(self):
        migration.prepare_migration()
        control.atomic_save(self.state, {**self.state_value,
                                          "request_id": "another-request", "round": 14})
        control.atomic_save(
            self.config, {**self.config_value, "window_title": "New Chat - Microsoft Edge"}
        )
        with self.assertRaisesRegex(RuntimeError, "request_id"):
            migration.attach_migration("New Chat - Microsoft Edge")
        self.assertTrue(self.pause.exists())
        self.assertEqual(migration.migration_status()["phase"], "awaiting_new_chat")

        control.atomic_save(self.state, self.state_value)
        migration.attach_migration("New Chat - Microsoft Edge")
        control.atomic_save(self.state, {**self.state_value, "status": "ready", "round": 14})
        with self.assertRaisesRegex(RuntimeError, "request_id"):
            migration.finish_migration()
        self.assertTrue(self.marker.exists())
        self.assertTrue(self.pause.exists())

    def test_migration_requires_different_conversation_url_even_if_renamed(self):
        old_url = "https://chatgpt.com/c/11111111-1111-4111-8111-111111111111"
        new_url = "https://chatgpt.com/c/22222222-2222-4222-8222-222222222222"
        control.atomic_save(
            self.config, {**self.config_value, "conversation_url": old_url}
        )
        migration.prepare_migration()
        control.atomic_save(
            self.config,
            {**self.config_value, "conversation_url": old_url,
             "window_title": "Renamed Old Chat - Microsoft Edge"},
        )
        with self.assertRaisesRegex(RuntimeError, "novo endereço"):
            migration.attach_migration("Renamed Old Chat - Microsoft Edge")
        self.assertTrue(self.pause.exists())
        control.atomic_save(
            self.config, {**self.config_value, "conversation_url": new_url,
                          "window_title": "New Chat - Microsoft Edge"}
        )
        migration.attach_migration("New Chat - Microsoft Edge")
        control.atomic_save(self.state, {**self.state_value, "status": "ready"})
        control.atomic_save(
            self.config, {**self.config_value, "conversation_url": old_url,
                          "window_title": "New Chat - Microsoft Edge"}
        )
        with self.assertRaisesRegex(RuntimeError, "Endereço"):
            migration.finish_migration()
        self.assertTrue(self.pause.exists())
        control.atomic_save(
            self.config, {**self.config_value, "conversation_url": new_url,
                          "window_title": "New Chat - Microsoft Edge"}
        )
        self.assertEqual(migration.finish_migration()["phase"], "finished")

    def test_limit_hold_blocks_resume_of_migration(self):
        migration.prepare_migration()
        control.atomic_save(
            self.config, {**self.config_value, "window_title": "New Chat - Microsoft Edge"}
        )
        migration.attach_migration("New Chat - Microsoft Edge")
        control.atomic_save(self.state, {**self.state_value, "status": "ready"})
        self.limit.touch()
        with self.assertRaisesRegex(RuntimeError, "limite"):
            migration.finish_migration()
        self.assertTrue(self.pause.exists())

    def test_direct_calibration_refuses_pending_migration(self):
        migration.prepare_migration()
        with self.assertRaisesRegex(RuntimeError, "migrate-attach"):
            rpa.calibrate_auto()
        self.assertEqual(control.load(self.config), self.config_value)

    def test_migrate_attach_does_not_send_and_still_requires_ready(self):
        migration.prepare_migration()

        def fake_calibration(*, migration_title, migration_url):
            self.assertEqual(migration_title, "Old Chat - Microsoft Edge")
            self.assertEqual(migration_url, "")
            control.atomic_save(
                self.config, {**self.config_value,
                              "window_title": "New Chat - Microsoft Edge"}
            )

        with patch.object(rpa.time, "sleep") as sleep, \
             patch.object(rpa, "calibrate_auto", side_effect=fake_calibration) as calibrate, \
             patch.object(rpa, "send_once") as send:
            rpa.migrate_attach()
            sleep.assert_called_once_with(6)
            calibrate.assert_called_once()
            send.assert_not_called()
        self.assertEqual(migration.migration_status()["phase"], "attached")
        self.assertTrue(self.pause.exists())
        self.assertEqual(control.load(self.state)["status"], "running")

    def test_finish_preserves_preexisting_pause(self):
        self.pause.touch()
        migration.prepare_migration()
        control.atomic_save(
            self.config, {**self.config_value, "window_title": "New Chat - Microsoft Edge"}
        )
        migration.attach_migration("New Chat - Microsoft Edge")
        control.atomic_save(self.state, {**self.state_value, "status": "ready"})
        result = migration.finish_migration()
        self.assertFalse(result["resumed"])
        self.assertTrue(self.pause.exists())

    def test_automatic_round_handoff_requires_ready_and_preserves_state(self):
        before = control.load(self.state)
        with self.assertRaisesRegex(RuntimeError, "ready"):
            migration.prepare_migration(trigger="round_budget", budget_rounds=8)
        self.assertFalse(self.pause.exists())
        control.atomic_save(self.state, {**before, "status": "ready"})
        before = control.load(self.state)
        handoff = migration.prepare_migration(trigger="round_budget", budget_rounds=8)
        self.assertTrue(self.pause.exists())
        self.assertEqual(handoff["trigger"], "round_budget")
        self.assertEqual(handoff["budget_rounds"], 8)
        self.assertEqual(handoff["request_id"], before["request_id"])
        self.assertEqual(control.load(self.state), before)
        self.assertRegex(handoff["migration_id"], r"^[0-9a-f]{16}$")
        prompt = migration.recovery_prompt(handoff)
        self.assertIn("[migration_id: " + handoff["migration_id"] + "]", prompt)
        self.assertIn("migrate-ack", prompt)
        self.assertIn("docs/EXECUTION_PLAN.md", prompt)
        self.assertIn("\\n", repr(prompt))

    def test_timeout_handoff_preserves_running_checkpoint_without_fake_ready(self):
        before = control.load(self.state)
        handoff = migration.prepare_migration(trigger="delivery_timeout")
        self.assertEqual(control.load(self.state), before)
        self.assertEqual(handoff["initial_status"], "running")
        self.assertEqual(handoff["trigger"], "delivery_timeout")
        self.assertTrue(self.pause.exists())
        self.assertEqual(migration.migration_status()["phase"], "awaiting_new_chat")

    def test_auto_recovery_ack_requires_exact_id_and_safe_checkpoint(self):
        control.atomic_save(self.state, {**self.state_value, "status": "ready"})
        handoff = migration.prepare_migration(trigger="conversation_limit")
        handoff["phase"] = "bootstrap_sent"
        control.atomic_save(self.marker, handoff)
        with self.assertRaisesRegex(RuntimeError, "ID mismatch"):
            migration.acknowledge_auto_migration("bad-token")
        ack = migration.acknowledge_auto_migration(handoff["migration_id"])
        self.assertEqual(ack["phase"], "acknowledged")
        self.assertTrue(self.pause.exists())
        self.assertEqual(control.load(self.state)["request_id"], self.state_value["request_id"])
        with self.assertRaisesRegex(RuntimeError, "awaiting recovery"):
            migration.acknowledge_auto_migration(handoff["migration_id"])
        # A verified URL allows same window title, but not the same chat URL.
        old = "https://chatgpt.com/c/11111111-1111-4111-8111-111111111111"
        new = "https://chatgpt.com/c/22222222-2222-4222-8222-222222222222"
        control.atomic_save(self.marker, {**ack, "previous_conversation_url": old})
        control.atomic_save(self.config, {**self.config_value, "conversation_url": new})
        migration.attach_migration(self.config_value["window_title"])
        finished = migration.finish_migration()
        self.assertTrue(finished["resumed"])
        self.assertFalse(self.pause.exists())
        self.assertFalse(self.marker.exists())
        self.assertEqual(control.load(self.state)["round"], 13)

    def test_auto_ack_fails_on_running_or_platform_limit(self):
        handoff = migration.prepare_migration(trigger="delivery_timeout")
        handoff["phase"] = "bootstrap_sent"
        control.atomic_save(self.marker, handoff)
        with self.assertRaisesRegex(RuntimeError, "ready"):
            migration.acknowledge_auto_migration(handoff["migration_id"])
        control.atomic_save(self.state, {**self.state_value, "status": "ready"})
        self.limit.touch()
        with self.assertRaisesRegex(RuntimeError, "limit"):
            migration.acknowledge_auto_migration(handoff["migration_id"])
        self.assertEqual(migration.migration_status()["phase"], "bootstrap_sent")
        self.assertTrue(self.pause.exists())

    def test_hud_displays_migration_instead_of_idle_countdown(self):
        base = {
            "paused": True, "limit_hold": False, "supervisor_live": True,
            "migration_phase": "awaiting_new_chat", "state": "running",
            "next_check_kind": "periodic", "next_check_seconds": 900,
            "pacing_seconds": None,
        }
        view = hud_data.timing_view(base)
        self.assertEqual(view["decision"], "Aguardando novo chat")
        self.assertFalse(view["idle_visible"])
        self.assertIn("suspensos", view["check"])


if __name__ == "__main__":
    unittest.main()
