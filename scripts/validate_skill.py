#!/usr/bin/env python3
"""Dependency-free structural validator for an Agent Skills repository."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def parse_frontmatter(text: str) -> tuple[dict[str, str], list[str]]:
    errors: list[str] = []
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return {}, ["SKILL.md must start with YAML frontmatter delimiter ---"]
    try:
        end = lines.index("---", 1)
    except ValueError:
        return {}, ["SKILL.md frontmatter has no closing --- delimiter"]

    data: dict[str, str] = {}
    in_metadata = False
    for number, line in enumerate(lines[1:end], start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line == "metadata:":
            in_metadata = True
            continue
        if line.startswith("  ") and in_metadata:
            match = re.fullmatch(r"  ([a-zA-Z0-9_-]+):\s*(.+)", line)
            if not match:
                errors.append(f"unsupported metadata syntax on line {number}")
            continue
        in_metadata = False
        match = re.fullmatch(r"([a-zA-Z0-9_-]+):\s*(.*)", line)
        if not match:
            errors.append(f"unsupported frontmatter syntax on line {number}")
            continue
        key, value = match.groups()
        raw_value = value.strip()
        if ": " in raw_value and not raw_value.startswith(('"', "'")):
            errors.append(
                f"plain YAML scalar on line {number} contains ': '; quote the value"
            )
        data[key] = raw_value.strip('"').strip("'")
    return data, errors


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    skill_file = root / "SKILL.md"
    if not skill_file.is_file():
        return [f"missing {skill_file}"]
    text = skill_file.read_text(encoding="utf-8")
    frontmatter, parse_errors = parse_frontmatter(text)
    errors.extend(parse_errors)

    name = frontmatter.get("name", "")
    description = frontmatter.get("description", "")
    if not NAME_RE.fullmatch(name):
        errors.append("name must be lowercase alphanumeric with single hyphen separators")
    if root.name != name:
        errors.append(f"skill directory name {root.name!r} must equal frontmatter name {name!r}")
    if not 1 <= len(name) <= 64:
        errors.append("name must contain 1-64 characters")
    if not 1 <= len(description) <= 1024:
        errors.append("description must contain 1-1024 characters")
    if len(text.splitlines()) > 500:
        errors.append("SKILL.md must not exceed 500 lines")

    allowed = {"name", "description", "license", "compatibility", "metadata"}
    unknown = sorted(set(frontmatter) - allowed)
    if unknown:
        errors.append(f"non-portable frontmatter fields: {', '.join(unknown)}")

    for match in LINK_RE.finditer(text):
        target = match.group(1).split("#", 1)[0]
        if not target or "://" in target or target.startswith("mailto:"):
            continue
        if not (root / target).exists():
            errors.append(f"broken SKILL.md link: {target}")

    for required in (
        "references/browser-workflow.md",
        "references/idempotency.md",
        "references/tool-contract.md",
        "references/treatwell-evidence.md",
        "references/whatsapp-conversation.md",
        "scripts/booking_ledger.py",
        "LICENSE",
    ):
        if not (root / required).is_file():
            errors.append(f"missing runtime file: {required}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"VALID: {root / 'SKILL.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
