# Model Card

## Summary

`route-openclaw-task` bundles two small multinomial Naive Bayes classifiers implemented with the Python standard library:

- `profile-policy-model.json` predicts a planner profile, executor family, and policy prior for general task requests.
- `tool-family-model.json` is a focused fallback for tasks that expose an `Available tool interfaces:` catalog.

Deterministic rules remain authoritative for explicit execution hints, read-only constraints, incomplete tool dependencies, and high-risk actions. The models do not execute tools and do not override OpenClaw permissions.

## Public Profile Model

- Model type: token-count multinomial Naive Bayes.
- Final training examples: 626 dev examples.
- Evaluation examples: 138 held-out examples.
- Raw training or evaluation rows bundled: no.
- Raw prompts stored in model weights: no.
- Sensitive-literal scan: email, IPv4, URL, private-key marker, and common API-key shapes; passed.

Training data comes from a license-reviewed slice:

| Source | Rows | License |
|---|---:|---|
| PhoneHarness | 144 | Apache-2.0 |
| PhoneHarness synthetic | 250 | Apache-2.0 |
| [tau2-bench](https://github.com/sierra-research/tau2-bench) | 184 | MIT |
| [ToolBench](https://github.com/OpenBMB/ToolBench) | 100 | Apache-2.0 |
| [SkillsBench](https://github.com/benchflow-ai/skillsbench) | 11 | Apache-2.0 |
| Project-authored terminal templates | 75 | MIT |

TerminalWorld task rows were excluded from model training because its dataset license changed across releases. Explicit TerminalWorld-style routing is covered by project-authored templates and deterministic terminal markers instead.

Held-out classifier accuracy:

| Field | Accuracy |
|---|---:|
| Planner profile | 98.55% |
| Execution tools | 86.23% |
| Policy mode | 78.26% |

Runtime routing is guarded by deterministic rules, so field accuracy is not the promotion metric. On the frozen 1,000-task generalization suite, the public model plus router reaches 99.90% task-route success and 100.00% holdout task-route success.

## Tool-Family Model

The tool-family fallback was trained on 106 ToolSandbox dev source groups using only the no-distraction variant. ToolSandbox holdout groups were excluded. It predicts no executor, MCP, mobile CLI, or a combined MCP/mobile CLI route when deterministic dependency closure does not recognize the catalog.

ToolSandbox is distributed under Apple's repository license. The public package includes the required third-party notice and aggregate benchmark evidence, but not ToolSandbox task rows.

## Limitations

- The router selects executor families, not concrete commands or tool arguments.
- Policy output is an advisory prior. The runtime permission engine remains the final authority.
- The ToolSandbox evaluation simulates tool selection; it does not prove real-device or real-account execution correctness.
- Languages and tools outside the bundled training distribution may be routed conservatively to `replan`.
- The published model is intentionally small and auditable. It is not a replacement for a generative planner.

## Promotion Gates

A public model change must pass all of the following before release:

1. Schema validity is 100% on both benchmark suites.
2. The 1,000-task generalization suite remains at or above 99.0% task-route success and 99.0% holdout success.
3. ToolSandbox remains at or above 90.0% overall task-route success and 80.0% holdout success.
4. Required executor coverage does not regress.
5. Sensitive-literal scanning reports zero findings.
6. Safety and permission invariants pass the deterministic test suite.
