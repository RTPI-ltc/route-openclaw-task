# Host Integrations

Version 0.3 packages one hash-locked Skill for multiple agent hosts. The
router, model tables, and routing contract are byte-identical to v0.1.0; each
adapter only handles host discovery, invocation, bounded context transfer, and
failure fallback.

## Compatibility matrix

| Host | Constraint | Package | Validation | Native host run |
|---|---|---|---|---:|
| OpenClaw | `>=2026.6.11 <2026.7.0` | native plugin | official container E2E | Yes |
| Codex | `.codex-plugin/plugin.json` contract, 2026-07-11 snapshot | plugin bundle | official manifest validator + offline contract E2E | No |
| Claude Code | `>=2.1.142 <3.0.0` | plugin bundle | hash-locked schema + offline contract E2E | No |
| LocalAuditPlanner fork | exact API fingerprints | Python adapter | adapter contract + prior task benchmark | Yes |

The Codex package was not installed into or invoked through the owner's Codex
environment. Claude Code was not installed or started. Those rows therefore do
not claim native runtime execution. Their evidence proves package discovery
shape, manifest contract, embedded core identity, and router execution from the
built package.

## OpenClaw native plugin

Install the `task-compass-openclaw-native-v0.3.0.tar.gz` release asset:

```bash
openclaw plugins install ./task-compass-openclaw-native-v0.3.0.tar.gz
openclaw plugins inspect task-compass --runtime --json
```

The plugin registers only `before_prompt_build`. It invokes the bundled Python
router with `execFile`, forwards no ambient secrets, returns a bounded advisory
JSON context, and falls back to the unmodified planner on timeout or error. It
registers no tools, services, providers, channels, or network clients.

The release gate uses the exact official image digest in
`integrations/compatibility.json` with networking disabled, a read-only root
filesystem, all Linux capabilities dropped, and `no-new-privileges`.

## Codex bundle

The `task-compass-codex-v0.3.0.tar.gz` asset contains:

```text
.codex-plugin/plugin.json
skills/task-compass/SKILL.md
skills/task-compass/scripts/...
skills/task-compass/assets/...
skills/route-openclaw-task/SKILL.md  # compatibility alias
```

It does not contain hooks, MCP servers, apps, credentials, or host
configuration. Installation is intentionally left to the target Codex
environment; v0.3 validation does not mutate the owner's Codex setup.

## Claude Code bundle

The `task-compass-claude-code-v0.3.0.tar.gz` asset uses the standard
`.claude-plugin/plugin.json` plus `skills/` layout. Its declared compatibility
range is `>=2.1.142 <3.0.0`. The official manifest schema snapshot URL,
generation timestamp, and SHA-256 are recorded in the compatibility contract.

The package can be tested by an operator in a separate Claude Code environment
using that host's `--plugin-dir` flow. This project did not execute that command
for v0.3.

## LocalAuditPlanner adapter

`local-audit-planner` is a deep adapter for the research Python planner, not an
upstream OpenClaw API. It must only be used when the target `planner.py` and
`search_planner.py` match the recorded fingerprints. The native OpenClaw plugin
is the portable integration.

## Contract benchmark

`scripts/benchmark_integrations.py` builds 240 safe synthetic task variations
and executes the router from each generated host bundle. Promotion requires:

- 100% schema validity;
- 100% exact parity with the root Skill;
- 100% preservation of policy, permission, next-action, and safety fields;
- unchanged v0.1 behavioral-core hashes.

This integration benchmark proves packaging and adapter parity. Capability
quality remains grounded in the separate 258-task ToolSandbox and 1,000-task
generalization evaluations.

## Name migration

`task-compass` is the canonical Skill and plugin id from v0.3 onward. Bundles
also contain a low-trigger compatibility Skill named `route-openclaw-task`,
and the OpenClaw manifest declares that id in `legacyPluginIds`. Existing
explicit calls and `OPENCLAW_PLANNER_SKILL=route-openclaw-task` remain valid;
new integrations should use `task-compass`.

OpenClaw does not automatically delete an installed legacy plugin directory.
For a native-plugin upgrade, uninstall `route-openclaw-task` before installing
the v0.3 `task-compass` archive. Side-by-side native installation is not a
supported migration path because both plugins would register prompt hooks.
