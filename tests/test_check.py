#!/usr/bin/env python3
"""
Unit tests for agent-notify check engine.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import check


class TestCheckEngine(unittest.TestCase):
    def setUp(self):
        self.sample_monitors = [
            {
                "id": "omarchy-pr380",
                "name": "Omarchy Bluetooth Poweroff PR #380",
                "type": "github_pr",
                "repo": "omacom/omarchy-mac",
                "pr": 380,
                "enabled": True
            },
            {
                "id": "quattro-vm",
                "name": "Omarchy Quattro Install VM",
                "type": "github_workflow",
                "repo": "omacom/omarchy-mac",
                "workflow": "install-vm.yml",
                "branch": "quattro",
                "enabled": True
            }
        ]

    def test_find_monitor_exact(self):
        m = check.find_monitor(self.sample_monitors, "omarchy-pr380")
        self.assertIsNotNone(m)
        self.assertEqual(m["id"], "omarchy-pr380")

    def test_find_monitor_by_pr_number(self):
        m = check.find_monitor(self.sample_monitors, "380")
        self.assertIsNotNone(m)
        self.assertEqual(m["id"], "omarchy-pr380")

    def test_find_monitor_by_substring(self):
        m = check.find_monitor(self.sample_monitors, "quattro")
        self.assertIsNotNone(m)
        self.assertEqual(m["id"], "quattro-vm")

    def test_find_monitor_not_found(self):
        m = check.find_monitor(self.sample_monitors, "nonexistent-target")
        self.assertIsNone(m)

    @patch("check.ntfy_send")
    @patch("check.fetch_ntfy_messages")
    def test_process_phone_commands_unsub(self, mock_fetch, mock_send):
        mock_fetch.return_value = [
            {
                "id": "msg-123",
                "message": "unsub 380",
                "title": "",
                "time": 1789240000
            }
        ]
        state = {"last_processed_command_id": "msg-100", "monitors": {}}
        monitors = [dict(m) for m in self.sample_monitors]

        mon_changed, st_changed = check.process_phone_commands(monitors, state)

        self.assertTrue(mon_changed)
        self.assertTrue(st_changed)
        self.assertFalse(monitors[0]["enabled"])
        self.assertEqual(state["last_processed_command_id"], "msg-123")
        mock_send.assert_called_once()
        self.assertIn("Unsubscribed", mock_send.call_args[0][0])

    @patch("check.ntfy_send")
    @patch("check.fetch_ntfy_messages")
    def test_process_phone_commands_sub(self, mock_fetch, mock_send):
        mock_fetch.return_value = [
            {
                "id": "msg-124",
                "message": "sub omarchy-pr380",
                "title": "",
                "time": 1789240010
            }
        ]
        state = {"last_processed_command_id": "msg-123", "monitors": {}}
        monitors = [dict(m) for m in self.sample_monitors]
        monitors[0]["enabled"] = False

        mon_changed, st_changed = check.process_phone_commands(monitors, state)

        self.assertTrue(mon_changed)
        self.assertTrue(monitors[0]["enabled"])
        self.assertEqual(state["last_processed_command_id"], "msg-124")
        mock_send.assert_called_once()
        self.assertIn("Subscribed", mock_send.call_args[0][0])

    @patch("check.ntfy_send")
    @patch("check.fetch_ntfy_messages")
    def test_process_phone_commands_duplicate_ignored(self, mock_fetch, mock_send):
        mock_fetch.return_value = [
            {
                "id": "msg-100",
                "message": "unsub 380",
                "title": "",
                "time": 1789230000
            }
        ]
        # Already processed msg-100
        state = {"last_processed_command_id": "msg-100", "monitors": {}}
        monitors = [dict(m) for m in self.sample_monitors]

        mon_changed, st_changed = check.process_phone_commands(monitors, state)

        self.assertFalse(mon_changed)
        mock_send.assert_not_called()

    @patch("check.ntfy_send")
    @patch("check.fetch_json")
    def test_check_github_pr_merged(self, mock_fetch, mock_send):
        mock_fetch.return_value = {
            "state": "closed",
            "merged": True,
            "comments": 5,
            "title": "Fix bluetooth",
            "html_url": "https://github.com/omacom/omarchy-mac/pull/380"
        }
        prev_state = {"state": "open", "merged": False, "comments": 4}
        monitor = self.sample_monitors[0]

        new_state, changed = check.check_github_pr(monitor, prev_state)

        self.assertTrue(changed)
        self.assertTrue(new_state["merged"])
        mock_send.assert_called_once()
        self.assertIn("MERGED", mock_send.call_args[0][0])

    @patch("check.ntfy_send")
    @patch("check.fetch_json")
    def test_check_github_workflow_success(self, mock_fetch, mock_send):
        mock_fetch.return_value = {
            "workflow_runs": [
                {
                    "id": 99999,
                    "conclusion": "success",
                    "html_url": "https://github.com/..."
                }
            ]
        }
        prev_state = {"run_id": 88888, "conclusion": "failure"}
        monitor = self.sample_monitors[1]

        new_state, changed = check.check_github_workflow(monitor, prev_state)

        self.assertTrue(changed)
        self.assertEqual(new_state["conclusion"], "success")
        mock_send.assert_called_once()
        self.assertIn("PASSED", mock_send.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
