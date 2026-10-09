"""Tests for request_id guarded acknowledgement and administrative reconciliation."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("expert_ai_state", Path(__file__).with_name("expert_ai_state.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class StateTransitions(unittest.TestCase):
    def test_ack_can_arrive_during_pending_send(self):
        previous = {"status": "pending_send", "request_id": "123", "round": 2}
        with patch.object(m, "load", return_value=previous), patch.object(m, "atomic_save") as write:
            m.change_status("ack", "123")
        result = write.call_args.args[1]
        self.assertEqual(result["status"], "running")
        self.assertEqual(result["request_id"], "123")
        self.assertEqual(result["round"], 2)

    def test_wrong_request_id_does_not_ack(self):
        previous = {"status": "pending_send", "request_id": "123", "round": 2}
        with patch.object(m, "load", return_value=previous), patch.object(m, "atomic_save") as write:
            with self.assertRaisesRegex(RuntimeError, "Request ID mismatch"):
                m.change_status("ack", "another")
            write.assert_not_called()

    def test_reconcile_blocked_delivered_request(self):
        previous = {"status": "blocked", "request_id": "example-request-001", "round": 2}
        with patch.object(m, "load", return_value=previous), patch.object(m, "atomic_save") as write:
            m.change_status("reconcile", "example-request-001",
                            "Original text confirmed in conversation; not a completed task")
        result = write.call_args.args[1]
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["round"], 2)
        self.assertIn("confirmed", result["summary"])

    def test_reconcile_requires_reason(self):
        previous = {"status": "blocked", "request_id": "123", "round": 2}
        with patch.object(m, "load", return_value=previous), patch.object(m, "atomic_save") as write:
            with self.assertRaisesRegex(RuntimeError, "requires an explanation"):
                m.change_status("reconcile", "123")
            write.assert_not_called()

    def test_reconcile_does_not_interrupt_running(self):
        previous = {"status": "running", "request_id": "123", "round": 2}
        with patch.object(m, "load", return_value=previous), patch.object(m, "atomic_save") as write:
            with self.assertRaisesRegex(RuntimeError, "Expected blocked/requested"):
                m.change_status("reconcile", "123", "manually delivered")
            write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
