# OpenClaw Integration

## Standard Skill Flow

Install the Git repository directly:

```bash
openclaw skills install git:RTPI-ltc/Task-Compass-Skill@v0.3.0 --as task-compass
```

OpenClaw discovers `SKILL.md` at the repository root. When the task matches the trigger description, the agent can invoke `scripts/route_task.py`, inspect the validated JSON, and build its plan without changing OpenClaw source code.

This is the recommended portable integration.

## Native Runtime Plugin

Version 0.3 publishes
`task-compass-openclaw-native-v0.3.0.tar.gz` for OpenClaw
`>=2026.6.11 <2026.7.0`:

```bash
openclaw plugins install ./task-compass-openclaw-native-v0.3.0.tar.gz
openclaw plugins inspect task-compass --runtime --json
```

Upgrade from the v0.2 native plugin with an explicit replacement:

```bash
openclaw plugins uninstall route-openclaw-task
openclaw plugins install ./task-compass-openclaw-native-v0.3.0.tar.gz
```

Do not install both native plugin archives side by side; OpenClaw preserves the
old installation directory and both prompt hooks would remain active.

The plugin registers a single `before_prompt_build` hook and embeds this Skill.
The hook invokes `route_task.py` with Node `execFile`, a bounded prompt length,
a timeout, a 1 MiB output cap, and a minimal environment. It appends a bounded
advisory decision and falls back without changing the baseline planner if the
router fails. It has no execution tool, service, provider, channel, network
client, or credential access.

The v0.3 release gate installs the archive into the official OpenClaw
`2026.6.11` image, loads the runtime, verifies the typed hook and embedded
Skill, and executes the installed bridge with networking disabled and a
read-only root filesystem.

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

The reference research integration loads the workspace skill when `OPENCLAW_PLANNER_SKILL=task-compass`, emits `planner_skill_route` and `planner_skill_candidates` audit events, expands missing executor candidates, and passes a bounded `desired_tools_override` into A*/Reflexion search. The old `route-openclaw-task` value remains supported by the bundled compatibility Skill.

This adapter is validated against the `LocalAuditPlanner` implementation in `hopercheche/openclaw_optimization`. It is not claimed to be a stable upstream OpenClaw extension point. The v0.3 adapter bundle records the exact target file fingerprints and refuses an upstream-portability claim. Consumers should use the native plugin or JSON contract unless they maintain the same planner API.

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
openclaw skills install git:RTPI-ltc/Task-Compass-Skill@v0.3.0 --as task-compass
```

For rollback, reinstall the previous tag. Git-installed skills are reinstalled to update; OpenClaw's tracked `skills update` flow applies to ClawHub installs.
