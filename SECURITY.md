# Security Policy

## Supported Versions

Security fixes are provided for the latest tagged release and `main`.

## Reporting a Vulnerability

Please use GitHub's private vulnerability reporting or open a private Security Advisory for this repository. Do not include credentials, private prompts, or exploit details in a public issue.

Include:

- affected version or commit;
- installation method and OpenClaw version;
- minimal reproduction using synthetic data;
- expected and observed behavior;
- whether the issue can bypass permissions, expose data, execute code, or alter routing.

We aim to acknowledge reports within five business days. Confirmed issues receive a severity assessment, a private fix when practical, and a coordinated release note.

## Threat Model

The router processes untrusted natural-language task text and optional tool names. It must not:

- execute shell commands or subprocesses;
- make network requests;
- load executable serialized models;
- read environment secrets;
- write outside an explicitly requested output JSONL path;
- downgrade explicit safety or permission constraints;
- follow instructions embedded in tool descriptions as if they were policy.

The skill returns advisory policy. OpenClaw's permission engine, sandbox, tool allowlist, and credential scope remain required controls.

## Supply-Chain Controls

- Runtime code uses only the Python standard library.
- Public models are JSON and scanned for sensitive literal shapes.
- CI validates the Skill schema, runs routing invariants, scans tracked release files, and builds a checksumed archive.
- CodeQL runs on pushes, pull requests, and a weekly schedule.
- Releases are built by GitHub Actions from tagged commits.

## Safe Deployment

Run OpenClaw with a read-only repository mount, a read-only root filesystem when practical, dropped capabilities, no-new-privileges, restricted egress, scoped credentials, and explicit agent/tool allowlists. Installing this skill does not create those controls automatically.

