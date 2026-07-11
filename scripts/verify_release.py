#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from validate_skill import validate as validate_skill  # noqa: E402


REQUIRED_FILES = {
    "SKILL.md",
    "README.md",
    "README.zh-CN.md",
    "LICENSE",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "THIRD_PARTY_NOTICES.md",
    "scripts/route_task.py",
    "scripts/validate_route.py",
    "assets/profile-policy-model.json",
    "assets/tool-family-model.json",
    "references/routing-contract.md",
    "references/model-card.md",
    "benchmarks/manifest.json",
    "benchmarks/toolsandbox-integrated.json",
    "benchmarks/toolsandbox-router.json",
    "benchmarks/generalization-1k.json",
}
SECRET_PATTERNS = {
    "private_key": re.compile(r"BEGIN [A-Z ]*PRIVATE KEY"),
    "openai_style_key": re.compile(r"(^|[^A-Za-z])sk-[A-Za-z0-9_\-]{16,}"),
    "aws_access_key": re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
}
MODEL_SENSITIVE_PATTERNS = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "ipv4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "url": re.compile(r"https?://[^\s\"<>]+"),
}
MARKDOWN_LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify release integrity, privacy, and benchmark gates.")
    parser.add_argument("root", type=Path, nargs="?", default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    errors = verify(root)
    print(json.dumps({"root": str(root), "valid": not errors, "errors": errors}, indent=2))
    raise SystemExit(1 if errors else 0)


def verify(root: Path) -> list[str]:
    errors = validate_skill(root)
    missing = sorted(path for path in REQUIRED_FILES if not (root / path).is_file())
    if missing:
        errors.append(f"missing release files: {missing}")
    symlinks = [path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_symlink()]
    if symlinks:
        errors.append(f"release must not contain symlinks: {symlinks}")
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.stat().st_size > 3 * 1024 * 1024:
            errors.append(f"file exceeds 3 MiB release limit: {path.relative_to(root)}")
        if _is_text(path):
            text = path.read_text(encoding="utf-8", errors="replace")
            for name, pattern in SECRET_PATTERNS.items():
                if pattern.search(text):
                    errors.append(f"{name} pattern in {path.relative_to(root)}")
    _verify_models(root, errors)
    _verify_runtime(root, errors)
    _verify_benchmarks(root, errors)
    _verify_release_manifest(root, errors)
    _verify_markdown_links(root, errors)
    return errors


def _verify_models(root: Path, errors: list[str]) -> None:
    for relative in ("assets/profile-policy-model.json", "assets/tool-family-model.json"):
        path = root / relative
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if "evaluation" in payload:
            errors.append(f"raw evaluation section present in {relative}")
        rendered = json.dumps(payload, ensure_ascii=False)
        for name, pattern in MODEL_SENSITIVE_PATTERNS.items():
            if pattern.search(rendered):
                errors.append(f"{name} literal present in {relative}")
    profile_path = root / "assets/profile-policy-model.json"
    if profile_path.is_file():
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        sources = set(profile.get("training_summary", {}).get("source_counts", {}))
        if "terminalworld_safe_network" in sources:
            errors.append("public profile model must not train on TerminalWorld task rows")
        if profile.get("release_metadata", {}).get("raw_examples_included") is not False:
            errors.append("profile model must declare raw_examples_included=false")


def _verify_runtime(root: Path, errors: list[str]) -> None:
    path = root / "scripts/route_task.py"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    forbidden = ["import requests", "import subprocess", "import socket", "os.system(", "pickle.load("]
    for marker in forbidden:
        if marker in text:
            errors.append(f"forbidden runtime capability in route_task.py: {marker}")


def _verify_benchmarks(root: Path, errors: list[str]) -> None:
    paths = {
        "toolsandbox-router.json": (0.90, 0.80),
        "generalization-1k.json": (0.99, 0.99),
    }
    for name, (overall_gate, holdout_gate) in paths.items():
        path = root / "benchmarks" / name
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        overall = float(payload["summary"]["task_route_success_rate"])
        holdout = float(payload["split_summary"]["holdout"]["task_route_success_rate"])
        schema = float(payload["summary"]["schema_valid_rate"])
        if overall < overall_gate or holdout < holdout_gate or schema != 1.0:
            errors.append(
                f"benchmark gate failed for {name}: overall={overall}, holdout={holdout}, schema={schema}"
            )
    integrated = root / "benchmarks/toolsandbox-integrated.json"
    if integrated.is_file():
        payload = json.loads(integrated.read_text(encoding="utf-8"))
        summary = payload["optimized"]["summary"]
        holdout = payload["optimized"]["split_summary"]["holdout"]
        if float(summary["route_success_rate"]) < 0.90 or float(holdout["route_success_rate"]) < 0.80:
            errors.append("integrated ToolSandbox promotion gate failed")
        if float(summary["safety_rate"]) != 1.0 or float(summary["qwen_success_rate"]) != 1.0:
            errors.append("integrated ToolSandbox safety/model gate failed")


def _verify_markdown_links(root: Path, errors: list[str]) -> None:
    for path in sorted(root.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK_PATTERN.findall(text):
            target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            relative = target.split("#", 1)[0].split("?", 1)[0]
            resolved = (path.parent / relative).resolve()
            try:
                resolved.relative_to(root)
            except ValueError:
                errors.append(f"markdown link escapes release root in {path.relative_to(root)}: {target}")
                continue
            if not resolved.exists():
                errors.append(f"broken markdown link in {path.relative_to(root)}: {target}")


def _verify_release_manifest(root: Path, errors: list[str]) -> None:
    path = root / "release-manifest.json"
    if not path.is_file():
        errors.append("missing release-manifest.json")
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    validation = payload.get("compatibility_validation", {})
    if validation.get("openclaw_version") != "2026.6.11":
        errors.append("release manifest must record the tested OpenClaw version")
    required = ("network_disabled", "read_only_root", "skill_eligible", "offline_route_executed")
    if not all(validation.get(key) is True for key in required):
        errors.append("release manifest has incomplete OpenClaw compatibility evidence")


def _is_text(path: Path) -> bool:
    return path.suffix.lower() in {"", ".cff", ".json", ".md", ".py", ".txt", ".yaml", ".yml"}


if __name__ == "__main__":
    main()
