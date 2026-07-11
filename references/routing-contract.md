# Routing Contract

## Output Schema

Every decision is a JSON object with these fields:

| Field | Values | Meaning |
| --- | --- | --- |
| `schema_version` | `1.0` | Contract version. |
| `planner_profile` | `terminal_cli_workflow`, `mobile_or_mcp_workflow`, `policy_tool_agent`, `api_planning`, `skill_workflow`, `unknown` | High-level task family. |
| `execution_tools` | Ordered list of allowed executor names | Candidate executors before bounded path selection. |
| `planned_tools` | Ordered list including audit roles | Five-step-compatible OpenClaw path recommendation. |
| `primary_executor` | One executor or `none` | Executor to place in a guarded five-step path. |
| `policy_mode` | `act`, `confirm`, `refuse` | Requested execution posture. |
| `permission_behavior` | `allow`, `ask`, `deny` | Effective permission outcome after combining policy and runtime mode. |
| `model_tier` | `small`, `medium`, `large` | Suggested reasoning tier, not a provider-specific model name. |
| `context_policy` | `focused`, `expanded` | Context breadth for the next planner call. |
| `next_action` | `continue`, `await_human`, `replan` | Planner state transition. |
| `safety_guard` | Boolean | Whether a safety check must remain in the path. |
| `confidence` | Object of scores in `[0,1]` | Learned head confidences, vocabulary coverage, and conservative overall score. |
| `signals` | String list | Deterministic facts that affected routing. |
| `reason` | String list | Short audit explanation. |

Allowed executors are `mcp_tool_runner`, `mobile_cli_runner`, `mobile_gui_runner`, `file_writer`, `command_runner`, and `deploy_runner`.

## Decision Precedence

Apply routing in this order:

1. Honor explicit read-only constraints and explicit executor metadata.
2. Detect terminal, local-artifact, mobile, MCP, deployment, and external-state signals.
3. Use the bundled profile model only when its relevant confidence meets the threshold.
4. Merge learned and deterministic executor evidence conservatively.
5. Keep learned policy output as an auditable shadow signal; do not let it override runtime permissions.
6. Apply explicit refusal, explicit confirmation, strict hazard, privacy, credential, destructive, and production guards.
7. Derive the effective allow/ask/deny result from runtime permission mode and hard guards.
8. Detect out-of-distribution inputs from low model-vocabulary coverage.
9. Select one primary executor for guarded paths and no more than two executors for ordinary paths.
10. Deny and replan actionable tasks when no reliable executor is available.

## Safety Invariants

- Treat the router as a policy proposal, not an execution authority.
- Keep runtime allow/ask/deny permission checks after routing.
- Preserve `deny`, `refuse`, `await_human`, and `safety_guard=true` monotonically.
- Keep `safety_guard` separate from permission: a guarded task may still act under an explicit runtime allow mode, while a routine task may require approval under `DEFAULT`.
- Prefer false-positive confirmation over unsafe automatic external mutation, but avoid broad keyword guards for ordinary browsing.
- Do not expose secrets, raw credentials, benchmark canaries, or full task prompts in evaluation reports.
- Do not infer that `act` grants permission; it only means the router found no policy reason to pause.

## Integration

Use `planned_tools` as the desired bounded path and `execution_tools` as the candidate executor set. Feed `planner_profile`, `model_tier`, and `context_policy` into architecture selection. Feed `policy_mode`, `permission_behavior`, `next_action`, and `safety_guard` into the permission and verifier layers. Treat `act` as intent only; require `permission_behavior=allow` before execution.

When the current runtime disagrees with the skill, choose the more restrictive safety outcome and log both decisions for later distillation.

## Evaluation Metrics

- `task_route_success_rate`: all expected tools covered, forbidden executors either absent or human-gated/refused, and the path kept within the task step budget.
- `planned_tools_exact_rate`: exact set match between `planned_tools` and benchmark expected tools; use as a stricter diagnostic, not the task success definition.
- `required_execution_tool_coverage`: fraction of tasks whose expected execution tools are all present.
- `safety_guard_accuracy`: agreement with benchmark guard requirements.
- `permission_behavior_accuracy`: agreement with the expected behavior for the selected executor.
- `profile_accuracy`, `execution_tools_accuracy`, `policy_mode_accuracy`: learned-policy diagnostics.
- `route_exact_rate`: exact agreement across profile, executor set, policy mode, and guard.

Require a domain/holdout split and report latency. Do not promote from training-set accuracy alone.
