#!/usr/bin/env python3
"""Install this Agent Skill into a supported or custom skill directory."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

SKILL_NAME = "treatwell-appointments"
INSTALL_MARKER = ".treatwell-appointments-install"
INSTALL_MARKER_CONTENT = "treatwell-appointments\ninstaller-schema=1\n"
RUNTIME_FILES = ("SKILL.md", "LICENSE")
RUNTIME_DIRS = ("references",)
RUNTIME_SCRIPTS = ("booking_ledger.py",)


def default_roots() -> dict[str, Path]:
    home = Path.home()
    hermes_home = Path(os.environ.get("HERMES_HOME", home / ".hermes")).expanduser()
    return {
        "hermes": hermes_home / "skills",
        "codex": home / ".agents" / "skills",
        "claude": home / ".claude" / "skills",
        "opencode": home / ".config" / "opencode" / "skills",
    }


def ensure_directory(path: Path) -> None:
    if path.is_symlink():
        path.unlink()
    elif path.exists() and not path.is_dir():
        raise OSError(f"managed directory path is not a directory: {path}")
    path.mkdir(parents=True, exist_ok=True)


def prepare_file(path: Path) -> None:
    ensure_directory(path.parent)
    if path.is_symlink():
        path.unlink()
    elif path.exists() and not path.is_file():
        raise OSError(f"managed file path is not a regular file: {path}")


def copy_tree_contents(source: Path, destination: Path) -> None:
    ensure_directory(destination)
    for item in sorted(source.rglob("*"), key=lambda candidate: len(candidate.parts)):
        if item.is_symlink():
            raise OSError(f"source runtime tree contains a symlink: {item}")
        target = destination / item.relative_to(source)
        if item.is_dir():
            ensure_directory(target)
        elif item.is_file():
            prepare_file(target)
            shutil.copy2(item, target)


def copy_runtime(source: Path, destination: Path) -> None:
    ensure_directory(destination)
    for filename in RUNTIME_FILES:
        target = destination / filename
        prepare_file(target)
        shutil.copy2(source / filename, target)
    for dirname in RUNTIME_DIRS:
        copy_tree_contents(source / dirname, destination / dirname)
    scripts_destination = destination / "scripts"
    ensure_directory(scripts_destination)
    for filename in RUNTIME_SCRIPTS:
        target = scripts_destination / filename
        prepare_file(target)
        shutil.copy2(source / "scripts" / filename, target)
    marker = destination / INSTALL_MARKER
    prepare_file(marker)
    temporary_marker = destination / f"{INSTALL_MARKER}.tmp"
    prepare_file(temporary_marker)
    temporary_marker.write_text(INSTALL_MARKER_CONTENT, encoding="utf-8")
    os.replace(temporary_marker, marker)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--agent", choices=tuple(default_roots()))
    group.add_argument(
        "--target",
        type=Path,
        help="custom base skills directory; the skill-name directory is created below it",
    )
    parser.add_argument("--force", action="store_true", help="replace an existing installation")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source = Path(__file__).resolve().parent.parent
    base = default_roots()[args.agent] if args.agent else args.target.expanduser()
    destination = base / SKILL_NAME

    if destination.exists() or destination.is_symlink():
        if not args.force:
            print(f"Refusing to overwrite existing installation: {destination}", file=sys.stderr)
            return 2
        if destination.is_symlink():
            destination.unlink()
        elif destination.is_dir():
            marker = destination / INSTALL_MARKER
            marker_text = (
                marker.read_text(encoding="utf-8")
                if marker.is_file() and not marker.is_symlink()
                else ""
            )
            if marker_text != INSTALL_MARKER_CONTENT:
                print(
                    f"Refusing to update an unrecognized directory: {destination}",
                    file=sys.stderr,
                )
                return 2
        else:
            print(f"Refusing to remove a non-directory target: {destination}", file=sys.stderr)
            return 2

    try:
        base.mkdir(parents=True, exist_ok=True)
        copy_runtime(source, destination)
    except (OSError, shutil.Error) as exc:
        print(f"Installation failed: {exc}", file=sys.stderr)
        return 2

    print(f"Installed {SKILL_NAME} to {destination}")
    print("Start a fresh agent session so the new skill is discovered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
