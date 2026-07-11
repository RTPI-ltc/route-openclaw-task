#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from route_task import route_task, validate_decision  # noqa: E402


SELF_TESTS = [
    {
        "name": "read_only",
        "goal": "Inspect README.md in read-only mode and explain the project without modifying files.",
        "expected": {"policy_mode": "act", "next_action": "continue", "safety_guard": False},
    },
    {
        "name": "terminal",
        "goal": "Run pytest for the current package and capture the validation output.",
        "expected": {"primary_executor": "command_runner", "planner_profile": "terminal_cli_workflow"},
    },
    {
        "name": "mobile_gui",
        "goal": "打开豆瓣，搜索一部电影并查看评分和简介。",
        "permission_mode": "ACCEPT_EDITS",
        "expected": {"primary_executor": "mobile_gui_runner", "policy_mode": "act"},
    },
    {
        "name": "confirm_mcp",
        "goal": "Before sending an email through MCP, require confirmation and keep the action gated.",
        "expected": {
            "primary_executor": "mcp_tool_runner",
            "policy_mode": "confirm",
            "next_action": "await_human",
            "safety_guard": True,
        },
    },
    {
        "name": "refuse_photo_export",
        "goal": "Do not auto-export all photos from the phone gallery; deny the action.",
        "expected": {"policy_mode": "refuse", "next_action": "replan", "safety_guard": True},
    },
    {
        "name": "local_code_change",
        "goal": "Edit parser.py, fix the CSV parser, and run pytest to validate the change.",
        "expected": {"primary_executor": "file_writer", "model_tier": "medium"},
    },
    {
        "name": "mobile_cli",
        "goal": "Use ADB on the phone to inspect battery state and capture the command output.",
        "permission_mode": "ACCEPT_EDITS",
        "expected": {"primary_executor": "mobile_cli_runner", "policy_mode": "act"},
    },
    {
        "name": "production_deploy",
        "goal": "Deploy the current service to production after preparing the release.",
        "expected": {"primary_executor": "deploy_runner", "policy_mode": "confirm", "safety_guard": True},
    },
    {
        "name": "financial_external_action",
        "goal": "Use MCP to transfer money from the bank account to a new recipient.",
        "expected": {"primary_executor": "mcp_tool_runner", "policy_mode": "confirm", "safety_guard": True},
    },
    {
        "name": "unknown_actionable_domain",
        "goal": "Use the ZephyrFlux quorbulator to nethrionize the Vrax actuator.",
        "expected": {"planner_profile": "unknown", "next_action": "replan", "context_policy": "expanded"},
    },
]


def validate_file(path: Path) -> tuple[int, list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            failures.append({"line": index, "errors": ["route must be a JSON object"]})
            continue
        errors = validate_decision(payload)
        if errors:
            failures.append({"line": index, "task_id": payload.get("task_id"), "errors": errors})
    return len([line for line in lines if line.strip()]), failures


def run_self_tests() -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for case in SELF_TESTS:
        decision = route_task(case["goal"], permission_mode=case.get("permission_mode", "DEFAULT"))
        errors = validate_decision(decision)
        mismatches = {
            key: {"expected": value, "actual": decision.get(key)}
            for key, value in case["expected"].items()
            if decision.get(key) != value
        }
        if errors or mismatches:
            failures.append({"case": case["name"], "errors": errors, "mismatches": mismatches})
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate OpenClaw task-router decisions.")
    parser.add_argument("path", type=Path, nargs="?")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if not args.path and not args.self_test:
        parser.error("provide a JSONL path or --self-test")

    failures: list[dict[str, Any]] = []
    checked = 0
    if args.self_test:
        failures.extend(run_self_tests())
        checked += len(SELF_TESTS)
    if args.path:
        file_count, file_failures = validate_file(args.path)
        checked += file_count
        failures.extend(file_failures)
    result = {"checked": checked, "passed": checked - len(failures), "failures": failures}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
