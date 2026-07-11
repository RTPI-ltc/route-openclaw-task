#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from validate_skill import validate as validate_skill  # noqa: E402
from scan_secrets import scan_filesystem  # noqa: E402


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
    "docs/INTEGRATIONS.md",
    "integrations/compatibility.json",
    "integrations/openclaw-native/openclaw.plugin.json",
    "integrations/openclaw-native/package.json",
    "integrations/openclaw-native/index.mjs",
    "integrations/codex/.codex-plugin/plugin.json",
    "integrations/claude-code/.claude-plugin/plugin.json",
    "scripts/build_integrations.py",
    "scripts/validate_integrations.py",
    "scripts/benchmark_integrations.py",
    "scripts/scan_secrets.py",
    "benchmarks/manifest.json",
    "benchmarks/toolsandbox-integrated.json",
    "benchmarks/toolsandbox-router.json",
    "benchmarks/generalization-1k.json",
    "benchmarks/integrations-v0.3.json",
}
SECRET_PATTERNS = {
    "private_key": re.compile(r"BEGIN [A-Z ]*PRIVATE KEY"),
    "openai_style_key": re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9._/+=-]{16,}"),
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
    for finding in scan_filesystem(root):
        errors.append(f"secret scan finding {finding.kind} in {finding.path}")
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
    integrations = root / "benchmarks/integrations-v0.3.json"
    if integrations.is_file():
        payload = json.loads(integrations.read_text(encoding="utf-8"))
        if int(payload.get("case_generation", {}).get("cases", 0)) < 200:
            errors.append("integration benchmark must contain at least 200 cases")
        for host, metrics in payload.get("hosts", {}).items():
            if float(metrics.get("exact_core_parity", 0.0)) != 1.0:
                errors.append(f"integration exact-core parity failed for {host}")
            if float(metrics.get("schema_valid_rate", 0.0)) != 1.0:
                errors.append(f"integration schema gate failed for {host}")
            if float(metrics.get("safety_invariant_rate", 0.0)) != 1.0:
                errors.append(f"integration safety-field gate failed for {host}")
    manifest_path = root / "benchmarks/manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for name, expected in manifest.get("files", {}).items():
            evidence = root / "benchmarks" / name
            if not evidence.is_file():
                errors.append(f"benchmark manifest references missing file: {name}")
                continue
            actual = hashlib.sha256(evidence.read_bytes()).hexdigest()
            if actual != expected:
                errors.append(f"benchmark evidence hash mismatch: {name}")


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
    if payload.get("name") != "task-compass" or payload.get("version") != "0.3.0":
        errors.append("release manifest name/version must be task-compass 0.3.0")
    validation = payload.get("compatibility_validation", {})
    if validation.get("openclaw_version") != "2026.6.11":
        errors.append("release manifest must record the tested OpenClaw version")
    required = (
        "network_disabled",
        "read_only_root",
        "skill_eligible",
        "offline_route_executed",
        "native_plugin_installed",
        "native_plugin_runtime_loaded",
        "before_prompt_build_hook_registered",
        "embedded_skill_eligible",
        "installed_bridge_executed",
        "tracked_secret_scan_passed",
        "git_history_secret_scan_passed",
        "sensitive_filename_gate_passed",
    )
    if not all(validation.get(key) is True for key in required):
        errors.append("release manifest has incomplete OpenClaw compatibility evidence")
    integrations = payload.get("integration_validation", {})
    if integrations.get("openclaw", {}).get("native_host_executed") is not True:
        errors.append("release manifest must record native OpenClaw execution")
    for host in ("codex", "claude_code"):
        if integrations.get(host, {}).get("native_host_executed") is not False:
            errors.append(f"release manifest must not claim native {host} execution")
    migration = payload.get("name_migration", {})
    if migration.get("canonical_skill") != "task-compass":
        errors.append("release manifest canonical skill must be task-compass")
    if migration.get("legacy_skill") != "route-openclaw-task":
        errors.append("release manifest legacy skill must be route-openclaw-task")
    if migration.get("legacy_repository") != "RTPI-ltc/route-openclaw-task":
        errors.append("release manifest must record the legacy repository name")
    if not all(
        migration.get(key) is True
        for key in (
            "legacy_skill_packaged",
            "openclaw_legacy_plugin_id_declared",
            "safe_native_upgrade_e2e_passed",
            "repository_renamed",
            "legacy_repository_redirect_verified",
        )
    ):
        errors.append("release manifest has incomplete name-migration evidence")
    if migration.get("side_by_side_native_upgrade_supported") is not False:
        errors.append("release manifest must reject side-by-side native plugin upgrades")
    source_hashes = payload.get("source_hashes", {})
    source_files = {
        "SKILL.md": "SKILL.md",
        "route_task.py": "scripts/route_task.py",
        "profile-policy-model.json": "assets/profile-policy-model.json",
        "tool-family-model.json": "assets/tool-family-model.json",
        "routing-contract.md": "references/routing-contract.md",
    }
    for name, relative in source_files.items():
        actual = hashlib.sha256((root / relative).read_bytes()).hexdigest()
        if source_hashes.get(name) != actual:
            errors.append(f"release source hash mismatch for {name}")


def _is_text(path: Path) -> bool:
    return path.suffix.lower() in {"", ".cff", ".json", ".md", ".py", ".txt", ".yaml", ".yml"}


if __name__ == "__main__":
    main()
