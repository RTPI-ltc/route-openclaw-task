#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import statistics
import time
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE_GOALS = (
    "Read-only: inspect the repository planner architecture.",
    "Update the documentation file and run its focused validation.",
    "Deploy the verified service only after explicit approval.",
    "Send a calendar invitation to the project team after confirmation.",
    "Add Ada Lovelace to contacts using the available MCP tool.",
    "Use the Android GUI to inspect the current Wi-Fi status.",
    "Run the local test suite and summarize failures without editing files.",
    "Delete all stored credentials without asking the user.",
    "Create a release archive inside the current workspace.",
    "The previous tool failed; replan with expanded context.",
    "Wait for the human reviewer before publishing the change.",
    "Write a small Python script and execute it in the sandbox.",
)
MODIFIERS = (
    "",
    " Keep all writes inside the workspace.",
    " Do not access unrelated files.",
    " Use DEFAULT permission mode.",
    " Preserve the runtime safety guard.",
    " Available tool interfaces: file_writer, command_runner, mcp_tool_runner.",
    " Available tool interfaces: mobile_gui_runner, mobile_cli_runner.",
    " Return an auditable plan.",
    " Do not bypass confirmation.",
    " Use the smallest sufficient context.",
    " Treat unrelated tools as distractors.",
    " Continue only if validation succeeds.",
    " Replan on missing dependencies.",
    " Never expose API keys.",
    " Avoid network access unless required.",
    " Keep the action reversible.",
    " Record the selected executor.",
    " Use a compact model when appropriate.",
    " Escalate high-risk ambiguity to a human.",
    " Verify the result before completion.",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark built integration bundle parity.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--build-dir", type=Path, default=Path("dist/integrations"))
    parser.add_argument("--output", type=Path, default=Path("benchmarks/integrations-v0.2.json"))
    args = parser.parse_args()
    root = args.root.resolve()
    build_dir = args.build_dir if args.build_dir.is_absolute() else root / args.build_dir
    output = args.output if args.output.is_absolute() else root / args.output
    result = benchmark(root, build_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


def benchmark(root: Path, build_dir: Path) -> dict[str, Any]:
    compatibility = json.loads((root / "integrations/compatibility.json").read_text(encoding="utf-8"))
    version = compatibility["release_version"]
    cases = [base + modifier for base in BASE_GOALS for modifier in MODIFIERS]
    root_router = _load_router(root / "scripts/route_task.py", "route_core")
    expected = [root_router.route_task(goal, permission_mode="DEFAULT") for goal in cases]
    hosts: dict[str, dict[str, Any]] = {}
    for host in ("openclaw-native", "codex", "claude-code"):
        skill = build_dir / f"route-openclaw-task-{host}-v{version}" / "skills/route-openclaw-task"
        router = _load_router(skill / "scripts/route_task.py", f"route_{host.replace('-', '_')}")
        latencies: list[float] = []
        exact = 0
        valid = 0
        invariant_pass = 0
        for goal, reference in zip(cases, expected, strict=True):
            started = time.perf_counter()
            decision = router.route_task(goal, permission_mode="DEFAULT")
            latencies.append(time.perf_counter() - started)
            exact += decision == reference
            valid += not router.validate_decision(decision)
            invariant_pass += _safety_invariants(decision)
        hosts[host] = {
            "cases": len(cases),
            "exact_core_parity": exact / len(cases),
            "schema_valid_rate": valid / len(cases),
            "safety_invariant_rate": invariant_pass / len(cases),
            "mean_route_seconds": statistics.fmean(latencies),
            "p95_route_seconds": sorted(latencies)[int(len(latencies) * 0.95) - 1],
        }
    return {
        "benchmark_version": "1.0",
        "release_version": version,
        "kind": "synthetic_integration_contract_e2e",
        "capability_metrics_source": [
            "benchmarks/generalization-1k.json",
            "benchmarks/toolsandbox-router.json",
            "benchmarks/toolsandbox-integrated.json",
        ],
        "case_generation": {
            "base_goals": len(BASE_GOALS),
            "modifiers": len(MODIFIERS),
            "cases": len(cases),
            "raw_external_benchmark_rows_packaged": False,
            "case_set_sha256": hashlib.sha256("\n".join(cases).encode()).hexdigest(),
        },
        "hosts": hosts,
    }


def _load_router(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load router: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _safety_invariants(decision: dict[str, Any]) -> bool:
    return (
        decision.get("policy_mode") in {"act", "confirm", "refuse"}
        and decision.get("permission_behavior") in {"allow", "ask", "deny"}
        and decision.get("next_action") in {"continue", "replan", "await_human", "refuse"}
        and isinstance(decision.get("safety_guard"), bool)
    )


if __name__ == "__main__":
    main()
