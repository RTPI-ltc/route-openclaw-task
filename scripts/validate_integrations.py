#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
PACKAGE_NAME = "task-compass"
CANONICAL_SKILL_NAME = "task-compass"
LEGACY_SKILL_NAME = "route-openclaw-task"


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate built host integration bundles.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--build-dir", type=Path, default=Path("dist/integrations"))
    parser.add_argument("--codex-validator", type=Path)
    parser.add_argument("--claude-schema", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    build_dir = args.build_dir if args.build_dir.is_absolute() else root / args.build_dir
    errors = validate_integrations(root, build_dir, args.codex_validator, args.claude_schema)
    print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
    raise SystemExit(1 if errors else 0)


def validate_integrations(
    root: Path,
    build_dir: Path,
    codex_validator: Path | None = None,
    claude_schema: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    compatibility = _load_json(root / "integrations/compatibility.json", errors)
    if compatibility is None:
        return errors
    version = compatibility.get("release_version")
    if not isinstance(version, str) or SEMVER.fullmatch(version) is None:
        errors.append("compatibility release_version must be strict semver")
        return errors
    locked = compatibility.get("core_skill", {}).get("locked_files", {})
    if not isinstance(locked, dict) or not locked:
        errors.append("compatibility core lock is missing")
    else:
        _verify_hashes(root, locked, "core", errors)

    bundles = {
        name: build_dir / f"{PACKAGE_NAME}-{name}-v{version}"
        for name in ("openclaw-native", "codex", "claude-code", "local-audit-planner")
    }
    for name, bundle in bundles.items():
        if not bundle.is_dir():
            errors.append(f"missing built bundle: {name}")
            continue
        _reject_symlinks(bundle, name, errors)
        copied_contract = _load_json(bundle / "compatibility.json", errors)
        if copied_contract != compatibility:
            errors.append(f"{name}: copied compatibility contract differs from source")
        if name != "local-audit-planner":
            canonical = bundle / "skills" / CANONICAL_SKILL_NAME
            legacy = bundle / "skills" / LEGACY_SKILL_NAME
            _verify_hashes(canonical, locked, f"{name} canonical skill", errors)
            _verify_hashes(legacy, locked, f"{name} legacy skill", errors)
            _smoke_router(canonical, f"{name} canonical", errors)
            _smoke_router(legacy, f"{name} legacy", errors)

    if bundles["openclaw-native"].is_dir():
        _validate_openclaw(bundles["openclaw-native"], version, errors)
    if bundles["codex"].is_dir():
        _validate_codex(bundles["codex"], version, errors)
        if codex_validator is not None:
            _run_codex_validator(codex_validator, bundles["codex"], errors)
    if bundles["claude-code"].is_dir():
        _validate_claude(
            bundles["claude-code"],
            compatibility,
            version,
            errors,
            claude_schema,
        )
    if bundles["local-audit-planner"].is_dir():
        _validate_local_audit(bundles["local-audit-planner"], errors)
    return errors


def _validate_openclaw(bundle: Path, version: str, errors: list[str]) -> None:
    manifest = _load_json(bundle / "openclaw.plugin.json", errors)
    package = _load_json(bundle / "package.json", errors)
    if manifest is None or package is None:
        return
    if manifest.get("id") != PACKAGE_NAME:
        errors.append("openclaw: incorrect plugin id")
    if manifest.get("legacyPluginIds") != [LEGACY_SKILL_NAME]:
        errors.append("openclaw: legacy plugin id is missing")
    if manifest.get("version") != version or package.get("version") != version:
        errors.append("openclaw: package and manifest versions must match release")
    if manifest.get("skills") != ["./skills"]:
        errors.append("openclaw: manifest must declare ./skills")
    schema = manifest.get("configSchema")
    if not isinstance(schema, dict) or schema.get("additionalProperties") is not False:
        errors.append("openclaw: configSchema must reject additional properties")
    if package.get("peerDependencies", {}).get("openclaw") != ">=2026.6.11 <2026.7.0":
        errors.append("openclaw: host peer dependency is not version constrained")
    if package.get("name") != manifest.get("id"):
        errors.append("openclaw: npm package name must match manifest id")
    if package.get("openclaw", {}).get("extensions") != ["./index.mjs"]:
        errors.append("openclaw: package extension entry is missing")
    index = (bundle / "index.mjs").read_text(encoding="utf-8")
    bridge = (bundle / "router-bridge.mjs").read_text(encoding="utf-8")
    for marker in ("definePluginEntry", '"before_prompt_build"', "buildRouteContext"):
        if marker not in index:
            errors.append(f"openclaw: index.mjs missing {marker}")
    if "error.message" in index or "String(error)" in index:
        errors.append("openclaw: adapter must not log raw subprocess errors or prompts")
    if "execFileAsync" not in bridge or "exec(" in bridge or "shell:" in bridge:
        errors.append("openclaw: bridge must use execFile without a shell")
    if "process.env" in bridge and "process.env.PATH" not in bridge:
        errors.append("openclaw: bridge must not forward ambient environment variables")


def _validate_codex(bundle: Path, version: str, errors: list[str]) -> None:
    manifest = _load_json(bundle / ".codex-plugin/plugin.json", errors)
    if manifest is None:
        return
    required = {"name", "version", "description", "author", "skills", "interface"}
    if not required.issubset(manifest):
        errors.append("codex: required manifest fields are missing")
    if manifest.get("name") != PACKAGE_NAME:
        errors.append("codex: incorrect plugin name")
    if manifest.get("version") != version or SEMVER.fullmatch(str(manifest.get("version"))) is None:
        errors.append("codex: version must match release strict semver")
    if manifest.get("skills") != "./skills/":
        errors.append("codex: skills path must be ./skills/")
    interface = manifest.get("interface")
    required_interface = {
        "displayName", "shortDescription", "longDescription", "developerName",
        "category", "capabilities", "defaultPrompt",
    }
    if not isinstance(interface, dict) or not required_interface.issubset(interface):
        errors.append("codex: interface metadata is incomplete")


def _validate_claude(
    bundle: Path,
    compatibility: dict[str, Any],
    version: str,
    errors: list[str],
    schema_path: Path | None = None,
) -> None:
    manifest = _load_json(bundle / ".claude-plugin/plugin.json", errors)
    if manifest is None:
        return
    allowed = {
        "$schema", "name", "version", "description", "author", "homepage",
        "repository", "license", "keywords", "dependencies", "hooks",
        "commands", "agents", "skills", "outputStyles", "lspServers",
    }
    unknown = sorted(set(manifest) - allowed)
    if unknown:
        errors.append(f"claude-code: unsupported manifest fields: {unknown}")
    if manifest.get("name") != PACKAGE_NAME or manifest.get("version") != version:
        errors.append("claude-code: name/version mismatch")
    if not isinstance(manifest.get("author"), dict) or not manifest["author"].get("name"):
        errors.append("claude-code: author.name is required")
    host = compatibility.get("hosts", {}).get("claude_code", {})
    if host.get("host_constraint") != ">=2.1.142 <3.0.0":
        errors.append("claude-code: host range is not constrained")
    if host.get("schema_sha256") != "3f69938d71a47a72fa60050b2050dd620054708911defc1c1dcd7188dcb169f5":
        errors.append("claude-code: schema lock mismatch")
    if schema_path is not None:
        if _sha256(schema_path) != host.get("schema_sha256"):
            errors.append("claude-code: supplied official schema does not match the lock")
            return
        try:
            import jsonschema
        except ImportError as exc:
            errors.append(f"claude-code: jsonschema dependency unavailable: {exc}")
            return
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.Draft7Validator.check_schema(schema)
            jsonschema.Draft7Validator(schema).validate(manifest)
        except (
            OSError,
            json.JSONDecodeError,
            jsonschema.SchemaError,
            jsonschema.ValidationError,
        ) as exc:
            errors.append(f"claude-code: official schema validation failed: {exc}")


def _validate_local_audit(bundle: Path, errors: list[str]) -> None:
    contract = _load_json(bundle / "integration.json", errors)
    if contract is None:
        return
    adapter = bundle / "planner_skill_adapter.py"
    if _sha256(adapter) != contract.get("adapter_sha256"):
        errors.append("local-audit-planner: adapter fingerprint mismatch")
    if contract.get("portable_upstream_openclaw") is not False:
        errors.append("local-audit-planner: custom adapter must not claim upstream portability")
    expected_targets = {
        "backend/openclaw/planner.py",
        "backend/openclaw/search_planner.py",
    }
    if set(contract.get("target_fingerprints", {})) != expected_targets:
        errors.append("local-audit-planner: target fingerprints are incomplete")


def _run_codex_validator(validator: Path, bundle: Path, errors: list[str]) -> None:
    result = subprocess.run(
        [sys.executable, str(validator), str(bundle)],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        errors.append(f"codex: official validator failed: {(result.stdout + result.stderr).strip()}")


def _smoke_router(skill: Path, label: str, errors: list[str]) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(skill / "scripts/route_task.py"),
            "--goal",
            "Read-only: inspect the repository planner architecture.",
        ],
        cwd=skill,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    if result.returncode != 0:
        errors.append(f"{label}: embedded router failed: {result.stderr.strip()}")
        return
    try:
        decision = json.loads(result.stdout)
    except json.JSONDecodeError:
        errors.append(f"{label}: embedded router returned invalid JSON")
        return
    if decision.get("schema_version") != "1.0" or decision.get("next_action") not in {
        "continue", "replan", "await_human", "refuse",
    }:
        errors.append(f"{label}: embedded router returned an invalid decision")


def _verify_hashes(root: Path, locked: dict[str, str], label: str, errors: list[str]) -> None:
    for relative, expected in locked.items():
        path = root / relative
        if not path.is_file():
            errors.append(f"{label}: missing locked file {relative}")
        elif _sha256(path) != expected:
            errors.append(f"{label}: hash mismatch for {relative}")


def _reject_symlinks(root: Path, label: str, errors: list[str]) -> None:
    symlinks = [path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_symlink()]
    if symlinks:
        errors.append(f"{label}: symlinks are not allowed: {symlinks}")
    generated = [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.name == "__pycache__" or path.suffix == ".pyc"
    ]
    if generated:
        errors.append(f"{label}: generated bytecode is not allowed: {generated}")


def _load_json(path: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"unable to read JSON {path}: {exc}")
        return None
    if not isinstance(payload, dict):
        errors.append(f"JSON root must be an object: {path}")
        return None
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
