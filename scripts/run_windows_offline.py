"""Run the explicitly supported offline Windows suites without installing the package."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
import tomllib
import traceback
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    "foundation": (
        "test_windows_platform",
        "test_windows_smoke",
        "test_portable_paths",
        "test_safe_argv",
        "test_providers",
        "test_registry",
        "test_agent_ops",
    ),
    "regression": ("test_runtime.EventsTests", "test_runtime.RuntimeWorkflowTests"),
}


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def environment_info() -> dict:
    git = {}
    for name, ref in (("head", "HEAD"), ("tree", "HEAD^{tree}")):
        try:
            completed = subprocess.run(
                ["git", "-C", str(ROOT), "rev-parse", ref],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                check=False,
            )
            git[name] = completed.stdout.strip() if completed.returncode == 0 else None
        except (OSError, subprocess.SubprocessError):
            git[name] = None
    return {
        "os": platform.system(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "git": git,
        "github_sha": os.environ.get("GITHUB_SHA"),
    }


class RecordedResult(unittest.TextTestResult):
    """Count test cases once while retaining individual failing subtest identifiers."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outcomes = {}

    def record(self, test, outcome):
        priority = {"pass": 0, "skip": 1, "fail": 2, "error": 3}
        previous = self.outcomes.get(test.id(), "pass")
        if priority[outcome] >= priority[previous]:
            self.outcomes[test.id()] = outcome

    def addSuccess(self, test):
        super().addSuccess(test)
        self.record(test, "pass")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.record(test, "fail")

    def addError(self, test, err):
        super().addError(test, err)
        self.record(test, "error")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.record(test, "skip")

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.record(test, "fail")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.record(test, "fail")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self.record(test, "fail" if issubclass(err[0], test.failureException) else "error")


def child_group(group: str, output: Path) -> int:
    sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
    started = time.monotonic()
    report = {
        "group": group,
        "selectors": list(GROUPS[group]),
        "environment": environment_info(),
        "state": "completed",
    }
    try:
        suite = unittest.defaultTestLoader.loadTestsFromNames(GROUPS[group])
        result = unittest.TextTestRunner(
            stream=sys.stdout, verbosity=2, resultclass=RecordedResult
        ).run(suite)
        counts = {
            label: sum(outcome == value for outcome in result.outcomes.values())
            for label, value in (("pass", "pass"), ("fail", "fail"), ("error", "error"),
                                 ("skip", "skip"))
        }
        failures = [
            {"id": test.id(), "traceback": detail}
            for test, detail in [*result.failures, *result.errors, *result.expectedFailures]
        ]
        failed_ids = sorted({item["id"] for item in failures}
                            | {test.id() for test in result.unexpectedSuccesses})
        success = result.wasSuccessful() and not result.expectedFailures
        report.update(
            tests=result.testsRun,
            counts=counts,
            outcomes=result.outcomes,
            success=success,
            failed_ids=failed_ids,
            failures=failures,
            skipped=[{"id": test.id(), "reason": reason} for test, reason in result.skipped],
            expected_failures=len(result.expectedFailures),
            unexpected_successes=len(result.unexpectedSuccesses),
            exit_code=0 if success else 1,
        )
    except BaseException:
        report.update(
            tests=0, counts={"pass": 0, "fail": 0, "error": 1, "skip": 0},
            success=False, failed_ids=[], skipped=[], exit_code=2,
            infrastructure_error=traceback.format_exc(),
        )
    report["duration_s"] = round(time.monotonic() - started, 3)
    write_json(output / f"{group}.json", report)
    return report["exit_code"]


def metadata_environment(runtime: Path) -> dict[str, str]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    name, version = project["name"], project["version"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._+-]*", version
    ):
        raise ValueError("project name/version cannot form isolated package metadata")
    metadata = runtime / "metadata"
    info = metadata / f"{re.sub(r'[-_.]+', '_', name)}-{version}.dist-info"
    info.mkdir(parents=True)
    (info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n", encoding="utf-8"
    )
    return {
        **os.environ,
        "PYTHONPATH": os.pathsep.join((str(metadata), str(ROOT), str(ROOT / "tests"))),
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def parent_groups(output: Path) -> int:
    started = time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat()
    reports = []
    with tempfile.TemporaryDirectory(prefix=".runtime-", dir=output) as temporary:
        runtime = Path(temporary)
        env = metadata_environment(runtime)
        for group in GROUPS:
            report_path, log_path = output / f"{group}.json", output / f"{group}.log"
            report = {
                "group": group, "state": "pending", "success": False, "tests": 0,
                "counts": {"pass": 0, "fail": 0, "error": 1, "skip": 0},
                "failed_ids": [], "skipped": [], "exit_code": 2,
            }
            write_json(report_path, report)
            scratch = runtime / group
            scratch.mkdir()
            group_env = {**env, "TMP": str(scratch), "TEMP": str(scratch), "TMPDIR": str(scratch)}
            group_started = time.monotonic()
            try:
                with log_path.open("wb") as log:
                    completed = subprocess.run(
                        [sys.executable, "-X", "utf8", "-B", str(Path(__file__).resolve()),
                         "--output", str(output), "--_child", group],
                        cwd=ROOT, env=group_env, stdout=log, stderr=subprocess.STDOUT,
                        check=False, timeout=600,
                    )
                loaded = json.loads(report_path.read_text(encoding="utf-8"))
                if loaded.get("state") == "completed":
                    report = loaded
                else:
                    report["infrastructure_error"] = "child exited before saving its report"
                report["process_exit_code"] = completed.returncode
                if completed.returncode:
                    report["success"] = False
                    report["exit_code"] = completed.returncode
            except Exception:
                report["infrastructure_error"] = traceback.format_exc()
            report["process_duration_s"] = round(time.monotonic() - group_started, 3)
            report["log"] = log_path.name
            write_json(report_path, report)
            reports.append(report)
            print(f"{group}: {report['tests']} tests, {report['counts']}, "
                  f"exit={report['exit_code']} ({log_path})", flush=True)
    exit_code = 0 if all(report["success"] for report in reports) else 1
    summary = {
        "started_at": started_at,
        "environment": environment_info(),
        "duration_s": round(time.monotonic() - started, 3),
        "groups": reports,
        "exit_code": exit_code,
    }
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        try:
            with Path(step_summary).open("a", encoding="utf-8") as stream:
                stream.write("\n### Windows offline test results\n\n")
                stream.write("| Group | Tests | Pass | Fail | Error | Skip | Exit |\n")
                stream.write("|---|---:|---:|---:|---:|---:|---:|\n")
                for report in reports:
                    counts = report["counts"]
                    stream.write(f"| {report['group']} | {report['tests']} | {counts['pass']} "
                                 f"| {counts['fail']} | {counts['error']} | {counts['skip']} "
                                 f"| {report['exit_code']} |\n")
        except OSError as exc:
            summary["step_summary_error"] = str(exc)
            print(f"Could not append GitHub step summary: {exc}", file=sys.stderr)
    write_json(output / "summary.json", summary)
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=".test-temp/windows-offline", type=Path)
    parser.add_argument("--_child", choices=GROUPS, help=argparse.SUPPRESS)
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to(ROOT):
        parser.error("--output must stay inside this repository")
    output.mkdir(parents=True, exist_ok=True)
    return child_group(args._child, output) if args._child else parent_groups(output)


if __name__ == "__main__":
    raise SystemExit(main())
