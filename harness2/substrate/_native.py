# Copyright 2026 The Harness2 Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Shared CLI resolution and bounded native-file operations for executors."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .._argv import CliBinary, cli_argv
from .._paths import checked_path as safe_path
from .._paths import checked_root, iter_files, validate_relative_paths
from ..core import tree as HT
from ..settings import ConfigError


def check_cli(binary: CliBinary, default: str) -> None:
    argv = cli_argv(binary, default)
    try:
        subprocess.run([*argv, "--version"], check=True, capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ConfigError(f"executor version check failed: {binary or default}") from exc


def checked_path(root: Path, rel: str) -> Path:
    try:
        return safe_path(root, rel)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc


def surface_files(surface: HT.SurfaceSpec, tree: HT.Tree) -> HT.Tree:
    validate_relative_paths(tree)
    stubs = {rel for rel, _ in surface.stubs}
    out = {}
    for rel, content in tree.items():
        rel = HT.normalize_rel(rel)
        if rel in stubs:
            continue
        if not HT.is_allowed(surface, rel):
            raise ValueError(f"file is outside the {surface.name} surface: {rel}")
        out[rel] = content
    return out


def native_tree(
    surface: HT.SurfaceSpec,
    root: Path,
    entries: tuple[str, ...],
    rejected: list[str] | None = None,
) -> HT.Tree:
    root = checked_root(root)
    out = {}
    stubs = {rel for rel, _ in surface.stubs}
    for entry in entries:
        path = root if entry == "." else checked_path(root, entry)
        candidates = iter_files(path) if path.is_dir() else [path]
        for candidate in candidates:
            if not candidate.is_file() or "__pycache__" in candidate.parts:
                continue
            rel = candidate.relative_to(root).as_posix()
            if rel in stubs:
                continue
            if HT.is_allowed(surface, rel):
                out[rel] = checked_path(root, rel).read_text(encoding="utf-8", errors="replace")
            elif rejected is not None:
                rejected.append(rel)
    validate_relative_paths(out)
    return out


def export_files(root: Path, files: HT.Tree, base: HT.Tree) -> dict[str, list[str]]:
    validate_relative_paths(files)
    validate_relative_paths(base)
    validate_relative_paths(files.keys() | base.keys())
    files = {HT.normalize_rel(rel): body for rel, body in files.items()}
    base = {HT.normalize_rel(rel): body for rel, body in base.items()}
    paths = {rel: checked_path(root, rel) for rel in files.keys() | base.keys()}
    for rel, path in paths.items():
        if path.is_dir():
            raise ConfigError(f"managed file path is an existing directory: {rel}")
    written = []
    deleted = []
    for rel, content in sorted(files.items()):
        path = paths[rel]
        if path.is_file() and path.read_text(encoding="utf-8", errors="replace") == content:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(rel)
    for rel in sorted(base.keys() - files.keys()):
        path = paths[rel]
        if path.is_file():
            path.unlink()
            deleted.append(rel)
    return {"written": written, "deleted": deleted}
