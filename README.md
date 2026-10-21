[English](README.md) | [한국어](README.ko.md)

# Harness2 CLI Windows fork

[L2KnMn/harness2-cli-windows](https://github.com/L2KnMn/harness2-cli-windows) is an
independent fork of [3ae3ae/harness2-cli](https://github.com/3ae3ae/harness2-cli),
working toward safe native Windows support. The original research is
[google-research/harness2](https://github.com/google-research/harness2).
The goal is to experiment with project instructions, skills, prompts and helper scripts,
then review the results. This tool does not change model weights or the user's approval
and security policies.

**This is currently an offline Windows compatibility foundation, not a completed Codex improvement workflow.**
The guide below defines this fork's current support. The general upstream documentation
that follows is retained for attribution and design reference; it does not establish that
those commands work unchanged on Windows.

- [Current support and validation](#current-support-and-validation)
- [Installing this fork](#installing-this-fork)
- [Preparing a project and task](#preparing-a-project-and-task)
- [Previewing a plan without authentication](#previewing-a-plan-without-authentication)
- [Inspecting saved runs and reviewing results](#inspecting-saved-runs-and-reviewing-results)
- [Offline tests](#offline-tests)
- [Current limitations and next steps](#current-limitations-and-next-steps)
- [Upstream reference documentation](#upstream-reference-documentation)

## Current support and validation

| Area | Current status |
| --- | --- |
| Process liveness | Queries Windows processes without sending signals; treats access denial conservatively |
| Files and paths | Cross-process locking, `/` relative paths, Korean and spaced paths, reserved-name and junction checks |
| Execution arguments | Explicit argv arrays, UTF-8 I/O, Codex approval and sandbox bypass options removed |
| Project setup and inspection | init, task/config commands, saved-run inspection and dry-run with its prerequisites met |
| Real-model experiments | Native Windows live run/eval/judge/chat/doctor --live remain blocked |
| Linux/macOS | Upstream code and CI retained; full support by this fork has not been established |

On 2026-10-21, the recorded baseline at commit `c4d117f6` compared **the same 85 tests
on Python 3.12.6**. Local Windows 11 recorded **79 pass / 6 skip**; the GitHub Windows
Server 2022 VM recorded **80 pass / 5 skip**. Both had zero failures and errors.
The difference was one real junction test skipped locally because creation was denied.
These figures do not validate the full product, real-model runs or package installation.
See the [logs, commits and detailed results](docs/validation/windows-offline-comparison.md)
and [Windows support contract](docs/windows.md).

## Installing this fork

Python 3.12 or 3.13 and Git are required. The shared 85-test baseline above used 3.12.6.
The following is a **source installation procedure for this fork**, for users who choose
to install it. Package installation itself was not validated by the offline comparison.
Run these commands in PowerShell.

```powershell
git clone https://github.com/L2KnMn/harness2-cli-windows.git
Set-Location harness2-cli-windows
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\harness2.exe --help

$python = (Resolve-Path .\.venv\Scripts\python.exe).Path
$harness2 = (Resolve-Path .\.venv\Scripts\harness2.exe).Path
```

There is no need to activate the venv or change PowerShell execution policy.
The distribution name is still `harness2-cli`, and the command is `harness2`.
A plain `pip install harness2-cli`, or the upstream installation URL below, can install
**the original distribution instead of this fork**. Running the normal CLI from a source
checkout also requires package metadata.

The Codex CLI and model authentication are separate prerequisites for future real-model
experiments. Do not install Codex, sign in or configure keys for the offline tests and
test-only preview below. Real-model setup and execution are outside current Windows support.

## Preparing a project and task

Start in a practice directory separate from existing development repositories.
The commands below prepare only that directory's `.harness2/`. Initialization stops if
configuration already exists; using `--force` is not recommended here.
Use a shell without `HARNESS2_*` or profile overrides. Before creating the task, inspect
`config show --origin` to confirm that the paths resolve to the project-relative paths below.

```powershell
$project = Join-Path (Split-Path (Get-Location) -Parent) "하네스 연습 프로젝트"
New-Item -ItemType Directory -Path $project -ErrorAction Stop
& $harness2 -C $project init --yes --executor codex --auth api-key
& $harness2 -C $project config set paths.tasks .harness2/tasks
& $harness2 -C $project config set paths.runs .harness2/runs
& $harness2 -C $project config show --origin
& $harness2 -C $project task new hello-ko --files --domain smoke --check "python -X utf8 check/verify.py"
New-Item -ItemType Directory -Path (Join-Path $project ".harness2/tasks/hello-ko/check")
& $harness2 -C $project --json task ls
```

Here, `--auth api-key` selects the configuration format without storing a key or signing in.
`init` may query detected Claude/Codex CLIs with `--version`. Choosing the default login
method also checks authentication status. This example does not require new authentication;
a missing-key message is expected until the test-only configuration below replaces it.

Save the following files as **UTF-8 without a BOM**. Replace the generated `TODO:` text
in `task.md`.

```text
.harness2/tasks/hello-ko/
  task.md
  task.toml
  files/input.txt
  check/verify.py
```

`task.md`:

```text
작업 디렉터리의 input.txt를 UTF-8로 읽고,
같은 내용을 output/answer.txt에 UTF-8로 작성하세요.
외부 네트워크를 사용하지 마세요.
```

Put text to compare, such as `안녕하세요`, in `files/input.txt`. The contents of `files/`
are copied to the temporary workspace root, so the task and check refer to `input.txt`,
rather than `files/input.txt`.

`task.toml`:

```toml
domain = "smoke"
split = "train"
workspace = "files"
deliverable = "files"
timeout = 60
check = "python -X utf8 check/verify.py"
```

`check/verify.py`:

```python
import json
from pathlib import Path

expected = Path("input.txt").read_text(encoding="utf-8").strip()
answer = Path("output/answer.txt")
passed = answer.is_file() and answer.read_text(encoding="utf-8").strip() == expected
print(json.dumps({"n_passed": int(passed), "n_criteria": 1}))
raise SystemExit(0 if passed else 1)
```

`check` is a **shell-command string**, not an argv array. It runs in a fresh workspace
during future evaluation; do not assume that the default Windows shell is PowerShell.
Write only checks you trust. The final JSON line supplies partial scores, while exit code
0 indicates success. Windows `eval` and `judge` are currently blocked, and dry-run does not
execute this check.

Repository-editing tasks use `workspace = "project"` and `deliverable = "diff"`.
They require a valid commit in a Git repository and create an isolated worktree from the
commit specified by `ref`. Uncommitted changes are not automatically included.
See the [task documentation](docs/tasks.md).

## Previewing a plan without authentication

A normal `run --dry-run` still performs executable and provider preflight checks, so an
existing real-model configuration can trigger CLI or authentication-status queries.
**To inspect the prepared task and estimated call count without authentication**, replace
the generated `.harness2/config.toml` in the practice directory with the test configuration
below. It uses Python in the executable slot and a loopback provider address that is never
contacted. No model CLI, server or key is needed. Do not use this as a real experiment
configuration.

Use a shell without `HARNESS2_*`, profile or additional `-c` overrides. Configuration
precedence is defaults → global config → project config → environment → CLI.
Before previewing, check the final `config show --origin`: the suite must be tasks, and
all model roles must use the preview provider.

```powershell
$pythonToml = $python | ConvertTo-Json -Compress
$previewConfig = @"
[suite]
name = "tasks"

[executor]
name = "codex"
bin = [$pythonToml]
model = "preview/offline"

[improver]
channel = "codex"
bin = [$pythonToml]
model = "preview/offline"

[selector]
channel = "codex"
bin = [$pythonToml]
model = "preview/offline"

[reflector]
channel = "codex"
bin = [$pythonToml]
model = "preview/offline"

[judge]
channel = "codex"
bin = [$pythonToml]
model = "preview/offline"

[providers.preview]
type = "openai"
base_url = "http://127.0.0.1:9/v1"
api_key_env = ""

[paths]
harness = "."
tasks = ".harness2/tasks"
runs = ".harness2/runs"

[run]
k = 1
workers = 1
"@
[IO.File]::WriteAllText((Join-Path $project ".harness2/config.toml"), $previewConfig, [Text.UTF8Encoding]::new($false))
& $harness2 -C $project config show --origin
& $harness2 -C $project --json run --name preview --dry-run --only-tasks hello-ko
& $harness2 -C $project --json runs ls
```

This preview does not execute a model, check or network request, and does not create a new
`run.json`. An empty `runs ls` and a missing-run error from `status preview` are therefore
expected. Do not overwrite an existing real project configuration with this example.

When configuring a real Codex path later, a Windows string means **one executable**.
Additional arguments belong in an argv array, such as
`bin = ['C:\도구\codex.exe', '인자']`. Direct `.cmd`, `.bat`, `.ps1` and `.py` shim execution
is rejected. A configuration example is not authorization for a real-model run.

## Inspecting saved runs and reviewing results

Use the following only when a saved run already exists. Replace `saved-run` with its actual name.

```powershell
& $harness2 -C $project --json runs ls
& $harness2 -C $project --json runs show saved-run
& $harness2 -C $project --json status saved-run
& $harness2 -C $project --json diff saved-run --stat
```

Review improvements as a diff against the original harness. `eval` compares the baseline
and candidate on the same tasks; `apply --dry-run` previews an application plan.
An actual `apply` changes project files. Do not automate it: preserve user changes in a
separate review checkout and approve the concrete diff before applying it.
The complete Windows evaluation and application paths have not been validated. Without
saved results, a diff or application plan is unavailable as well.

An outer Codex calling this CLI as a tool differs from the separate `codex exec` process
inside the CLI. Future experiments must manage that process's usage, time and permissions.
Existing resume support reuses completed stages; it does not guarantee continuation of an
interrupted Codex conversation.

## Offline tests

Run the following from the fork repository root. It uses the installed Python without
installing this project, and requires no Codex, keys or login. Temporary metadata and
working directories are isolated for testing.

```powershell
py -3.12 -X utf8 -B scripts/run_windows_offline.py --output .test-temp/windows-offline
```

The foundation modules and 11 Demo-fixture regression tests run in separate processes and
save JSON reports and logs. A failure in either group makes the final exit code nonzero.
The 85-test figures above belong to the linked validation commit. One regression test for
lock contention on an empty sidecar was added afterward, bringing the current selected
scope to 86 tests. This is not the full upstream suite. Unavailable real-junction creation
and POSIX-only controls are recorded with skip reasons.

## Current limitations and next steps

- Native Windows live `run`, `eval`, `judge`, `chat`, `doctor --live`, live stop/detach,
  and the general-purpose POSIX shell executor remain blocked. Documentation does not
  remove these guards.
- Existing budget accounting has no concurrent-call reservation, so a limit of 3 calls can
  become 4. Parallel context-directory creation can also encounter access errors and fall
  back, producing 29 total calls instead of 30. Both causes were reproduced at the original
  commit and **remain unfixed**. One successful test run does not establish stability.
  A Codex cost of `0.0` does not mean free usage; do not treat the USD budget as a hard cap.
- Process ownership, stop/resume, deadlines, cost and evaluation accounting, CRLF/binary
  patch preservation, and application transactions that preserve user changes need further
  validation.
- These results do not establish full Linux support either. General CLI and benchmark-plugin
  functionality in the upstream reference below is separate from this fork's Windows status.

## License and attribution

This fork's root license is [Apache-2.0](LICENSE). The original research and implementation
are credited to the paper's Google authors; the general-purpose CLI comes from
[3ae3ae/harness2-cli](https://github.com/3ae3ae/harness2-cli).
This is an independent fork, not a Google product. Third-party code in the benchmark plugin
retains its respective upstream licenses. The paper citation and license explanation below
are also preserved.

## Upstream reference documentation

The introduction, original installation URLs, general execution examples and CI badges below
are **reference documentation from 3ae3ae/harness2-cli**. Follow the guide above for this
fork's current Windows usage. Attribution, the paper, licenses and useful existing
explanations are preserved. In particular, the real-model run/login/detach/eval examples
below are not currently supported Windows commands.

---

<h3 align="center">
  <img src="assets/Harness2-wordmark.png" alt="Harness²" width="360"><br>
  Harness² CLI: tune your coding agent's harness on your own tasks
</h3>

<p align="center">
  <a href="https://github.com/3ae3ae/harness2-cli/actions/workflows/ci.yml"><img src="https://github.com/3ae3ae/harness2-cli/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://arxiv.org/abs/2610.14224"><img src="https://img.shields.io/badge/Paper-arXiv-EA4335?logo=arxiv&logoColor=white" alt="Paper"></a>
  <a href="https://harness2.github.io"><img src="https://img.shields.io/badge/Website-harness2.github.io-4285F4?logo=googlechrome&logoColor=white" alt="Website"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-34A853" alt="License"></a>
</p>

A coding agent is a model plus a **harness**: the instructions, skills, subagents, helper
scripts and hooks it runs with. `harness2` improves the harness of the agent you already use
(Claude Code's `CLAUDE.md` and `.claude/`, or Codex's `AGENTS.md` and `.agents/`) by running
it on tasks from your own project, studying what happened, and refining the harness from
that evidence. The model stays the same. Your files change only when you apply the result.

Harness² CLI is a general-purpose version of
[Harness²: Recursive Agent Harnessing for an Open World](https://arxiv.org/abs/2610.14224).
The original release ([google-research/harness2](https://github.com/google-research/harness2))
reproduces the paper on three fixed benchmarks with Vertex AI. This fork turns the same method
into a command-line tool for any project, any task, Claude Code or Codex (or your own agent),
on your subscription or any model provider. [What changed](#what-changed-from-the-original)
lists the differences; the paper's benchmark setup lives on as a
[plugin](plugins/harness2-benchmarks/).

- [How it works](#how-it-works)
- [Install](#install)
- [Quick start](#quick-start)
- [Driving it from an agent](#driving-it-from-an-agent)
- [Commands](#commands)
- [Configuration](#configuration)
- [What changed from the original](#what-changed-from-the-original)
- [Documentation](#documentation)

## How it works

For every task you give it, `harness2`:

1. runs your agent with its current harness and records what it does;
2. has an improver agent propose harness edits from those trajectories, from two angles:
   how the agent works, and what it needs to know about this kind of task;
3. runs the agent with each candidate harness, and composes a refined one from what the
   differences between the runs show;
4. keeps the refined harness and a short lesson for the next task in the same area.

When all tasks are done, it combines what the tasks taught into **one final harness** for
your project. That is the single result you review with `harness2 diff` and write into the
project with `harness2 apply`.

No step needs a grade or a reference answer, so any task you can describe can be used. If
you can also check results, with a test command or a rubric, `harness2 eval` measures the
final harness against the one you started with. [How it works](docs/how-it-works.md) has
the details.

<p align="center">
  <a href="assets/harness2_pipeline.png">
    <img src="assets/harness2_pipeline.png" alt="Harness² pipeline: an agent runs the initial harness, an editor proposes general and domain-specific edits, candidate runs probe them, and a composer combines them into the final harness. A reflector then updates the experience carried to the next task." width="100%">
  </a>
</p>

## Install

You need Python 3.12 or 3.13, git, and the agent CLI whose harness you want to tune,
installed, on your `PATH` and logged in:
[Claude Code](https://docs.claude.com/en/docs/claude-code) (`claude`) or
[Codex](https://github.com/openai/codex) (`codex`).

```bash
uv tool install git+https://github.com/3ae3ae/harness2-cli
# or: pipx install git+https://github.com/3ae3ae/harness2-cli
```

By default runs use your subscription, so a Claude or ChatGPT plan is enough: Claude Code
runs on its own login, and Codex on a login kept for harness2 that you make once with
`harness2 login codex`. You
can use an API key or another provider instead; see [Configuration](#configuration). Runs
make many model calls and use money or subscription quota: the [quick start](#quick-start)
shows how to see the number of calls first and how to cap them.

## Quick start

Inside the project whose agent setup you want to improve:

```bash
harness2 init                          # pick the agent, how it logs in, where the harness lives
harness2 task new fix-login-redirect   # then write the request in .harness2/tasks/fix-login-redirect/task.md
harness2 doctor                        # check the CLI, its login and the tasks
harness2 run --dry-run                 # the tasks and how many model calls a run makes
harness2 run --max-calls 200           # refine the harness on every task, then build the final one
```

A run works in temporary git worktrees, so your working tree is never touched. While it
runs, from another terminal:

```bash
harness2 status --watch                # progress, spend, the harness picked per task
```

When it has finished:

```bash
harness2 diff                          # what the final harness changes
harness2 eval                          # optional: compare it with your current harness on graded tasks
harness2 apply                         # review the changes and write them into the project
```

Running `harness2 run` again resumes an interrupted or limited run and reuses every finished
step. Write a few varied tasks that look like the work you really do: see
[Tasks](docs/tasks.md).

## Driving it from an agent

`harness2` is built to be driven by an AI agent as well as by hand. Every command has
`--json`, errors included; no command waits for input without a terminal, since every prompt
has a flag; and long runs go to the background with `harness2 run --detach`, are followed with
`harness2 status --json` and are stopped with `harness2 stop`.

`harness2 guide` prints the contract for agents, with your project's current state. Tell your
agent to read it, or install it as a Claude Code skill:

```bash
harness2 guide --install claude
```

## Commands

| Command | What it does |
|---|---|
| `harness2 init` | Set up `.harness2/` in a project, with a short wizard (`--yes` for defaults) |
| `harness2 doctor` | Check the agent CLIs, their login or keys, settings and tasks; `--live` also makes one tiny call per model |
| `harness2 task new / ls / import` | Create, list and import tasks |
| `harness2 run` | Refine the harness on the tasks and build the final harness; `--dry-run` previews, `--max-calls` / `--budget-usd` cap spending, `--detach` runs in the background, `--selector human` lets you pick between candidates |
| `harness2 status` | A run's progress; `--watch` keeps it updated |
| `harness2 stop` | Stop a running run; running it again resumes |
| `harness2 diff` | What the final harness changes |
| `harness2 eval` | Compare the final harness with the starting one on graded tasks |
| `harness2 apply` | Write the final harness into the project after showing the changes; `-i` to accept file by file |
| `harness2 judge` / `report` | Grade each task's adopted result, and summarise the grades |
| `harness2 runs ls / show / rm` | List, inspect and delete runs |
| `harness2 config show / get / set` | Read and change settings; `show --origin` says where each value comes from |
| `harness2 login` | Check the subscription logins; `login codex` signs Codex in for harness2 |
| `harness2 chat` | Talk to your agent CLI about tasks, runs and results |
| `harness2 guide` | The guide for AI agents that use harness2 |
| `harness2 demo` | A local run with scripted editors and no model calls |

Every command takes `--help`. The [command reference](docs/cli.md) lists every flag, the exit
codes and the layout of a run directory.

## Configuration

Settings come from `~/.config/harness2/config.toml`, the project's `.harness2/config.toml`,
`HARNESS2_*` environment variables and flags, in that order of precedence. Models are
written `provider/model`:

```toml
[executor]
name = "claude"
model = "claude-login/claude-sonnet-5-5"   # your Claude subscription, through Claude Code

[improver]
channel = "claude"
model = "claude-login/claude-opus-5-5"
```

`chatgpt-login/<model>` uses your ChatGPT subscription through Codex (after
`harness2 login codex`). API keys and other
endpoints work too: Anthropic, OpenAI, any OpenAI-compatible or Anthropic-compatible
server, Vertex AI and Bedrock. To tune an agent other than Claude Code or Codex, the
`command` executor runs your own command and edits the files you list.
[Configuration](docs/configuration.md) covers every setting.

## What changed from the original

| | google-research/harness2 | Harness² CLI |
|---|---|---|
| Tasks | JobBench, LAB, WorkBuddy-Bench | your own tasks, in your repository or from files; the benchmarks as a plugin |
| Agents | OpenCode, Codex, pinned builds | Claude Code, Codex or any command, as installed on your system |
| Models | Vertex AI | your Claude or ChatGPT subscription, or any API provider |
| Result | one adopted harness per task, kept for scoring | one final harness for the project, which you review and apply |
| Interface | seven scripts, settings in `.env` | one `harness2` command, layered TOML settings, JSON output, background runs, resumable limits |

The method itself (propose, probe, compose, and the library of lessons) and its prompts are
the paper's. [How it works](docs/how-it-works.md) describes what was added around it.

## Documentation

- [How it works](docs/how-it-works.md): the method, the final harness, what a run costs and stores
- [Tasks](docs/tasks.md): writing tasks, workspaces, grading
- [Configuration](docs/configuration.md): settings, subscriptions, models and providers
- [Command reference](docs/cli.md): every command and flag
- [Changelog](CHANGELOG.md) and [contributing](CONTRIBUTING.md)

## Citation

If you use Harness² CLI in research, cite the paper:

```bibtex
@article{xu2026harness2,
  title   = {Harness$^2$: Recursive Agent Harnessing for an Open World},
  author  = {Xu, Ruiyao and Chen, Yanfei and CuiZhu, Zhongying and Dalvi Mishra, Bhavana and Ming, Yifei and Yu, Han and Han, Rujun and Lee, Chen-Yu and Pfister, Tomas},
  journal = {arXiv preprint arXiv:2610.14224},
  year    = {2026},
  url     = {https://arxiv.org/abs/2610.14224}
}
```

## License

Apache 2.0; see [LICENSE](LICENSE). The method and the original implementation are by the
paper's authors at Google; Harness² CLI is an independent fork, not a Google product, and is
not maintained by Google. Third-party code in the benchmarks plugin keeps its upstream
licenses.

## Windows fork status

Native Windows foundation work is documented in [docs/windows.md](docs/windows.md).
This milestone covers offline compatibility contracts; full experiment lifecycle support
remains in progress.
