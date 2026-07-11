# Contributing

Contributions are welcome when they improve a repeatable routing workflow rather than one benchmark item.

## Development Setup

```bash
git clone https://github.com/RTPI-ltc/route-openclaw-task.git
cd route-openclaw-task
python3 -m unittest discover -s tests -v
python3 scripts/validate_skill.py .
python3 scripts/verify_release.py .
```

No third-party runtime or test dependency is required.

## Behavior Changes

For a routing change:

1. Add a positive trigger case.
2. Add a nearby negative or distraction case.
3. Assert safety, permission behavior, executor coverage, and step budget.
4. Run the full offline test suite.
5. If the change affects a benchmark family, report dev and holdout metrics separately.

Do not tune directly against holdout task text. Do not add raw third-party prompts, credentials, private logs, or model responses to the repository.

## Model Changes

Model updates must include:

- a license-reviewed source manifest;
- dev-only final training;
- aggregate held-out metrics;
- zero sensitive-literal findings;
- an updated model card;
- both benchmark promotion gates passing.

Executable model formats such as pickle are not accepted.

## Pull Requests

Keep changes focused. Explain the routing failure being fixed, why the rule generalizes, which tests prove it, and any known tradeoff. CI must pass on every supported Python version.

By contributing, you agree that your contribution is licensed under the repository's MIT License.
