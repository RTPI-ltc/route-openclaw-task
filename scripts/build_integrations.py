#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import shutil
import tarfile
from pathlib import Path
from typing import Iterable

from scan_secrets import scan_paths


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VERSION = "0.3.0"
PACKAGE_NAME = "task-compass"
CANONICAL_SKILL_NAME = "task-compass"
LEGACY_SKILL_NAME = "route-openclaw-task"
SKILL_PAYLOAD_FILES = (
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "scripts/route_task.py",
    "scripts/validate_route.py",
    "scripts/evaluate_router.py",
    "assets/profile-policy-model.json",
    "assets/tool-family-model.json",
    "assets/evaluation-metrics.json",
    "references/routing-contract.md",
    "references/model-card.md",
)
BUNDLES = ("openclaw-native", "codex", "claude-code", "local-audit-planner")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build host integration bundles.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, default=Path("dist/integrations"))
    parser.add_argument("--version", default=DEFAULT_VERSION)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output_dir if args.output_dir.is_absolute() else root / args.output_dir
    result = build_integrations(root, output, args.version)
    print(json.dumps(result, indent=2, sort_keys=True))


def build_integrations(root: Path, output: Path, version: str = DEFAULT_VERSION) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    compatibility = json.loads((root / "integrations/compatibility.json").read_text(encoding="utf-8"))
    if compatibility["release_version"] != version:
        raise ValueError("integration compatibility release_version does not match requested version")
    built: dict[str, dict[str, object]] = {}
    checksums: list[str] = []
    for bundle_name in BUNDLES:
        template = root / "integrations" / bundle_name
        destination = output / f"{PACKAGE_NAME}-{bundle_name}-v{version}"
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(
            template,
            destination,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".ruff_cache"),
        )
        shutil.copy2(root / "LICENSE", destination / "LICENSE")
        shutil.copy2(root / "integrations/compatibility.json", destination / "compatibility.json")
        if bundle_name != "local-audit-planner":
            canonical_root = destination / "skills" / CANONICAL_SKILL_NAME
            legacy_root = destination / "skills" / LEGACY_SKILL_NAME
            _copy_skill(root, canonical_root, root / "SKILL.md")
            _copy_skill(root, legacy_root, root / "integrations/legacy-skill/SKILL.template")
        bundle_files = sorted(path for path in destination.rglob("*") if path.is_file())
        findings = scan_paths(destination, bundle_files, source=f"integration:{bundle_name}")
        if findings:
            summary = [f"{finding.kind}:{finding.path}" for finding in findings]
            raise ValueError(f"integration secret scan failed: {summary}")
        archive = output / f"{PACKAGE_NAME}-{bundle_name}-v{version}.tar.gz"
        _write_reproducible_archive(destination, archive)
        digest = _sha256(archive)
        checksums.append(f"{digest}  {archive.name}")
        built[bundle_name] = {
            "directory": str(destination),
            "archive": str(archive),
            "sha256": digest,
            "files": sum(1 for path in destination.rglob("*") if path.is_file()),
        }
    (output / "INTEGRATION_SHA256SUMS").write_text(
        "\n".join(checksums) + "\n",
        encoding="utf-8",
    )
    return {"version": version, "bundles": built}


def _copy_skill(root: Path, destination: Path, manifest: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(manifest, destination / "SKILL.md")
    for relative in SKILL_PAYLOAD_FILES:
        source = root / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _write_reproducible_archive(source: Path, archive: Path) -> None:
    with archive.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as handle:
                members = [source, *sorted(source.rglob("*"))]
                for path in members:
                    relative = path.relative_to(source.parent)
                    info = _archive_info(relative.as_posix(), directory=path.is_dir())
                    if path.is_file():
                        data = path.read_bytes()
                        info.size = len(data)
                        handle.addfile(info, io.BytesIO(data))
                    else:
                        handle.addfile(info)


def _archive_info(name: str, *, directory: bool) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name.rstrip("/") + ("/" if directory else ""))
    info.mode = 0o755 if directory or name.endswith((".py", ".mjs")) else 0o644
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    if directory:
        info.type = tarfile.DIRTYPE
    return info


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
