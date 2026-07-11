# Architecture

## Design Goal

The router answers one bounded question before planning: which planner profile, executor families, context policy, permission behavior, and next action best fit this task?

It deliberately does not generate commands, tool arguments, or final answers.

## Decision Pipeline

1. Normalize whitespace and preserve the original task text for audit output.
2. Split an optional `Available tool interfaces:` catalog from the user intent.
3. Extract deterministic signals such as explicit executor hints, read-only constraints, terminal context, mobile/MCP affordances, production intent, and safety terms.
4. Resolve known catalog dependencies. If a required dependency is unavailable, abstain and replan.
5. Query the bundled Naive Bayes priors only where deterministic evidence is incomplete.
6. Apply precedence rules: explicit constraints, terminal/local artifacts, structured catalog closure, external-tool merge, then learned fallback.
7. Derive policy mode, safety guard, permission behavior, context policy, model tier, next action, and a bounded planner path.
8. Validate the output schema before returning JSON.

## Precedence

```text
explicit safety/refusal
  > explicit executor hints
  > structured tool dependency closure
  > terminal and local-artifact rules
  > deterministic mobile/MCP/deploy signals
  > learned profile/tool/policy priors
  > conservative replan fallback
```

The precedence is intentional. A statistical prediction cannot disable an explicit safety guard or read-only boundary.

## Models

Both bundled models are JSON token-count tables consumed by a standard-library multinomial Naive Bayes implementation. There is no pickle, dynamic import, native extension, model server, or downloaded code.

- The profile model provides broad planner, executor, and policy priors.
- The tool-family model handles unfamiliar structured tool catalogs.

See [the model card](../references/model-card.md) for provenance and limitations.

## OpenClaw Boundary

The router returns advisory JSON. In the standard skill flow, the agent reads the decision before constructing its plan. In the optional deep integration, the decision becomes a bounded desired-tool constraint for `LocalAuditPlanner` search.

OpenClaw remains responsible for:

- candidate generation;
- A*/Reflexion or other path search;
- permission and confirmation decisions;
- tool execution;
- verifier feedback;
- audit persistence.

## Failure Modes

- **Unknown task:** low confidence produces `replan` with expanded context.
- **Missing tool dependency:** no executor is selected; the route abstains.
- **Mutation under restrictive permission mode:** permission behavior becomes `ask` or `deny`.
- **Malformed model asset:** the CLI exits non-zero with a bounded error.
- **Invalid output:** schema validation prevents emission.

## Extension Points

- Add deterministic catalog dependencies in `scripts/route_task.py` with paired distractor tests.
- Retrain the public profile prior only from license-reviewed dev data.
- Add executor families only after updating the routing contract, validators, tests, and promotion gates.
- Integrate a new planner by consuming the stable JSON contract instead of importing internal router functions.

