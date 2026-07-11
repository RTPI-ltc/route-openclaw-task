---
name: task-compass
description: Classify agent tasks into a planner profile, execution tools, safety policy, model tier, context policy, and next action. Use when deciding how a task should be planned or delegated, selecting CLI, file, mobile GUI, mobile CLI, MCP, or deployment executors, determining whether to continue, replan, refuse, or await human approval, or evaluating routing behavior across benchmark tasks.
license: MIT
metadata: {"version":"0.3.0","aliases":["route-openclaw-task"],"compatibility":"OpenClaw, Codex, or Claude Code with Python 3.10 or newer; no network access or API key required","openclaw":{"requires":{"bins":["python3"]}}}
---

# Task Compass Skill

Produce a deterministic, auditable routing decision before planning or execution. Treat the result as advisory policy input; never use it to bypass runtime permission checks.

## OpenClaw Runtime Integration

Install this repository as an OpenClaw workspace skill, or copy this directory to `skills/task-compass`. OpenClaw loads the instructions automatically; the bundled router is invoked explicitly when a deterministic route is needed. The deprecated `route-openclaw-task` name remains a compatibility alias.

This project's optional `LocalAuditPlanner` adapter can enable automatic runtime routing with:

```bash
OPENCLAW_PLANNER_SKILL=task-compass
```

When a task includes an `Available tool interfaces:` catalog, resolve the required tool dependency closure from the task intent and ignore unrelated distraction tools. The runtime adapter converts `execution_tools` into a bounded target path and passes it to OpenClaw's A*/Reflexion planner as an auditable desired-tool constraint. Candidate generation, permission decisions, risk checks, and verification remain owned by OpenClaw.

Do not use this skill as a command generator, a tool-argument generator, or a replacement for runtime permissions.

## Route One Task

Run the bundled router from this skill directory:

```bash
python3 scripts/route_task.py --goal "<task>" --pretty
```

Pass the runtime permission mode when known:

```bash
python3 scripts/route_task.py --goal "<task>" --permission-mode DEFAULT --pretty
```

Use the returned `planned_tools`, `primary_executor`, `policy_mode`, `permission_behavior`, `next_action`, and `safety_guard` to construct the next planner step. Preserve `deny`, `await_human`, `replan`, and `refuse` outcomes exactly.

## Route Many Tasks

Provide JSONL rows containing `goal` and optional `id` and `permission_mode` fields:

```bash
python3 scripts/route_task.py --input-jsonl tasks.jsonl --output-jsonl routes.jsonl
python3 scripts/validate_route.py routes.jsonl
```

Do not pass expected labels or benchmark annotations to the router.

## Evaluate

Measure routing behavior without copying raw prompts into the report:

```bash
python3 scripts/evaluate_router.py --suite benchmark.json --output metrics.json
```

Compare `task_route_success_rate`, `safety_guard_accuracy`, `required_execution_tool_coverage`, and holdout results before promoting a change. Keep the existing runtime permission engine as the final authority.

## Interpret Decisions

Read [references/routing-contract.md](references/routing-contract.md) when integrating the JSON output, changing enum values, or investigating a route. Do not load `assets/profile-policy-model.json` into the prompt; let the script read it.

Read [references/model-card.md](references/model-card.md) when reviewing training provenance, benchmark claims, licensing, limitations, or promotion gates.

Apply these invariants:

- Never downgrade `confirm` or `refuse` to `act` without external verifier evidence.
- Never turn `safety_guard=true` off downstream.
- Route low-confidence actionable tasks to `replan` with expanded context.
- Keep explicit read-only constraints and workspace boundaries intact.
- Keep model predictions, deterministic signals, and the final reason visible in audit logs.
