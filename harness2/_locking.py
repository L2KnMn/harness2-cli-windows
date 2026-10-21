# Copyright 2026 The Harness2 Authors
# Licensed under the Apache License, Version 2.0.
"""Bounded advisory locks shared by independent local processes."""

from __future__ import annotations

import errno
import math
import os
import time
from contextlib import contextmanager
from pathlib import Path

IS_WINDOWS = os.name == "nt"


@contextmanager
def file_lock(path: Path, *, timeout: float = 30.0, poll_interval: float = 0.05):
    """Exclusively lock a persistent sidecar without truncating it.

    All cooperating writers must use this sidecar, and it must not be removed while a
    writer could still hold it. The same first byte is locked on every Windows attempt.
    """
    if not math.isfinite(timeout) or timeout < 0:
        raise ValueError("lock timeout must be a finite non-negative number")
    if not math.isfinite(poll_interval) or poll_interval <= 0:
        raise ValueError("lock poll interval must be a finite positive number")
    if IS_WINDOWS:
        import msvcrt
    else:
        import fcntl

    with open(path, "a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        deadline = time.monotonic() + timeout
        while True:
            stream.seek(0)
            try:
                if IS_WINDOWS:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                    raise
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"timed out waiting for file lock: {path}") from exc
                time.sleep(min(poll_interval, remaining))
        try:
            yield
        finally:
            stream.seek(0)
            if IS_WINDOWS:
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
