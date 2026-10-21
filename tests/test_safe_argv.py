"""Portable CLI contracts; fixtures launch only the current Python interpreter."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from harness2 import _argv, providers, settings
from harness2.core.proposer import Proposer
from harness2.core.spec import ChannelSpec
from harness2.settings import ConfigError
from harness2.substrate._native import check_cli, cli_argv
from harness2.substrate.codex import CodexSubstrate
from harness2.substrate.command import CommandSubstrate


class ArgvContractTests(unittest.TestCase):
    def test_native_model_entrypoints_are_blocked_before_dispatch(self):
        from harness2.cli import main

        for command in (["eval"], ["judge"], ["chat"], ["doctor", "--live"]):
            with self.subTest(command=command), patch.object(
                main, "NATIVE_WINDOWS", True
            ), patch.object(main, "version", return_value="offline"), patch(
                f"harness2.cli.{command[0]}.run"
            ) as dispatch, patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertEqual(main.main(["--json", *command]), 1)
                self.assertIn("unsupported", json.loads(output.getvalue())["error"])
            dispatch.assert_not_called()

    def test_provider_check_forwards_explicit_binary(self):
        provider = providers.Provider("login", "chatgpt-login")
        binary = [sys.executable, "fixture.py"]
        with patch.object(providers, "codex_logged_in", return_value=True) as logged_in:
            self.assertEqual(providers.check(provider, binary=binary), [])
        logged_in.assert_called_once_with(providers.codex_login_home(provider), binary)

    def test_windows_string_is_exact_path(self):
        binary = r"C:\한글 도구\Program Files\codex.exe"
        with patch.object(_argv, "_WINDOWS", True), patch.object(
            _argv.shutil, "which", return_value=binary
        ) as which:
            self.assertEqual(cli_argv(binary, "codex"), [os.path.abspath(binary)])
            which.assert_called_once_with(binary)
            self.assertEqual(cli_argv(f'"{binary}"', "codex"), [os.path.abspath(binary)])

    def test_array_preserves_arguments_and_input(self):
        binary = [sys.executable, "한글 fixture.py", "", "a & b", r"C:\a\b"]
        before = list(binary)
        self.assertEqual(cli_argv(binary, "codex"), binary)
        self.assertEqual(binary, before)
        self.assertEqual(cli_argv(tuple(binary), "codex"), binary)

    def test_windows_shell_shims_fail_closed(self):
        for suffix in (".cmd", ".bat", ".ps1", ".py"):
            with self.subTest(suffix=suffix), patch.object(_argv, "_WINDOWS", True), patch.object(
                _argv.shutil, "which", return_value="C:/tool" + suffix
            ), self.assertRaisesRegex(ConfigError, "native.*exe"):
                cli_argv("codex", "codex")

    def test_invalid_arrays_and_missing_binary(self):
        for value in ([], [""], ["python", 1], ["python\0.exe"], b"python", 3):
            with self.subTest(value=value), self.assertRaises(ConfigError):
                cli_argv(value, "codex")
        with patch.object(_argv.shutil, "which", return_value=None), self.assertRaisesRegex(
            ConfigError, "argv array"
        ):
            cli_argv("missing tool", "codex")

    def test_posix_legacy_string_remains_supported(self):
        with patch.object(_argv, "_WINDOWS", False), patch.object(
            _argv.shutil, "which", side_effect=[None, "/bin/wrapper"]
        ):
            self.assertEqual(
                cli_argv("'wrapper cli' --option", "codex"),
                [os.path.abspath("/bin/wrapper"), "--option"],
            )

    def test_settings_accept_arrays_and_reject_invalid_bin(self):
        for value in ([sys.executable, "fixture.py"], sys.executable):
            values = {**settings.DEFAULTS, "executor": {"bin": value}}
            settings._validate(values)
        for value in ([], [1], 1):
            with self.subTest(value=value), self.assertRaisesRegex(ConfigError, "executor.bin"):
                settings._validate({**settings.DEFAULTS, "executor": {"bin": value}})

    def test_codex_entrypoints_are_read_only_and_keep_hook_trust(self):
        sub = CodexSubstrate(bin=[sys.executable, "fake.py"])
        workspace = Path.cwd()
        commands = [
            sub.argv(workspace / "prompt.md", workspace, "fixture-model", "low"),
            sub.exec_argv("fixture prompt", workspace, "fixture-model"),
        ]
        for argv in commands:
            with self.subTest(argv=argv):
                self.assertEqual(argv[argv.index("--sandbox") + 1], "read-only")
                self.assertFalse(
                    any("bypass" in value or "skip-permissions" in value for value in argv)
                )

    @unittest.skipUnless(os.name == "nt", "native Windows shell guard")
    def test_shell_executor_cannot_launch_on_windows(self):
        with patch("harness2.substrate.command.subprocess.run") as execute:
            with self.assertRaisesRegex(ConfigError, "unsupported on native Windows"):
                CommandSubstrate("echo unsafe", ("*.txt",)).run(
                    Path("prompt"), Path.cwd(), Path.cwd(), 10, {}
                )
        execute.assert_not_called()

    def test_native_live_run_is_blocked_before_preflight_or_launch(self):
        from harness2.cli import run

        args = SimpleNamespace(name=None, argv=[], detach=False, dry_run=False)
        with patch.object(run, "NATIVE_WINDOWS", True), patch.object(
            run.registry, "load"
        ) as suite, patch.object(run.subprocess, "Popen") as launch:
            with self.assertRaisesRegex(ConfigError, "live experiments are disabled"):
                run.run(args, None)
        suite.assert_not_called()
        launch.assert_not_called()


class OfflinePythonLaunchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="한글 공백 argv ", dir=Path.cwd())
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.script = self.root / "가짜 CLI.py"
        self.script.write_text(
            "import json,sys\n"
            "from pathlib import Path\n"
            "if '--version' in sys.argv:\n"
            " print('offline fixture 1.0'); raise SystemExit(0)\n"
            "data={'argv':sys.argv[1:],'stdin':sys.stdin.buffer.read().decode('utf-8'),"
            "'cwd':str(Path.cwd())}\n"
            "event={'type':'item.completed','item':{'type':'agent_message',"
            "'text':json.dumps(data,ensure_ascii=False)}}\n"
            "sys.stdout.buffer.write((json.dumps(event,ensure_ascii=False)+'\\n')"
            ".encode('utf-8'))\n",
            encoding="utf-8",
        )

    def test_python_fixture_roundtrip(self):
        binary = [sys.executable, str(self.script)]
        check_cli(binary, "codex")
        result = subprocess.run(
            [*cli_argv(binary, "codex"), "공백 인자", "x & y"],
            input="한글 입력\n".encode("utf-8"),
            capture_output=True,
            cwd=self.root,
            timeout=10,
            check=True,
        )
        value = json.loads(json.loads(result.stdout)["item"]["text"])
        self.assertEqual(value["argv"], ["공백 인자", "x & y"])
        self.assertEqual(value["stdin"], "한글 입력\n")
        self.assertEqual(Path(value["cwd"]), self.root)

    def test_proposer_uses_same_contract_without_model(self):
        spec = ChannelSpec("codex", "offline/model", bin=[sys.executable, str(self.script)])
        prop = Proposer(spec)
        text, cost, error = prop._codex(self.root, "한글 mission", "한글 system", 10)
        self.assertEqual((cost, error), (0.0, ""))
        value = json.loads(text)
        self.assertEqual(value["argv"][:3], ["exec", "--json", "--skip-git-repo-check"])
        self.assertEqual(value["argv"][value["argv"].index("--sandbox") + 1], "read-only")
        self.assertIn("한글 mission", value["stdin"])
        self.assertIn("한글 system", value["stdin"])
        self.assertFalse(any("bypass" in v for v in value["argv"]))

    def test_json_stdout_is_utf8_even_when_process_default_is_cp949(self):
        code = (
            "from unittest.mock import patch\n"
            "from harness2.cli import main\n"
            "def output(args,ctx):\n"
            " ctx.out({'text':'한글 😀'},str); return 0\n"
            "with patch.object(main,'version',return_value='offline'), "
            "patch('harness2.cli.status.run',side_effect=output):\n"
            " raise SystemExit(main.main(['--json','status']))\n"
        )
        env = dict(os.environ, PYTHONIOENCODING="cp949", PYTHONUTF8="0")
        result = subprocess.run(
            [sys.executable, "-c", code],
            env=env,
            capture_output=True,
            check=True,
            timeout=10,
        )
        self.assertEqual(json.loads(result.stdout.decode("utf-8")), {"text": "한글 😀"})

    def test_export_directory_conflict_leaves_existing_harness_intact(self):
        from harness2.substrate._native import export_files

        (self.root / "AGENTS.md").write_text("keep", encoding="utf-8")
        (self.root / "directory").mkdir()
        with self.assertRaisesRegex(ConfigError, "existing directory"):
            export_files(self.root, {"AGENTS.md": "changed", "directory": "file"}, {})
        self.assertEqual((self.root / "AGENTS.md").read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
