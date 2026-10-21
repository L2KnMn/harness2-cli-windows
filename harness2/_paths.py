"""Portable managed paths, validated before filesystem operations."""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path, PureWindowsPath

_DEVICES = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"} | {
    f"{prefix}{number}"
    for prefix in ("COM", "LPT")
    for number in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "¹", "²", "³")
}


def normalize_rel(rel: str) -> str:
    """Canonical '/' key for a portable relative file; never trim an ambiguous name."""
    raw = str(rel).replace("\\", "/")
    if raw.startswith("/") or PureWindowsPath(raw).drive:
        raise ValueError(f"path escapes the harness: {rel!r}")
    parts = []
    for part in raw.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            raise ValueError(f"path escapes the harness: {rel!r}")
        if part.endswith((" ", ".")) or any(ord(char) < 32 or char in '<>:"|?*' for char in part):
            raise ValueError(f"path is not a portable file name: {rel!r}")
        if part.split(".", 1)[0].rstrip(" ").upper() in _DEVICES:
            raise ValueError(f"path uses a reserved Windows name: {rel!r}")
        parts.append(part)
    return "/".join(parts)


def validate_relative_paths(paths: Iterable[str]) -> list[str]:
    """Reject aliases and file/directory conflicts before a group of writes starts."""
    result = []
    aliases = {}
    files = set()
    for original in paths:
        rel = normalize_rel(original)
        if not rel:
            raise ValueError("managed file path must not be empty")
        if rel in files:
            raise ValueError(f"duplicate managed path: {original!r}")
        files.add(rel)
        result.append(rel)
        parts = rel.split("/")
        for count in range(1, len(parts) + 1):
            prefix = "/".join(parts[:count])
            previous = aliases.setdefault(prefix.casefold(), prefix)
            if previous != prefix:
                raise ValueError(f"case-colliding managed paths: {previous!r}, {prefix!r}")
    for rel in files:
        parts = rel.split("/")
        if any("/".join(parts[:count]) in files for count in range(1, len(parts))):
            raise ValueError(f"managed file is also a directory: {rel!r}")
    return result


def _linked(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


def checked_root(root: Path) -> Path:
    """Keep the caller's declared root, refusing a root that is itself redirected."""
    root = Path(root).absolute()
    if _linked(root):
        raise ValueError(f"managed root is a symlink or junction: {root}")
    return root


def checked_path(root: Path, rel: str) -> Path:
    """Reject redirected components and escapes before reading, writing or deleting."""
    rel = normalize_rel(rel)
    if not rel:
        raise ValueError("managed file path must not be empty")
    root = checked_root(root)
    path = root
    parts = rel.split("/")
    for index, part in enumerate(parts):
        if path.is_dir():
            for sibling in path.iterdir():
                if sibling.name != part and sibling.name.casefold() == part.casefold():
                    raise ValueError(
                        f"managed path aliases an existing name: {part!r}, {sibling.name!r}"
                    )
        path = path / part
        if _linked(path):
            raise ValueError(f"managed path is a symlink or junction: {rel}")
        if index < len(parts) - 1 and path.exists() and not path.is_dir():
            raise ValueError(f"managed path parent is not a directory: {rel}")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"managed path escapes its root: {rel}")
    return path


def iter_files(root: Path) -> list[Path]:
    """Walk without following a symlink or Windows junction, in portable key order."""
    root = checked_root(root)
    result = []
    if not root.is_dir():
        return result
    for directory, dirs, files in os.walk(root, followlinks=False):
        parent = Path(directory)
        for name in [*dirs, *files]:
            candidate = parent / name
            if _linked(candidate):
                raise ValueError(f"managed path is a symlink or junction: {candidate}")
        result.extend(parent / name for name in files)
    return sorted(result, key=lambda path: path.relative_to(root).as_posix())
