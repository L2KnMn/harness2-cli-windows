# Local and hosted Windows offline comparison: 2026-10-21

Both environments completed the same 85 selected tests with no failures or errors.
This validates the foundation scope; native Windows live model experiments remain blocked.

| Environment | OS | Python | Foundation (74) | Runtime regressions (11) | Total |
| --- | --- | --- | --- | --- | --- |
| User PC, managed execution context | Windows 11, build 26200 | 3.12.6 | 68 pass, 6 skip | 11 pass | 79 pass, 6 skip |
| Standard GitHub-hosted VM | Windows Server 2022, build 20348 | 3.12.6 | 69 pass, 5 skip | 11 pass | 80 pass, 5 skip |

All group process exits and aggregate exits were 0. Independent review reconciled source
test IDs, individual JSON/logs, aggregate reports, selectors, and the exact outcome difference.
The only difference was `PortablePathsTests.test_real_junction_is_rejected_before_read_write_and_delete`:
local junction creation returned Access Denied and the fixture skipped; it passed on the VM.
The other five skips are POSIX process-control tests on both Windows hosts.

## Reproduction and source identity

Both used this command from the repository root:

```powershell
python -X utf8 -B scripts/run_windows_offline.py --output .test-temp/windows-offline
```

The runner uses standard Python only. It creates temporary package metadata for imports,
starts each hardcoded test group in a separate Python process, and saves counts, outcomes,
skip reasons, environment metadata, and UTF-8 logs. Any test-group failure makes its final
exit nonzero; known regression assertions were neither relaxed nor marked expected-failure.

| Source identity | Value |
| --- | --- |
| Hosted tested commit | `c4d117f6a045ab843fea2cc1a38427e6c12886dd` |
| Local tested commit | `5e09742780e5aa5fcc74e3a8b0bb5ceb31ebb7a4` |
| Exact tree on both hosts | `3943d29664ee27a15dd19f29c4b9307df2e89639` |

Commit metadata differs because publication used Git Data API after local Git transport
failed. The tested content trees and all 85 executed test IDs match exactly. This report
is a later documentation change; it does not claim that documentation commit was rerun.

The foundation group contains test_windows_platform, test_windows_smoke, test_portable_paths,
test_safe_argv, test_providers, test_registry, and test_agent_ops. The regression group contains
test_runtime.EventsTests and test_runtime.RuntimeWorkflowTests. RuntimeWorkflow uses scripted
DemoAdapter/DemoProposer fixtures. Legacy test_runtime.ProposerTests and the full original
Unix-oriented test suites were not included.

## Evidence and execution limits

- [Completed hosted run](https://github.com/L2KnMn/harness2-cli-windows/actions/runs/39589021712)
- [Hosted job and setup logs](https://github.com/L2KnMn/harness2-cli-windows/actions/runs/39589021712/job/119185016204)
- [Five-file result/log artifact](https://github.com/L2KnMn/harness2-cli-windows/actions/runs/39589021712/artifacts/12340483946), retained for seven days, through 2026-10-28
- [Curated durable results, exact IDs and skip reasons](windows-offline-results.json)
- Local logs: `.test-temp/windows-offline/foundation.log` and `regression.log`; these raw logs are not committed.

Downloaded artifact SHA-256 was verified as
`3832ea6f22e38ddbc083942985c56fbf861b4aa52be3b8dfeb7989c7ced56c43` before reading
the five expected JSON/log files.

The public fork had no prior Actions run on this branch. Exactly one new run was started
by the dedicated branch-push workflow and followed through successful completion.
It used the standard `windows-2022` label, a 15-minute job limit, read-only repository token
permissions, and checkout credentials removed before testing. No billing, plan, runner
class, account authentication, or repository security settings were changed. GitHub's
[standard hosted runner usage in public repositories is free](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
Official setup-python prepared Python 3.12.6 (including its normal pip setup) inside the
disposable VM; no project/model package was installed, and the PC received no installation.
The test fixtures do not call a model CLI, network service, login, or credential store.
The checkout/setup/upload actions emitted a nonfatal Node.js compatibility warning; the
runner executed them successfully on Node.js 24.

The workflow also declares workflow_dispatch; GitHub's default-branch workflow discovery
rules still apply. This run used push. Main was not changed and no PR was created.

## Remaining limits

Both budget/resume samples reached the expected initial 3 calls, 14 adapter executions,
30 total calls, and zero repeated rollout executions. These single successful samples do
not fix or disprove the inherited concurrent admission and context-directory races recorded
in [the earlier cause isolation](windows-foundation.md).

This is not a full Windows product acceptance result. Real Codex/model execution, process
ownership and complete stop/resume, reliable hard cost limits, byte-preserving patches,
transactional application, package installation/console entry points, Python 3.13, and the
entire original suite remain unvalidated here. No production implementation changed during
this comparison and no existing test assertion was weakened.
