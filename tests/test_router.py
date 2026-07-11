from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from route_task import route_task, validate_decision  # noqa: E402


class RouterTest(unittest.TestCase):
    def test_decision_is_schema_valid_and_deterministic(self) -> None:
        goal = "Inspect the repository without editing files and summarize the planner architecture."
        first = route_task(goal)
        second = route_task(goal)
        self.assertEqual(first, second)
        self.assertEqual(validate_decision(first), [])
        self.assertEqual(first["schema_version"], "1.0")

    def test_catalog_distractors_do_not_change_executor_route(self) -> None:
        base = route_task(
            "Add Ada Lovelace to contacts. Available tool interfaces: add_contact."
        )
        distracted = route_task(
            "Add Ada Lovelace to contacts. Available tool interfaces: "
            "add_contact, search_stock, get_wifi_status, convert_currency."
        )
        self.assertEqual(base["execution_tools"], ["mcp_tool_runner"])
        self.assertEqual(distracted["execution_tools"], base["execution_tools"])
        self.assertEqual(distracted["planned_tools"], base["planned_tools"])
        self.assertIn("tool_dependency_closure", distracted["signals"])

    def test_missing_catalog_dependency_abstains(self) -> None:
        decision = route_task(
            "Send a message to Ada. Available tool interfaces: "
            "send_message_with_phone_number, search_stock."
        )
        self.assertEqual(decision["execution_tools"], [])
        self.assertEqual(decision["primary_executor"], "none")
        self.assertEqual(decision["next_action"], "replan")
        self.assertEqual(decision["permission_behavior"], "deny")
        self.assertIn("incomplete_tool_dependency", decision["signals"])

    def test_explicit_refusal_is_preserved(self) -> None:
        decision = route_task(
            "Never auto-execute this request: delete all photos from the phone without confirmation."
        )
        self.assertEqual(decision["policy_mode"], "refuse")
        self.assertEqual(decision["permission_behavior"], "deny")
        self.assertEqual(decision["next_action"], "replan")
        self.assertTrue(decision["safety_guard"])

    def test_read_only_goal_has_no_mutating_executor(self) -> None:
        decision = route_task(
            "Read-only: inspect the workspace and explain the planner. Do not modify or write files."
        )
        mutating = {
            "file_writer",
            "command_runner",
            "deploy_runner",
            "mobile_gui_runner",
            "mobile_cli_runner",
            "mcp_tool_runner",
        }
        self.assertFalse(mutating.intersection(decision["execution_tools"]))
        self.assertEqual(decision["planner_profile"], "terminal_cli_workflow")
        self.assertIn("explicit_read_only", decision["signals"])
        self.assertIn("local_project_context", decision["signals"])

    def test_planner_path_never_exceeds_five_steps(self) -> None:
        decisions = [
            route_task("Fix parser.py and run pytest."),
            route_task("Deploy the verified release to production after explicit approval."),
            route_task("Open the phone settings and inspect Wi-Fi status."),
        ]
        self.assertTrue(all(len(decision["planned_tools"]) <= 5 for decision in decisions))


if __name__ == "__main__":
    unittest.main()
