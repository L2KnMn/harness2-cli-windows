# Copyright 2026 The Harness2 Authors
# Licensed under the Apache License, Version 2.0.
"""Process observation without sending console signals on Windows."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

IS_WINDOWS = os.name == "nt"
_SYNCHRONIZE = 0x100000
_WAIT_OBJECT_0 = 0
_WAIT_TIMEOUT = 258
_ERROR_ACCESS_DENIED = 5
_ERROR_INVALID_PARAMETER = 87


def _windows_api():
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    api.OpenProcess.restype = wintypes.HANDLE
    api.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    api.WaitForSingleObject.restype = wintypes.DWORD
    api.CloseHandle.argtypes = (wintypes.HANDLE,)
    api.CloseHandle.restype = wintypes.BOOL
    return api


def _last_error() -> int:
    return ctypes.get_last_error()


def _windows_is_running(pid: int) -> bool:
    api = _windows_api()
    handle = api.OpenProcess(_SYNCHRONIZE, False, pid)
    if not handle:
        code = _last_error()
        if code == _ERROR_INVALID_PARAMETER:
            return False
        if code == _ERROR_ACCESS_DENIED:
            # An inaccessible PID is not evidence that it died. Do not start a duplicate run.
            return True
        raise OSError(code, f"cannot query Windows process {pid} (error {code})")
    try:
        # A zero-duration wait cannot send a signal and also handles exit code 259 correctly.
        state = api.WaitForSingleObject(handle, 0)
        if state == _WAIT_TIMEOUT:
            return True
        if state == _WAIT_OBJECT_0:
            return False
        code = _last_error()
        raise OSError(code, f"cannot query Windows process {pid} (error {code})")
    finally:
        api.CloseHandle(handle)


def is_running(pid: int) -> bool:
    """Whether a PID may still be alive; access denial is conservatively treated as alive.

    This does not establish ownership or protect against PID reuse. It must not be used as
    authorization to signal a process. Native Windows stop/detach remain unsupported.
    """
    if type(pid) is not int or pid <= 0:
        return False
    if IS_WINDOWS:
        if pid > 0xFFFFFFFF:
            return False
        return _windows_is_running(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
