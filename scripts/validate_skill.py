#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ALLOWED_TOP_LEVEL_KEYS = {"allowed-tools", "description", "license", "metadata", "name"}
LINK_PATTERN = re.compile(r"\[[^\]]+\]\((?!https?://|mailto:|#)([^)]+)\)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate an AgentSkills-compatible skill repository.")
    parser.add_argument("root", type=Path, nargs="?", default=Path.cwd())
    args = parser.parse_args()
    errors = validate(args.root.resolve())
    print(json.dumps({"root": str(args.root.resolve()), "valid": not errors, "errors": errors}, indent=2))
    raise SystemExit(1 if errors else 0)


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    skill_path = root / "SKILL.md"
    if not skill_path.is_file():
        return ["missing SKILL.md"]
    text = skill_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if len(lines) > 500:
        errors.append(f"SKILL.md exceeds 500 lines: {len(lines)}")
    frontmatter = _frontmatter(lines, errors)
    name = frontmatter.get("name", "")
    description = frontmatter.get("description", "")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        errors.append("name must be a lowercase hyphen-separated slug")
    if root.name != name:
        errors.append(f"skill name {name!r} must match parent directory {root.name!r}")
    if not description or len(description) > 1024:
        errors.append("description must contain 1-1024 characters")
    unexpected = sorted(set(frontmatter) - ALLOWED_TOP_LEVEL_KEYS)
    if unexpected:
        errors.append(f"unexpected frontmatter keys: {unexpected}")
    if frontmatter.get("license") != "MIT":
        errors.append("license frontmatter must be MIT")
    metadata = frontmatter.get("metadata")
    if not isinstance(metadata, dict):
        errors.append("metadata must be a single-line JSON object for OpenClaw compatibility")
    else:
        bins = metadata.get("openclaw", {}).get("requires", {}).get("bins", [])
        if "python3" not in bins:
            errors.append("metadata.openclaw.requires.bins must include python3")
    for target in LINK_PATTERN.findall(text):
        clean_target = target.split("#", 1)[0]
        if clean_target and not (root / clean_target).is_file():
            errors.append(f"broken SKILL.md link: {target}")
    return errors


def _frontmatter(lines: list[str], errors: list[str]) -> dict[str, Any]:
    if not lines or lines[0].strip() != "---":
        errors.append("SKILL.md must start with YAML frontmatter")
        return {}
    try:
        end = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration:
        errors.append("SKILL.md frontmatter is not closed")
        return {}
    values: dict[str, Any] = {}
    for line in lines[1:end]:
        if not line or line[0].isspace() or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key == "metadata":
            if not value:
                errors.append("metadata must be on one line; multiline YAML is not supported by OpenClaw")
                values[key] = None
                continue
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as exc:
                errors.append(f"metadata must be valid single-line JSON: {exc.msg}")
                values[key] = None
                continue
            if not isinstance(parsed, dict):
                errors.append("metadata JSON must be an object")
                values[key] = None
                continue
            values[key] = parsed
        else:
            values[key] = value.strip('"\'')
    return values


if __name__ == "__main__":
    main()
