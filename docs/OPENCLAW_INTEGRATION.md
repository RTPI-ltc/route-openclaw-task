# OpenClaw Integration

## Standard Skill Flow

Install the Git repository directly:

```bash
openclaw skills install git:RTPI-ltc/route-openclaw-task@v0.1.0
```

OpenClaw discovers `SKILL.md` at the repository root. When the task matches the trigger description, the agent can invoke `scripts/route_task.py`, inspect the validated JSON, and build its plan without changing OpenClaw source code.

This is the recommended portable integration.

## Planner Contract

Consume these fields:

- `planner_profile`
- `execution_tools`
- `planned_tools`
- `primary_executor`
- `policy_mode`
- `permission_behavior`
- `context_policy`
- `model_tier`
- `next_action`
- `safety_guard`
- `confidence`
- `signals`
- `reason`

The complete schema and enum values are in [the routing contract](../references/routing-contract.md).

Required invariants:

1. Never downgrade `confirm` or `refuse` to `act` without independent verifier evidence.
2. Never disable `safety_guard=true` downstream.
3. Keep OpenClaw's permission engine as the final authority.
4. Treat `replan`, `await_human`, and `refuse` as control flow, not explanatory text.
5. Record the route and the final planner decision together for auditability.

## Optional LocalAuditPlanner Adapter

The reference research integration loads the workspace skill when `OPENCLAW_PLANNER_SKILL=route-openclaw-task`, emits `planner_skill_route` and `planner_skill_candidates` audit events, expands missing executor candidates, and passes a bounded `desired_tools_override` into A*/Reflexion search.

This adapter is validated against the `LocalAuditPlanner` implementation in `hopercheche/openclaw_optimization`. It is not claimed to be a stable upstream OpenClaw extension point. Consumers should integrate through the JSON contract unless they maintain the same planner API.

## Security Configuration

For privileged OpenClaw deployments:

- install into a workspace-specific `skills/` directory;
- keep the repository mount read-only;
- use a read-only container root filesystem;
- drop Linux capabilities and set no-new-privileges;
- restrict model egress to the configured provider;
- keep API keys in runtime secret injection, never in `SKILL.md`, prompts, or logs;
- use OpenClaw agent skill allowlists and shell/tool allowlists separately.

The router itself does not need an API key or network access.

## Upgrade and Rollback

Pin a release tag:

```bash
openclaw skills install git:RTPI-ltc/route-openclaw-task@v0.1.0
```

For rollback, reinstall the previous tag. Git-installed skills are reinstalled to update; OpenClaw's tracked `skills update` flow applies to ClawHub installs.
