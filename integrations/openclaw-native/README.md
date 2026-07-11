# OpenClaw native integration

This package adds the unchanged `route-openclaw-task` Skill and a thin
`before_prompt_build` adapter. The adapter invokes the bundled Python router
with `execFile` (never a shell), appends only a bounded route decision, and
falls back to the baseline planner when routing fails.

Supported host range: OpenClaw `>=2026.6.11 <2026.7.0`. The release gate tests
the exact official `2026.6.11` image digest recorded in
`../compatibility.json` with networking disabled.

Runtime permission checks remain authoritative. The adapter does not register
execution tools, generate commands, access the network, or read API keys.
