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

"""Portable CLI smoke checks that cannot start an installed model CLI."""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from harness2.cli import main
from harness2.core import events
from harness2.demo import DemoAdapter
from harness2.substrate._native import cli_argv
from harness2.substrate.codex import CodexSubstrate

FAKE_CLI = """import json
import os
import sys

prompt = sys.stdin.buffer.read().decode('utf-8')
result = {'argv': sys.argv[1:], 'cwd': os.getcwd(), 'prompt': prompt}
sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode('utf-8'))
"""


class WindowsSmokeTests(unittest.TestCase):
    def setUp(self):
        # The explicit writable parent also works in managed Windows sandboxes
        # whose default temporary directory is outside the writable workspace.
        temporary = tempfile.TemporaryDirectory(prefix="harness2 한글 ", dir=Path.cwd())
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.project = self.root / "작업 공간"
        (self.project / ".harness2").mkdir(parents=True)
        isolated = patch.dict(
            os.environ, {"XDG_CONFIG_HOME": str(self.root / "격리 설정")}
        )
        isolated.start()
        self.addCleanup(isolated.stop)
        self.addCleanup(events.start, None)

    def invoke_without_processes(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with (
            patch.object(main, "version", return_value="0.1.0-test"),
            patch("subprocess.run", side_effect=AssertionError("unexpected subprocess")),
            patch("subprocess.Popen", side_effect=AssertionError("unexpected subprocess")),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            code = main.main(["-C", str(self.project), *argv])
        return code, out.getvalue(), err.getvalue()

    def test_public_help_never_launches_a_process(self):
        with self.assertRaises(SystemExit) as raised:
            self.invoke_without_processes("--help")
        self.assertEqual(raised.exception.code, 0)

    def test_public_json_status_reads_korean_paths_without_model_calls(self):
        run_dir = self.project / ".harness2/runs/codex-k1"
        run_dir.mkdir(parents=True)
        record = {
            "name": "codex-k1",
            "created": "2026-10-21T00:00:00+00:00",
            "settings": {},
            "suite": "tasks",
            "executor": "codex",
            "stream": [["문서", "검증 작업"]],
            "schedule": {"k": 1, "modes": "parallel"},
        }
        (run_dir / "run.json").write_text(json.dumps(record), encoding="utf-8")
        event = {"kind": "task_done", "task": "검증 작업", "status": "ok"}
        (run_dir / "events.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")
        code, out, err = self.invoke_without_processes("--json", "status", "codex-k1")
        self.assertEqual((code, err), (0, ""))
        result = json.loads(out)
        self.assertEqual(result["executor"], "codex")
        self.assertEqual(result["tasks"][0]["task"], "검증 작업")
        self.assertEqual(result["tasks"][0]["state"], "done")
        self.assertFalse(result["active"])

    def test_public_dry_run_uses_only_an_offline_adapter(self):
        def adapter(context):
            result = DemoAdapter(context.run_root / "fixture")
            result.spec = replace(result.spec, runs_root=context.run_root)
            return result

        suite = Mock(make_adapter=Mock(side_effect=adapter), check=Mock(return_value=[]))
        with patch("harness2.registry.load", return_value=suite):
            code, out, err = self.invoke_without_processes(
                "--json", "run", "--name", "offline", "--dry-run", "--only-tasks", "ledger-1"
            )
        self.assertEqual((code, err), (0, ""))
        result = json.loads(out)
        self.assertEqual(result["stream"], [["accounting", "ledger-1"]])
        self.assertEqual(result["estimate"]["calls"], 9)
        self.assertFalse((self.project / ".harness2/runs/offline/run.pid").exists())

    def test_explicit_python_fixture_preserves_utf8_stdin_and_arguments(self):
        script = self.root / "가짜 CLI.py"
        script.write_text(FAKE_CLI, encoding="utf-8")
        prompt = "한글 작업과 공백, & 및 따옴표 \" 그대로 전달"
        prompt_file = self.root / "작업 요청.md"
        prompt_file.write_text(prompt, encoding="utf-8")
        fixture = [sys.executable, str(script)]
        resolved = cli_argv(fixture, "codex")
        self.assertEqual(Path(resolved[0]).resolve(), Path(sys.executable).resolve())
        self.assertEqual(resolved[1], str(script))
        argv = CodexSubstrate(bin=fixture).argv(prompt_file, self.project, "offline-model", "low")
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", argv)
        self.assertNotIn("--dangerously-bypass-hook-trust", argv)
        sandbox = argv.index("--sandbox")
        self.assertEqual(argv[sandbox + 1], "read-only")
        result = subprocess.run(
            argv,
            cwd=self.project,
            input=prompt.encode("utf-8"),
            capture_output=True,
            check=True,
            timeout=10,
        )
        payload = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual(payload["prompt"], prompt)
        self.assertEqual(Path(payload["cwd"]).resolve(), self.project)
        self.assertEqual(payload["argv"], argv[2:])


if __name__ == "__main__":
    unittest.main()
