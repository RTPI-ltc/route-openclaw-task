# LocalAuditPlanner adapter

This adapter is for the research `LocalAuditPlanner` implementation in
`hopercheche/openclaw_optimization`, not for upstream OpenClaw. It loads the
workspace Skill, validates the route, maps at most two execution dependencies
into a bounded planner target, and falls back without raising into the runtime.

Use it only when the target files match the fingerprints in `integration.json`.
Install the unchanged Skill at `skills/route-openclaw-task`, place
`planner_skill_adapter.py` under `backend/openclaw/`, retain the corresponding
planner/search-planner call sites, and enable it with:

```bash
OPENCLAW_PLANNER_SKILL=route-openclaw-task
```

Do not apply this file blindly to another planner API. Upstream OpenClaw users
should use the native plugin bundle instead.
