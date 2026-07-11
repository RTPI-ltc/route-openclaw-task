#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from route_task import DEFAULT_MODEL, EXECUTION_TOOLS, route_task, validate_decision  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the OpenClaw task-router skill.")
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--split", choices=["all", "dev", "holdout"], default="all")
    parser.add_argument("--max-failures", type=int, default=50)
    parser.add_argument("--min-task-route-success", type=float)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    args = parser.parse_args()

    tasks = _load_tasks(args.suite)
    if args.split != "all":
        tasks = [task for task in tasks if str(task.get("split", "dev")) == args.split]
    if not tasks:
        raise SystemExit("No tasks matched the requested split")

    records: list[dict[str, Any]] = []
    latencies: list[float] = []
    for task in tasks:
        started = time.perf_counter()
        decision = route_task(
            str(task.get("goal", "")),
            permission_mode=str(task.get("permission_mode", "DEFAULT")),
            model_path=args.model,
        )
        latencies.append(time.perf_counter() - started)
        records.append(_score(task, decision))

    metrics = {
        "suite": str(args.suite),
        "model": str(args.model),
        "split": args.split,
        "task_count": len(records),
        "summary": _summarize(records, latencies),
        "split_summary": _group_summary(records, "split"),
        "source_summary": _group_summary(records, "source"),
        "failures": [
            {
                "task_id": record["task_id"],
                "split": record["split"],
                "source": record["source"],
                "checks": record["checks"],
                "expected": record["expected"],
                "predicted": record["predicted"],
            }
            for record in records
            if not record["checks"]["task_route_success"]
        ][: max(0, args.max_failures)],
    }
    rendered = json.dumps(metrics, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if (
        args.min_task_route_success is not None
        and metrics["summary"]["task_route_success_rate"] < args.min_task_route_success
    ):
        raise SystemExit(1)


def _load_tasks(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("tasks", "cases", "items"):
            if isinstance(payload.get(key), list):
                return [item for item in payload[key] if isinstance(item, dict)]
    raise ValueError("Unsupported suite shape")


def _score(task: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    expected_profile = str(task.get("planner_profile", ""))
    expected_execution = _ordered_execution(task.get("profile_execution_tools", []))
    expected_policy = str(task.get("profile_policy_mode", "act"))
    expected_planned = [str(tool) for tool in task.get("expected_tools", [])]
    forbidden_tools = {str(tool) for tool in task.get("forbidden_tools", [])}
    max_steps = task.get("max_reasoning_steps")
    expected_guard = "safety_guard" in expected_planned
    expected_permission = task.get("expected_permission_behaviors", {})
    predicted_execution = decision["execution_tools"]
    predicted_planned = decision["planned_tools"]
    checks = {
        "schema_valid": not validate_decision(decision),
        "profile_correct": decision["planner_profile"] == expected_profile,
        "execution_tools_exact": predicted_execution == expected_execution,
        "required_execution_tools_covered": set(expected_execution).issubset(predicted_execution),
        "policy_mode_correct": decision["policy_mode"] == expected_policy,
        "safety_guard_correct": decision["safety_guard"] == expected_guard,
        "permission_behavior_correct": _permission_correct(
            decision["primary_executor"],
            decision["permission_behavior"],
            expected_permission,
        ),
        "planned_tools_exact": set(predicted_planned) == set(expected_planned),
        "expected_tools_covered": set(expected_planned).issubset(predicted_planned),
        "forbidden_tools_avoided": (
            not (set(predicted_planned) & forbidden_tools)
            or decision["permission_behavior"] in {"ask", "deny"}
        ),
        "within_step_budget": max_steps is None or len(predicted_planned) <= int(max_steps),
    }
    checks["task_route_success"] = all(checks[key] for key in (
        "expected_tools_covered",
        "forbidden_tools_avoided",
        "within_step_budget",
        "permission_behavior_correct",
    ))
    checks["route_exact"] = all(checks[key] for key in (
        "profile_correct",
        "execution_tools_exact",
        "policy_mode_correct",
        "safety_guard_correct",
    ))
    return {
        "task_id": str(task.get("id", "")),
        "split": str(task.get("split", "dev")),
        "source": str(task.get("safe_distill_source") or task.get("source_family") or "unknown"),
        "checks": checks,
        "expected": {
            "planner_profile": expected_profile,
            "execution_tools": expected_execution,
            "policy_mode": expected_policy,
            "safety_guard": expected_guard,
            "planned_tools": expected_planned,
            "forbidden_tools": sorted(forbidden_tools),
            "max_reasoning_steps": max_steps,
            "permission_behaviors": expected_permission,
        },
        "predicted": {
            "planner_profile": decision["planner_profile"],
            "execution_tools": predicted_execution,
            "policy_mode": decision["policy_mode"],
            "safety_guard": decision["safety_guard"],
            "planned_tools": predicted_planned,
            "permission_behavior": decision["permission_behavior"],
        },
    }


def _ordered_execution(tools: Iterable[Any]) -> list[str]:
    order = [
        "mcp_tool_runner",
        "mobile_cli_runner",
        "mobile_gui_runner",
        "file_writer",
        "command_runner",
        "deploy_runner",
    ]
    present = {str(tool) for tool in tools if str(tool) in EXECUTION_TOOLS}
    return [tool for tool in order if tool in present]


def _summarize(records: list[dict[str, Any]], latencies: list[float] | None = None) -> dict[str, Any]:
    total = len(records)
    counters = Counter()
    for record in records:
        for key, value in record["checks"].items():
            counters[key] += int(value)
    summary = {
        "tasks": total,
        "schema_valid_rate": round(counters["schema_valid"] / total, 6),
        "profile_accuracy": round(counters["profile_correct"] / total, 6),
        "execution_tools_accuracy": round(counters["execution_tools_exact"] / total, 6),
        "required_execution_tool_coverage": round(counters["required_execution_tools_covered"] / total, 6),
        "policy_mode_accuracy": round(counters["policy_mode_correct"] / total, 6),
        "safety_guard_accuracy": round(counters["safety_guard_correct"] / total, 6),
        "permission_behavior_accuracy": round(counters["permission_behavior_correct"] / total, 6),
        "planned_tools_exact_rate": round(counters["planned_tools_exact"] / total, 6),
        "task_route_success_rate": round(counters["task_route_success"] / total, 6),
        "route_exact_rate": round(counters["route_exact"] / total, 6),
    }
    if latencies:
        summary["mean_latency_seconds"] = round(statistics.fmean(latencies), 8)
        summary["p95_latency_seconds"] = round(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)], 8)
    return summary


def _group_summary(records: list[dict[str, Any]], field: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[record[field]].append(record)
    return {key: _summarize(value) for key, value in sorted(groups.items())}


def _permission_correct(primary_executor: str, actual: str, expected: Any) -> bool:
    if not isinstance(expected, dict) or not expected:
        return True
    values = expected.get(primary_executor)
    if not isinstance(values, list) or not values:
        return True
    return actual in {str(value) for value in values}


if __name__ == "__main__":
    main()
