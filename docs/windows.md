# Native Windows foundation

This fork's first Windows milestone provides portable CLI arguments, signal-free process
observation, cross-process summary locks, managed-path validation, and offline tests. It
does not yet provide a complete Windows experiment lifecycle.

## Supported contracts

- Python 3.12 and 3.13. The Windows CI job runs the named foundation suites. Existing full
  Linux/macOS core and benchmark-plugin jobs remain in place.
- Prefer an explicit argument array for `executor.bin` and each model role's `bin`:

  ```toml
  [executor]
  name = "codex"
  bin = ['C:\Tools with spaces\codex.exe']

  [improver]
  channel = "codex"
  bin = ['C:\Tools with spaces\codex.exe']
  ```

  A Windows string is one executable path, with optional outer double quotes. Extra
  arguments must be array elements. `.cmd`, `.bat`, `.ps1`, and direct `.py` launchers are
  rejected; configure the native executable or an explicit interpreter array. POSIX keeps
  its legacy shell-like string parsing. No shell is used by this resolver.
- Core Codex launches use `--sandbox read-only`. Approval and hook-trust bypass flags
  are not supplied. This restrictive foundation is suitable for inspecting contracts;
  an editing experiment needs a separately reviewed permission design in a later milestone.
- `--json` stdout is UTF-8, including when the process starts with a legacy code page.
  Codex proposer input/output is explicitly UTF-8. Git binary patches still require the
  separate byte-preservation milestone below.
- Internal file keys and fingerprints use `/`. Managed paths reject Windows device names,
  drive/UNC paths, traversal, alternate data streams, case aliases, and symlink/junction
  redirection. Korean and space-containing paths are covered by offline fixtures.
- Windows PID observation opens a query handle and performs a zero-time wait. It sends
  no console signal. An inaccessible PID is conservatively treated as potentially alive.
  This observation does not prove ownership or protect against PID reuse.
- Summary writers cooperate through a persistent sidecar lock, using `msvcrt` on Windows
  and `flock` on POSIX. Do not remove sidecars while writers may be running.

## Explicit limits

Native Windows live `run`, `eval`, `judge`, `chat`, and `doctor --live` are disabled;
`run --dry-run` and offline inspection remain available. Background
`run --detach` and stopping a live run also fail with an actionable error until
the process supervisor can own and stop the complete child tree. The generic shell-command
executor is also blocked on native Windows because its templates use POSIX quoting.

Full stop/resume, reliable process-tree timeouts, exact patch bytes/CRLF handling,
cost/evaluation accounting, and transactional result application remain follow-up work.
The legacy parallel budget/resume regression intermittently reports either an initial
4 calls against a limit of 3 or 29 total calls against an expected 30. Its assertion has
not been weakened; this remains an open investigation, and live Windows runs stay blocked.
Codex-reported money is currently unknown even where legacy records contain `0.0`; do not
interpret that value as free usage or rely on the existing USD budget as a hard cap.

The legacy Windows suites still contain Unix executable fixtures, shell commands, HOME
assumptions and permission-bit assertions. The foundation CI job does not claim those
suites pass. Real junction creation can be unavailable in a restricted test environment;
the test records a skip reason and separately exercises the junction checks with mocks.

Path preflight protects against predictable errors before changing managed files. It is
not a race-proof filesystem transaction. Work on an isolated checkout, preserve user
changes, inspect a diff, and obtain authorization before applying project instructions.
No global Codex configuration, credentials, or approval policy is changed by this milestone.

## Offline validation

Run the Windows foundation suites after making the package available in a local test
environment:

```powershell
python -X utf8 -B -m unittest discover -s tests -p "test_windows_*.py" -v
python -X utf8 -B -m unittest discover -s tests -p "test_portable_*.py" -v
python -X utf8 -B -m unittest discover -s tests -p "test_safe_argv.py" -v
```

Fixtures explicitly invoke the current Python interpreter, exercise Korean/spaced paths,
and never invoke a model CLI. The tests do not log in, install agents, or change machine
permissions. Point process-local `TMP` and `TEMP` at a writable test directory when a
managed environment's default temporary directory is inaccessible.
