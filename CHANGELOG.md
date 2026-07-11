# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow semantic versioning.

## [Unreleased]

## [0.2.0] - 2026-07-11

### Added

- Version-constrained OpenClaw native plugin with a fail-open `before_prompt_build` adapter.
- Standard Codex and Claude Code plugin bundles built from the same hash-locked core Skill.
- Version-locked `LocalAuditPlanner` research adapter, explicitly separated from upstream OpenClaw.
- Reproducible multi-host bundle builder, offline validators, and a 240-case integration-contract benchmark.
- Official OpenClaw container gate for native installation, runtime hook loading, Skill discovery, and bridge execution.

### Changed

- Updated and SHA-pinned the GitHub Actions toolchain to Checkout 7.0.0, Setup Python 6.3.0, CodeQL 4.37.0, and Action GH Release 3.0.1; future Action updates are grouped into one Dependabot PR.
- Bumped release metadata to 0.2.0 while preserving the v0.1.0 router, model tables, and routing contract byte-for-byte.

## [0.1.0] - 2026-07-11

### Added

- Deterministic task router with single-task and JSONL CLIs.
- Planner profile, executor, policy, context, model-tier, and next-action output.
- Structured tool-catalog dependency closure with distraction-tool resistance.
- Public, license-reviewed Naive Bayes profile and tool-family models.
- Stable routing contract, model card, security policy, and OpenClaw integration guide.
- Offline test suite, release verifier, CI matrix, CodeQL, and tagged archive workflow.
- ToolSandbox and 1,000-task aggregate benchmark evidence.

[Unreleased]: https://github.com/RTPI-ltc/route-openclaw-task/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/RTPI-ltc/route-openclaw-task/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/RTPI-ltc/route-openclaw-task/releases/tag/v0.1.0
