# Windows foundation validation: 2026-10-21

This records the first offline Windows milestone, not a complete Windows release.
The later [local/hosted comparison](windows-offline-comparison.md) records the completed
Windows VM and PC run; the initial checks below remain a historical record.
Baseline: `0c811344a4edfe34960b2fc8f286369d7e81fb27`.
Local implementation commit: `ff21ee953bfea2aa899bfae51c835c617aeb8402`.
The documentation commit follows that local implementation.

## Completed scope

Signal-free Windows PID observation, cross-process summary locks, common executable/argv
contracts, portable relative keys and managed-path preflight, UTF-8 CLI output, Korean and
space-containing path fixtures, and a dedicated Windows CI foundation job are implemented.
Codex argv omits approval/sandbox bypass flags and requests read-only sandboxing.
Native Windows live CLI `run`, `eval`, `judge`, `chat`, `doctor --live`, live stop/detach,
and the generic POSIX shell-command executor remain blocked. The offline tests use the
current Python interpreter or mocks, never a real model CLI. These CLI guards are scope
checks, not a security boundary for arbitrary direct Python library callers.

## Executed checks

Environment: native Windows, CPython 3.12.6, with process-local writable TMP/TEMP and local
test metadata. The repository was not installed and no dependencies were installed.

| Check | Actual result |
| --- | --- |
| Final selected suite: test_windows_platform, test_windows_smoke, test_portable_paths, test_safe_argv, test_providers, test_registry, test_agent_ops | 74 run: 68 passed, 6 skipped, 0 failures/errors |
| Skips in that suite | One real junction fixture unavailable; five POSIX process-control cases skipped on Windows |
| Independent foundation review run, before the final extra guard test | 60 run: 59 passed, 1 junction skip |
| Independent final safe-argv checks | 15 passed |
| Python source AST parsing | 79 files parsed |
| git diff --check | Passed |
| Broader earlier offline subset | 103 run: 95 passed, 7 skipped, 1 budget/resume failure |
| Repeated standalone budget/resume test | 2 passes and 2 failures in 4 repeats; not declared stable |
| Full original Windows suite | Attempted and interrupted after failures in legacy Unix fixtures; not passed |
| Ruff | Not run; unavailable and not installed for this task |
| GitHub Actions, Python 3.13, Linux/macOS/plugin suites | Not executed during local validation |

The workflow is configured for pushes to main and pull requests. Publishing this development
branch without a PR does not itself establish a CI pass. No real model, login, or paid
experiment was executed. The existing Codex money field is not reliable cost evidence.

## Budget/resume failure isolation

### Four calls against max_calls=3: inherited admission race

Baseline and current `harness2/core/events.py` are identical Git blob
`0188925fa26ffd2618194be146520b40b5f31daf`.
An independent offline diagnostic loaded each version separately, emitted two completed
calls, then used a barrier so two harmless workers both passed `check()` before either
emitted. Both versions ended at calls=4, max_calls=3. Individual checks and event updates
are locked; admission across the work interval is not reserved atomically.

### Twenty-nine calls instead of thirty: inherited context fallback

An instrumented DemoAdapter/DemoProposer fixture produced one 30-call sample and one
29-call sample, each with 14 adapter executions. In the latter, ledger-2's aggregate-mode
dom1 stage failed at `context.build():128`, `dest.mkdir(parents=True, exist_ok=True)`, with
WinError 5. The unchanged stage handler returned fallback with attempts=0 before calling
the proposer, explaining the missing session.

Both revisions have identical context and recursion source blobs:

- `harness2/core/context.py`: `72f2868b06c13e30c031cb91c0f04dcd80293ec9`
- `harness2/core/recursion.py`: `99154ce15513c17e2f4a03cb4f2175a4ad95eeb3`

An independent reviewer separately loaded baseline/current context.build and ran a minimal
offline adapter with no harness, pool, library, or model. Each row represents 600 pairs of
concurrent stage-directory builds:

| Source | Shared parent created by workers | Shared parent prepared serially |
| --- | --- | --- |
| Baseline context.build | 2 WinError 5 failures | 0 failures |
| Current context.build | 15 WinError 5 failures | 0 failures |

A separate standard-library-only mkdir diagnostic also reproduced this pattern without
importing harness code: 5 failures in 600 fresh-parent pairs versus 0 in 600 prepared-parent
pairs (an earlier fresh-parent sample had 8 failures). These intermittent counts do not
establish a performance difference. The exact Windows filesystem/filter/sandbox cause of
ACCESS_DENIED is unresolved. No ACL or sandbox changes were attempted.

Both observed failure mechanisms therefore predate this milestone. The entire baseline
workflow was not run successfully on Windows; these are isolated, exact-source comparisons.
No assertion was weakened and no budget/resume production fix was included.

## Review and follow-up

Four Codex workers split process/locking, paths, CI/tests, and independent review.
Independent review findings were integrated, including reserved device-name variants,
configured binary forwarding, mock boundaries, UTF-8 pipe coverage, and live-entry guards.

Minimum follow-up: atomic call admission reservations with cached/retried/cancelled
settlement; coordinator-created context parents before parallel stage setup; explicit
unexpected-fallback assertions. Full process ownership/stop/resume, reliable timeouts,
unknown-versus-known costs, evaluation cache accounting, byte-preserving CRLF/binary patches,
and transactional apply remain separate work. Keep live Windows experiments blocked until
their required lifecycle and cost constraints are validated.

## Repository preservation and publication

The local checkout was reconstructed from verified source blobs and original Git trees
after Git transport failed. Seven unchanged image/video asset blobs are absent locally;
their original entries remain in every committed tree. No asset deletion is part of this
change. Publication must build on the original remote tree, preserve every asset mode and
OID, and verify the final remote tree against the local committed tree before reporting
success. Raw logs, user settings, credentials, and temporary test workspaces are excluded.
