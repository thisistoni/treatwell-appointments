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


def find_symlink_component(path: Path) -> Path | None:
    for candidate in (path, *path.parents):
        if candidate.is_symlink():
            return candidate
    return None


def paths_overlap(first: Path, second: Path) -> bool:
    return first == second or first in second.parents or second in first.parents


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


def reject_source_symlink_components(path: Path, root: Path) -> None:
    if path != root and root not in path.parents:
        raise OSError(f"source runtime path escapes source root: {path}")
    current = path
    while True:
        if current.is_symlink():
            raise OSError(f"source runtime path contains a symlink: {current}")
        if current == root:
            break
        current = current.parent


def validate_runtime_source(source: Path) -> None:
    reject_source_symlink_components(source, source)
    if not source.is_dir():
        raise OSError(f"source runtime root is not a directory: {source}")
    for filename in RUNTIME_FILES:
        path = source / filename
        reject_source_symlink_components(path, source)
        if not path.is_file():
            raise OSError(f"source runtime file is not a regular file: {path}")
    for dirname in RUNTIME_DIRS:
        tree = source / dirname
        reject_source_symlink_components(tree, source)
        if not tree.is_dir():
            raise OSError(f"source runtime tree is not a directory: {tree}")
        for item in tree.rglob("*"):
            reject_source_symlink_components(item, source)
            if not item.is_dir() and not item.is_file():
                raise OSError(f"unsupported source runtime entry: {item}")
    for filename in RUNTIME_SCRIPTS:
        path = source / "scripts" / filename
        reject_source_symlink_components(path, source)
        if not path.is_file():
            raise OSError(f"source runtime file is not a regular file: {path}")


def copy_source_file(source: Path, destination: Path, root: Path) -> None:
    reject_source_symlink_components(source, root)
    if not source.is_file():
        raise OSError(f"source runtime file is not a regular file: {source}")
    prepare_file(destination)
    shutil.copy2(source, destination)


def copy_tree_contents(source: Path, destination: Path, root: Path) -> None:
    reject_source_symlink_components(source, root)
    if not source.is_dir():
        raise OSError(f"source runtime tree is not a directory: {source}")
    ensure_directory(destination)
    for item in sorted(source.rglob("*"), key=lambda candidate: len(candidate.parts)):
        reject_source_symlink_components(item, root)
        target = destination / item.relative_to(source)
        if item.is_dir():
            ensure_directory(target)
        elif item.is_file():
            prepare_file(target)
            shutil.copy2(item, target)


def copy_runtime(source: Path, destination: Path) -> None:
    ensure_directory(destination)
    for filename in RUNTIME_FILES:
        copy_source_file(source / filename, destination / filename, source)
    for dirname in RUNTIME_DIRS:
        copy_tree_contents(source / dirname, destination / dirname, source)
    scripts_destination = destination / "scripts"
    ensure_directory(scripts_destination)
    for filename in RUNTIME_SCRIPTS:
        copy_source_file(
            source / "scripts" / filename, scripts_destination / filename, source
        )
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
    raw_base = default_roots()[args.agent] if args.agent else args.target.expanduser()
    if ".." in raw_base.parts:
        print(f"Refusing target path containing '..': {raw_base}", file=sys.stderr)
        return 2
    base = Path(os.path.abspath(raw_base))
    symlink_component = find_symlink_component(base)
    if symlink_component is not None:
        print(
            f"Refusing destination base with symlink component: {symlink_component}",
            file=sys.stderr,
        )
        return 2
    destination = base / SKILL_NAME
    resolved_destination = destination.resolve(strict=False)
    if paths_overlap(source, resolved_destination):
        print(
            f"Refusing overlapping source and destination: {source} <-> {resolved_destination}",
            file=sys.stderr,
        )
        return 2

    try:
        validate_runtime_source(source)
    except OSError as exc:
        print(f"Install failed: {exc}", file=sys.stderr)
        return 2

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
