#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


MAX_TEXT_BYTES = 5 * 1024 * 1024
SKIP_PARTS = {".git", "__pycache__", ".pytest_cache", ".ruff_cache", "dist", "build"}
ALLOWED_TEMPLATE_NAMES = {
    ".env.example",
    ".env.sample",
    ".env.template",
}
SENSITIVE_BASENAMES = {
    ".env",
    ".envrc",
    ".netrc",
    ".npmrc",
    ".pypirc",
    ".vault-token",
    "_netrc",
    "auth.json",
    "client_secret.json",
    "credentials.json",
    "config.json",
    "kubeconfig",
    "token.json",
    "tokens.json",
}
SENSITIVE_SUFFIXES = {
    ".der",
    ".jks",
    ".key",
    ".keystore",
    ".ovpn",
    ".p12",
    ".pem",
    ".pfx",
    ".secret",
    ".secrets",
    ".tfstate",
    ".tfvars",
    ".token",
}
SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    "openai_style_key": re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9._/+=-]{16,}"),
    "anthropic_key": re.compile(r"(?<![A-Za-z0-9])sk-ant-[A-Za-z0-9._/+=-]{16,}"),
    "github_token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "google_api_key": re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "stripe_live_key": re.compile(r"\b(?:sk|rk)_live_[A-Za-z0-9]{16,}\b"),
    "huggingface_token": re.compile(r"\bhf_[A-Za-z0-9]{24,}\b"),
    "credential_url": re.compile(r"https?://[^\s/:@]+:[^\s/@]+@[^\s]+"),
}
ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password|credential)\b"
    r"\s*[:=]\s*[\"']?([^\s\"',}\]]{12,})"
)


@dataclass(frozen=True)
class Finding:
    kind: str
    path: str
    source: str


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan tracked files and optional Git history for secrets.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--history", action="store_true", help="Also scan every unique blob in Git history.")
    args = parser.parse_args()
    root = args.root.resolve()
    findings = scan_repository(root, history=args.history)
    print(
        json.dumps(
            {
                "root": str(root),
                "history_scanned": args.history,
                "valid": not findings,
                "findings": [asdict(finding) for finding in findings],
            },
            indent=2,
            sort_keys=True,
        )
    )
    raise SystemExit(1 if findings else 0)


def scan_repository(root: Path, *, history: bool = False) -> list[Finding]:
    findings: set[Finding] = set()
    for relative, data in _working_tree_files(root):
        findings.update(_scan_one(relative, data, "working-tree"))
    if history:
        findings.update(_scan_history(root))
    return sorted(findings, key=lambda item: (item.source, item.path, item.kind))


def scan_filesystem(root: Path) -> list[Finding]:
    findings: set[Finding] = set()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if set(Path(relative).parts).intersection(SKIP_PARTS):
            continue
        if path.is_symlink():
            findings.add(Finding("symlink", relative, "filesystem"))
            continue
        findings.update(_scan_one(relative, path.read_bytes(), "filesystem"))
    return sorted(findings, key=lambda item: (item.path, item.kind))


def scan_paths(root: Path, paths: Iterable[Path], *, source: str) -> list[Finding]:
    findings: set[Finding] = set()
    for path in paths:
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            findings.add(Finding("symlink", relative, source))
            continue
        findings.update(_scan_one(relative, path.read_bytes(), source))
    return sorted(findings, key=lambda item: (item.path, item.kind))


def _working_tree_files(root: Path) -> Iterable[tuple[str, bytes]]:
    if (root / ".git").exists():
        result = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            check=True,
            capture_output=True,
        )
        for raw in result.stdout.split(b"\0"):
            if not raw:
                continue
            relative = raw.decode("utf-8", errors="surrogateescape")
            path = root / relative
            if path.is_file():
                yield relative, path.read_bytes()
        return
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if not set(Path(relative).parts).intersection(SKIP_PARTS):
            yield relative, path.read_bytes()


def _scan_history(root: Path) -> set[Finding]:
    name_result = subprocess.run(
        ["git", "log", "--all", "--pretty=format:", "--name-only", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    findings: set[Finding] = set()
    for raw_path in name_result.stdout.split(b"\0"):
        path = raw_path.decode("utf-8", errors="surrogateescape").strip()
        if path and _sensitive_path(path):
            findings.add(Finding("sensitive_filename", path, "git-history-name"))

    result = subprocess.run(
        ["git", "rev-list", "--objects", "--all"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    seen: set[str] = set()
    for line in result.stdout.splitlines():
        object_id, separator, path = line.partition(" ")
        if not separator or object_id in seen:
            continue
        seen.add(object_id)
        kind = subprocess.run(
            ["git", "cat-file", "-t", object_id],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if kind != "blob":
            continue
        data = subprocess.run(
            ["git", "cat-file", "blob", object_id],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
        findings.update(_scan_one(path, data, f"git:{object_id[:12]}"))
    return findings


def _scan_one(path: str, data: bytes, source: str) -> set[Finding]:
    findings: set[Finding] = set()
    if _sensitive_path(path):
        findings.add(Finding("sensitive_filename", path, source))
    if len(data) > MAX_TEXT_BYTES or b"\0" in data:
        return findings
    text = data.decode("utf-8", errors="replace")
    for name, pattern in SECRET_PATTERNS.items():
        if pattern.search(text):
            findings.add(Finding(name, path, source))
    for match in ASSIGNMENT_PATTERN.finditer(text):
        if not _is_placeholder(match.group(1)):
            findings.add(Finding("credential_assignment", path, source))
            break
    return findings


def _sensitive_path(path: str) -> bool:
    relative = Path(path)
    name = relative.name.lower()
    if name in ALLOWED_TEMPLATE_NAMES or name.endswith((".env.example", ".env.sample", ".env.template")):
        return False
    if name in SENSITIVE_BASENAMES or name.startswith(
        ("client_secret", "id_rsa", "id_ed25519", "oauth")
    ):
        return True
    if relative.suffix.lower() in SENSITIVE_SUFFIXES:
        return True
    parts = {part.lower() for part in relative.parts}
    return bool(parts.intersection({".direnv", ".secrets", ".terraform", "secrets", "credentials"}))


def _is_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    return (
        lowered in {"changeme", "placeholder", "redacted", "example-value"}
        or lowered.startswith(("${", "<", "your-", "your_", "example", "test-", "dummy-"))
        or set(lowered) <= {"*", "x", "-", "_"}
    )


if __name__ == "__main__":
    main()
