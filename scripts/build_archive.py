#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

from scan_secrets import scan_paths


PACKAGE_NAME = "task-compass"
DEFAULT_VERSION = "0.3.0"
EXCLUDED_PARTS = {".git", "__pycache__", ".pytest_cache", ".ruff_cache", "dist"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a reproducible Skill release archive.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    parser.add_argument("--version", default=DEFAULT_VERSION)
    args = parser.parse_args()
    root = args.root.resolve()
    output_dir = args.output_dir if args.output_dir.is_absolute() else root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"{PACKAGE_NAME}-v{args.version}.tar.gz"

    files = _release_files(root)
    findings = scan_paths(root, files, source="release-archive")
    if findings:
        summary = [f"{finding.kind}:{finding.path}" for finding in findings]
        raise ValueError(f"release archive secret scan failed: {summary}")
    directories = _release_directories(root, files)
    with archive.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as handle:
                handle.addfile(_archive_info(PACKAGE_NAME, mode=0o755, directory=True))
                for path in directories:
                    relative = path.relative_to(root)
                    handle.addfile(
                        _archive_info(
                            f"{PACKAGE_NAME}/{relative.as_posix()}",
                            mode=0o755,
                            directory=True,
                        )
                    )
                for path in files:
                    relative = path.relative_to(root)
                    data = path.read_bytes()
                    info = _archive_info(
                        f"{PACKAGE_NAME}/{relative.as_posix()}",
                        mode=0o755 if relative.parts[0] == "scripts" and path.suffix == ".py" else 0o644,
                    )
                    info.size = len(data)
                    handle.addfile(info, io.BytesIO(data))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum = output_dir / "SHA256SUMS"
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    print(json.dumps({"archive": str(archive), "sha256": digest, "files": len(files)}, indent=2))


def _archive_info(name: str, *, mode: int, directory: bool = False) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name.rstrip("/") + ("/" if directory else ""))
    info.mode = mode
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    if directory:
        info.type = tarfile.DIRTYPE
    return info


def _release_files(root: Path) -> list[Path]:
    if (root / ".git").exists():
        result = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            check=True,
            capture_output=True,
        )
        relatives = [
            Path(raw.decode("utf-8", errors="surrogateescape"))
            for raw in result.stdout.split(b"\0")
            if raw
        ]
    else:
        relatives = [path.relative_to(root) for path in root.rglob("*") if path.is_file()]
    files: list[Path] = []
    for relative in sorted(relatives):
        path = root / relative
        if set(relative.parts).intersection(EXCLUDED_PARTS) or path.name in {
            "SHA256SUMS",
            "INTEGRATION_SHA256SUMS",
        }:
            continue
        if path.is_symlink():
            raise ValueError(f"release archive cannot contain symlink: {relative}")
        if path.is_file():
            files.append(path)
    return files


def _release_directories(root: Path, files: list[Path]) -> list[Path]:
    relatives: set[Path] = set()
    for path in files:
        parent = path.relative_to(root).parent
        while parent != Path("."):
            relatives.add(parent)
            parent = parent.parent
    return [root / relative for relative in sorted(relatives)]


if __name__ == "__main__":
    main()
