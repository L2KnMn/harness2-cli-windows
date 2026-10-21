"""Offline process observation and real cross-process lock contracts."""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from harness2 import _process
from harness2._locking import file_lock
from harness2.cli import _common, run, stop
from harness2.settings import ConfigError

ROOT = Path(__file__).resolve().parents[1]


class ProcessTests(unittest.TestCase):
    def api(self, *, handle=0x100000001, state=258):
        return SimpleNamespace(
            OpenProcess=Mock(return_value=handle),
            WaitForSingleObject=Mock(return_value=state),
            CloseHandle=Mock(return_value=True),
        )

    def test_windows_query_never_signals_and_closes_full_handle(self):
        for state, expected in ((258, True), (0, False)):
            api = self.api(state=state)
            with (
                self.subTest(state=state),
                patch.object(_process, "IS_WINDOWS", True),
                patch.object(_process, "_windows_api", return_value=api),
                patch.object(os, "kill", side_effect=AssertionError("a query must not signal")),
            ):
                self.assertEqual(_process.is_running(42), expected)
            api.OpenProcess.assert_called_once_with(0x100000, False, 42)
            api.WaitForSingleObject.assert_called_once_with(0x100000001, 0)
            api.CloseHandle.assert_called_once_with(0x100000001)

    def test_windows_absent_and_inaccessible_processes(self):
        for error, expected in ((87, False), (5, True)):
            api = self.api(handle=None)
            with (
                self.subTest(error=error),
                patch.object(_process, "_windows_api", return_value=api),
                patch.object(_process, "_last_error", return_value=error),
            ):
                self.assertEqual(_process._windows_is_running(42), expected)
            api.CloseHandle.assert_not_called()

    def test_windows_query_failure_closes_handle(self):
        api = self.api(state=0xFFFFFFFF)
        with (
            patch.object(_process, "_windows_api", return_value=api),
            patch.object(_process, "_last_error", return_value=123),
            self.assertRaisesRegex(OSError, "error 123"),
        ):
            _process._windows_is_running(42)
        api.CloseHandle.assert_called_once_with(0x100000001)

    def test_windows_unexpected_open_error_is_not_reported_as_dead(self):
        with (
            patch.object(_process, "_windows_api", return_value=self.api(handle=None)),
            patch.object(_process, "_last_error", return_value=123),
            self.assertRaises(OSError),
        ):
            _process._windows_is_running(42)

    def test_invalid_pids_never_reach_windows_api(self):
        with (
            patch.object(_process, "IS_WINDOWS", True),
            patch.object(_process, "_windows_api") as api,
        ):
            for pid in (0, -1, True, None, "42", 0x100000000):
                with self.subTest(pid=pid):
                    self.assertFalse(_process.is_running(pid))
            api.assert_not_called()

    def test_posix_liveness_contract(self):
        with patch.object(_process, "IS_WINDOWS", False), patch.object(os, "kill") as kill:
            self.assertTrue(_process.is_running(42))
            kill.assert_called_once_with(42, 0)
            kill.side_effect = ProcessLookupError
            self.assertFalse(_process.is_running(42))
            kill.side_effect = PermissionError
            self.assertTrue(_process.is_running(42))

    @unittest.skipUnless(os.name == "nt", "native Windows handle query")
    def test_native_handle_signatures(self):
        api = _process._windows_api()
        self.assertEqual(ctypes.sizeof(api.OpenProcess.restype), ctypes.sizeof(ctypes.c_void_p))
        self.assertEqual(api.WaitForSingleObject.argtypes[0], api.OpenProcess.restype)
        self.assertEqual(api.CloseHandle.argtypes[0], api.OpenProcess.restype)

    @unittest.skipUnless(os.name == "nt", "native Windows signal-free child observation")
    def test_real_child_is_observed_without_signals(self):
        child = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import sys; print('ready',flush=True); sys.stdin.buffer.read()",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            self.assertEqual(child.stdout.readline().strip(), b"ready")
            with patch.object(os, "kill", side_effect=AssertionError("must not send a signal")):
                self.assertTrue(_process.is_running(child.pid))
        finally:
            child.communicate(timeout=10)
        self.assertEqual(child.returncode, 0)
        self.assertFalse(_process.is_running(child.pid))

    def test_run_record_uses_observation_and_removes_stale_record(self):
        with tempfile.TemporaryDirectory(prefix="harness2 한글 공백 ", dir=ROOT) as temporary:
            root = Path(temporary)
            record = {"pid": 42, "started": "now", "argv": ["run"]}
            path = root / "run.pid"
            path.write_text(json.dumps(record), encoding="utf-8")
            with patch.object(_process, "is_running", return_value=True) as probe:
                self.assertEqual(_common.run_process(root), record)
                probe.assert_called_once_with(42)
            with patch.object(_process, "is_running", return_value=False):
                self.assertIsNone(_common.run_process(root))
            self.assertFalse(path.exists())

    def test_native_windows_stop_is_explicitly_blocked_without_signals(self):
        ctx = SimpleNamespace(out=Mock())
        with (
            patch.object(stop, "IS_WINDOWS", True),
            patch.object(_common, "resolve_run", return_value=Path("run")),
            patch.object(_common, "run_process", return_value={"pid": 42}),
            patch.object(os, "kill", side_effect=AssertionError("must not send a signal")),
            self.assertRaisesRegex(ConfigError, "stop is not supported on native Windows"),
        ):
            stop.run(SimpleNamespace(name="run"), ctx)
        ctx.out.assert_not_called()

    def test_native_windows_detach_is_blocked_before_writing_or_launching(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            root = Path(temporary) / "not-created"
            with (
                patch.object(_process, "IS_WINDOWS", True),
                patch.object(run.subprocess, "Popen") as popen,
                self.assertRaisesRegex(ConfigError, "--detach is not supported"),
            ):
                run._detach(SimpleNamespace(), SimpleNamespace(), "run", root)
            self.assertFalse(root.exists())
            popen.assert_not_called()


class LockTests(unittest.TestCase):
    def test_lock_is_nontruncating_and_unlocks_after_error(self):
        with tempfile.TemporaryDirectory(prefix="harness2 한글 공백 ", dir=ROOT) as temporary:
            path = Path(temporary) / "summary.lock"
            path.write_bytes(b"sentinel")
            with self.assertRaisesRegex(RuntimeError, "inside"):
                with file_lock(path):
                    raise RuntimeError("inside")
            with file_lock(path, timeout=0):
                pass
            self.assertEqual(path.read_bytes(), b"sentinel")

    def test_lock_parameters_are_bounded(self):
        for kwargs in ({"timeout": -1}, {"timeout": float("inf")}, {"poll_interval": 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                with file_lock(Path("unused.lock"), **kwargs):
                    pass

    def child(self, script, *args):
        return subprocess.Popen(
            [sys.executable, "-X", "utf8", "-B", "-c", script, str(ROOT), *map(str, args)],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_lock_contends_across_real_processes_and_times_out(self):
        script = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from harness2._locking import file_lock
with file_lock(Path(sys.argv[2])):
    print('locked', flush=True)
    sys.stdin.buffer.read()
"""
        with tempfile.TemporaryDirectory(prefix="harness2 한글 공백 ", dir=ROOT) as temporary:
            path = Path(temporary) / "summary.lock"
            child = self.child(script, path)
            try:
                self.assertEqual(child.stdout.readline().strip(), b"locked")
                with self.assertRaises(TimeoutError):
                    with file_lock(path, timeout=0.1, poll_interval=0.01):
                        self.fail("another process holds the lock")
            finally:
                out, err = child.communicate(timeout=10)
            self.assertEqual(child.returncode, 0, (out, err))
            with file_lock(path, timeout=0):
                pass

    def test_summary_merges_from_concurrent_processes(self):
        script = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from harness2.core.schedule import TaskResult, _write_summary
path, worker = Path(sys.argv[2]), sys.argv[3]
for i in range(12):
    mode = worker + '-' + str(i)
    row = TaskResult('task', 'area', 1, status='ok', modes={mode: {'ok': True}},
                     selections={mode: {'ok': True, 'chosen_label': 'final'}})
    _write_summary(path, row)
"""
        with tempfile.TemporaryDirectory(prefix="harness2 한글 공백 ", dir=ROOT) as temporary:
            path = Path(temporary) / "summary.json"
            children = [self.child(script, path, str(i)) for i in range(4)]
            outputs = [child.communicate(timeout=30) for child in children]
            for child, (out, err) in zip(children, outputs):
                self.assertEqual(child.returncode, 0, (out, err))
            row = json.loads(path.read_text(encoding="utf-8"))
            expected = {f"{worker}-{i}" for worker in range(4) for i in range(12)}
            self.assertEqual(set(row["modes"]), expected)
            self.assertEqual(set(row["selections"]), expected)
            self.assertEqual(row["status"], "ok")


if __name__ == "__main__":
    unittest.main()
