"""Resolve CLI argv without passing command text to a Windows shell."""

from __future__ import annotations

import os
import shlex
import shutil
from collections.abc import Sequence

from .settings import ConfigError

CliBinary = str | Sequence[str]
_WINDOWS = os.name == "nt"


def binary_args(binary: CliBinary, default: str) -> list[str]:
    """Arrays are portable; legacy shell-like strings are supported on POSIX only.

    A Windows string denotes exactly one executable, including a path with spaces.
    Arguments belong in a TOML array, e.g. ["python.exe", "fixture.py"].
    """
    if isinstance(binary, str):
        value = binary.strip() or default
        if _WINDOWS:
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            argv = [value]
        elif shutil.which(value) is not None:
            argv = [value]
        else:
            try:
                argv = shlex.split(value)
            except ValueError as exc:
                raise ConfigError(f"invalid executor binary: {exc}") from exc
    elif isinstance(binary, Sequence) and not isinstance(binary, (bytes, bytearray)):
        argv = list(binary)
    else:
        raise ConfigError("executor binary must be a path string or an argv array of strings")
    if not argv or any(not isinstance(arg, str) or "\0" in arg for arg in argv) or not argv[0]:
        raise ConfigError("executor argv must have a non-empty executable and string arguments")
    return argv


def cli_argv(binary: CliBinary, default: str) -> list[str]:
    argv = binary_args(binary, default)
    resolved = shutil.which(argv[0])
    if resolved is None:
        raise ConfigError(
            f"executor binary not found: {argv[0]}; use an argv array for executable arguments"
        )
    if _WINDOWS and os.path.splitext(resolved)[1].lower() not in (".exe", ".com"):
        raise ConfigError(
            f"Windows executor must be a native .exe or .com: {resolved}; "
            "shell shims (.cmd, .bat, .ps1) are unsupported. Configure the native executable "
            "or an explicit interpreter argv array."
        )
    return [os.path.abspath(resolved), *argv[1:]]
