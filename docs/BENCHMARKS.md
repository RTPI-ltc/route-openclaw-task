# Benchmarks

## Promotion Philosophy

The project treats a skill as useful only when it improves end-to-end routing on the same frozen tasks, model, runtime, and safety policy. Training accuracy alone is not a promotion signal.

## ToolSandbox Evaluation

Source: [Apple ToolSandbox](https://github.com/apple/ToolSandbox), commit `165848b9a78cead7ca7fe7c89c688b58e6501219`.

- 129 upstream scenarios.
- Two variants per scenario: no distraction tools and three distraction tools.
- 258 tasks total: 212 dev and 46 holdout.
- Source-group pairs remain in the same split.
- Static AST conversion only; upstream Python was not imported or executed.
- Simulated tool selection only; no contacts, messages, reminders, devices, accounts, or external services were modified.

### Integrated OpenClaw Comparison

Both sides used the same OpenClaw image, Qwen3.7-Max endpoint, `OPENCLAW_MODEL_PLANNER_POLICY=always`, six-shard concurrency, read-only repository mount, read-only root filesystem, dropped capabilities, and no-new-privileges. The optimized runtime enabled the router now published as `task-compass`; the baseline did not.

| Metric | Baseline | With Skill | Delta |
|---|---:|---:|---:|
| Strict route success | 26.74% | 93.02% | +66.28 pp |
| Holdout success | 30.43% | 84.78% | +54.35 pp |
| Executor coverage | 36.43% | 98.06% | +61.63 pp |
| Executor precision | 65.50% | 100.00% | +34.50 pp |
| Path exact | 0.00% | 98.06% | +98.06 pp |
| Qwen success | 100.00% | 100.00% | 0.00 pp |
| Safety | 100.00% | 100.00% | 0.00 pp |
| Mean selected steps | 5.0000 | 4.3256 | -0.6744 |
| Mean latency | 34.2685 s | 34.5306 s | +0.2621 s |
| P95 latency | 51.5187 s | 50.2772 s | -1.2415 s |

Five primary-run requests had transient model fallbacks. Their original records remain in the evidence bundle. The same five frozen task IDs were rerun once; all returned normally, and the strict evaluator records five explicit overrides.

### Standalone Router

| Metric | All 258 | Holdout 46 |
|---|---:|---:|
| Task-route success | 93.41% | 84.78% |
| Schema validity | 100.00% | 100.00% |
| Required executor coverage | 100.00% | 100.00% |
| Safety guard accuracy | 100.00% | 100.00% |

Standalone latency was approximately 1.3 ms per task on the benchmark host. This is not directly comparable to remote Qwen latency.

## Generalization Regression Suite

The 1,000-task suite covers PhoneHarness, tau2, ToolBench, SkillsBench, project-authored mobile tasks, and a safe TerminalWorld routing slice.

| Metric | All 1,000 | Holdout 200 |
|---|---:|---:|
| Task-route success | 99.90% | 100.00% |
| Schema validity | 100.00% | 100.00% |
| Required executor coverage | 100.00% | 100.00% |
| Policy mode accuracy | 100.00% | 100.00% |

One known dev item requires a safety guard for an otherwise ordinary Bilibili tutorial search. Broadening that rule regressed normal application search, so the project keeps the narrow behavior and records the failure.

## Public Evidence

The release includes aggregate JSON summaries and source manifests, not raw benchmark prompts. This keeps the repository small, avoids credential-shaped fixtures, and respects upstream redistribution boundaries.

Files:

- `benchmarks/toolsandbox-integrated.json`
- `benchmarks/toolsandbox-router.json`
- `benchmarks/generalization-1k.json`
- `benchmarks/manifest.json`
- `benchmarks/integrations-v0.2.json`
- `benchmarks/integrations-v0.3.json`

## v0.3 Integration Contract Benchmark

The bundle gate generates 240 safe synthetic variations from 12 task intents
and 20 context modifiers. It executes the embedded router from the OpenClaw,
Codex, and Claude Code release bundles. All three require 100% schema validity,
100% exact output parity with the root Skill, and 100% safety-field integrity.

This is a packaging and adapter E2E benchmark, not a new capability-quality
dataset. Capability claims remain tied to the independently sourced
ToolSandbox and 1,000-task suites above. OpenClaw additionally receives a native
official-container install/load/bridge test; Codex and Claude Code remain
offline-contract-only by explicit constraint.

## Reproduction

Unit and synthetic acceptance tests require no network:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/verify_release.py .
python3 scripts/build_integrations.py
python3 scripts/validate_integrations.py
python3 scripts/benchmark_integrations.py
```

The full ToolSandbox and 1,000-task evaluations require separately obtained upstream datasets or the OpenClaw optimization research workspace. They are intentionally not downloaded by the skill.

## Limitations

- Tool selection metrics do not prove concrete command or argument correctness.
- The integrated comparison uses one hosted model family and one OpenClaw planner implementation.
- Holdout contains 46 ToolSandbox tasks; broader claims require more independently sourced task suites.
- Mean remote-model latency did not improve materially. The skill improves route quality, not model serving speed.
