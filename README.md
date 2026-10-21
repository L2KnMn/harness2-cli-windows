# Harness2 CLI Windows 포크

[L2KnMn/harness2-cli-windows](https://github.com/L2KnMn/harness2-cli-windows)는
[3ae3ae/harness2-cli](https://github.com/3ae3ae/harness2-cli)를 Windows 네이티브 환경에서
안전하게 사용할 수 있도록 개선하는 독립 포크입니다. 원본 연구는
[google-research/harness2](https://github.com/google-research/harness2)입니다.
프로젝트 지침·skill·프롬프트·보조 스크립트를 실험하고 결과를 검토하는 도구가 목표이며,
모델 가중치나 사용자의 승인·보안 정책을 변경하는 도구가 아닙니다.

**현재는 Windows 오프라인 호환 기반 단계입니다. 실제 Codex 개선 실험이 완성된 버전은 아닙니다.**
아래 한국어 안내가 이 포크의 현재 지원 범위입니다. 뒤의 upstream 범용 사용법은 출처와
설계 참고를 위해 보존했으며, Windows에서 그대로 실행할 수 있다는 뜻은 아닙니다.

- [현재 지원과 검증 결과](#현재-지원과-검증-결과)
- [이 포크 설치](#이-포크-설치)
- [프로젝트와 과제 준비](#프로젝트와-과제-준비)
- [인증 없는 계획 미리보기](#인증-없는-계획-미리보기)
- [조회와 결과 검토](#조회와-결과-검토)
- [오프라인 테스트](#오프라인-테스트)
- [현재 제한과 다음 단계](#현재-제한과-다음-단계)
- [Upstream 참고 문서](#upstream-참고-문서)

## 현재 지원과 검증 결과

| 범위 | 현재 상태 |
| --- | --- |
| 프로세스 생존 조회 | Windows 신호 전송 없이 조회; 접근 거부는 보수적으로 처리 |
| 파일·경로 기반 | 프로세스 간 잠금, `/` 상대경로, 한글·공백 경로, 예약명·junction 검사 |
| 실행 인자 | 명시적 argv 배열, UTF-8 입출력, Codex 승인·sandbox 우회 옵션 제거 |
| 프로젝트 준비·조회 | init, task/config, 기존 run 조회, 조건을 갖춘 dry-run |
| 실제 모델 실험 | Windows live run/eval/judge/chat/doctor --live 차단 유지 |
| Linux/macOS | upstream 코드와 CI 유지; 이 포크의 전체 지원 검증 완료로 표시하지 않음 |

2026-10-21, **Python 3.12.6과 동일한 테스트 85개**를 비교했습니다.
로컬 Windows 11은 **79 pass / 6 skip**, GitHub Windows Server 2022 VM은
**80 pass / 5 skip**이며 양쪽 모두 실패·오류 0입니다. 차이는 로컬에서 생성 시 접근 거부가 발생해
skip된 실제 junction 테스트 1개입니다. 이 수치는 전체 제품·실모델·설치 검증 결과가 아닙니다.
[실행 로그·커밋·상세 결과](docs/validation/windows-offline-comparison.md),
[지원 계약](docs/windows.md)을 확인하세요.

## 이 포크 설치

Python 3.12 또는 3.13과 Git이 필요합니다. 현재 위 85개 공통 검증 기준은 3.12.6입니다.
아래는 사용자가 선택해 수행하는 **포크 소스 설치 절차**이며 이번 오프라인 검증에서
패키지 설치 자체를 검증한 것은 아닙니다. PowerShell에서 실행합니다.

```powershell
git clone https://github.com/L2KnMn/harness2-cli-windows.git
Set-Location harness2-cli-windows
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\harness2.exe --help

$python = (Resolve-Path .\.venv\Scripts\python.exe).Path
$harness2 = (Resolve-Path .\.venv\Scripts\harness2.exe).Path
```

venv를 활성화하거나 PowerShell 실행 정책을 바꿀 필요는 없습니다. 배포 이름은 upstream과
같은 `harness2-cli`, 명령은 `harness2`입니다. 단순히 `pip install harness2-cli`를 실행하거나
아래 upstream 설치 URL을 사용하면 **이 포크가 아닌 원본 배포**를 설치할 수 있습니다.
소스에서 일반 CLI를 실행할 때도 패키지 메타데이터가 필요합니다.

Codex CLI와 모델 인증은 향후 실제 모델 실험을 위한 별도 요구사항입니다. 아래 오프라인
테스트와 테스트 전용 미리보기를 위해 Codex를 설치하거나 로그인·키를 설정하지 마세요.
실모델 설정·실행은 현재 Windows 지원 범위가 아닙니다.

## 프로젝트와 과제 준비

먼저 기존 개발 저장소와 분리된 연습 디렉터리에서 시작하세요. 다음 명령은 그 디렉터리의
`.harness2/`만 준비합니다. 기존 설정이 있으면 중단하며 `--force`를 권하지 않습니다.
`HARNESS2_*` 환경변수나 profile 덮어쓰기가 없는 셸에서 진행하고, 과제 생성 전 경로가
아래 프로젝트 상대경로로 해석되는지 `config show --origin`에서 확인하세요.

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

`--auth api-key`는 여기서 설정 형식만 선택하며 키를 저장하거나 로그인하지 않습니다.
`init`은 발견한 Claude/Codex CLI의 `--version`을 조회할 수 있습니다. 기본 login 방식을
선택하면 인증 상태 조회도 수행합니다. 위 예제는 새 인증을 요구하지 않으며, 키가 없다는
안내는 이후의 테스트 전용 설정으로 대체하기 전까지 예상되는 안내입니다.

다음 파일을 **UTF-8, BOM 없이** 저장합니다. 생성된 `task.md`의 `TODO:` 문구를 반드시 교체하세요.

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

`files/input.txt`에는 `안녕하세요`처럼 비교할 텍스트를 넣습니다. `files/`의 내용은 임시
작업공간 루트로 복사되므로 과제와 검사에서는 `files/input.txt`가 아닌 `input.txt`를 참조합니다.

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

`check`는 argv 배열이 아닌 **셸 명령 문자열**입니다. 향후 평가 시 새 작업공간에서 실행되며,
Windows의 기본 셸을 PowerShell로 가정하면 안 됩니다. 신뢰하는 검사만 작성하세요.
마지막 JSON 줄은 부분 점수를, 종료 코드 0은 성공 여부를 표현합니다. 현재 Windows의
`eval`·`judge`는 차단되어 있으며, dry-run은 이 검사도 실행하지 않습니다.

저장소 수정 과제는 `workspace = "project"`, `deliverable = "diff"`를 사용합니다.
Git 저장소의 유효한 커밋이 필요하고, `ref`에 고정한 커밋에서 격리 worktree를 만듭니다.
미커밋 변경은 자동 포함되지 않습니다. [과제 문서](docs/tasks.md)를 함께 참고하세요.

## 인증 없는 계획 미리보기

일반 `run --dry-run`도 실행파일·provider 사전 점검을 수행하므로 기존 실모델 설정에서는
CLI 또는 인증 상태 조회가 발생할 수 있습니다. **인증 없이 준비한 과제와 예상 호출 수만
확인하려면**, 위 연습 디렉터리의 생성된 `.harness2/config.toml`을 아래 테스트 설정으로 바꿉니다.
실행파일 자리는 Python으로, provider는 연결하지 않는 loopback 주소로 지정합니다.
모델 CLI·서버·키는 필요하지 않으며 실제 실험 설정으로 사용하면 안 됩니다.
`HARNESS2_*` 환경변수·profile·추가 `-c` 덮어쓰기가 없는 셸을 사용하세요. 설정 우선순위는
기본값 → 전역 config → 프로젝트 config → 환경변수 → CLI입니다. 마지막 `config show --origin`에서
suite가 tasks이고 모든 모델 역할이 preview provider인지 확인한 뒤 미리보기를 진행하세요.

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

이 미리보기는 모델·검사·네트워크를 실행하지 않고, 새 `run.json`도 만들지 않습니다.
따라서 `runs ls`가 비어 있고 `status preview`가 실행 없음 오류를 내는 것이 정상입니다.
이미 실제 설정을 가진 프로젝트의 config를 이 예제로 덮어쓰지 마세요.

실제 Codex 경로를 나중에 설정할 때 Windows 문자열은 실행파일 **한 개**를 뜻합니다.
추가 인자는 `bin = ['C:\도구\codex.exe', '인자']`처럼 argv 배열로 지정합니다.
직접 `.cmd`·`.bat`·`.ps1`·`.py` shim 실행은 거부됩니다. 설정 예시가 실모델 실행 허가는 아닙니다.

## 조회와 결과 검토

기존에 저장된 run이 있을 때만 다음 명령을 사용합니다. `saved-run`은 실제 이름으로 바꾸세요.

```powershell
& $harness2 -C $project --json runs ls
& $harness2 -C $project --json runs show saved-run
& $harness2 -C $project --json status saved-run
& $harness2 -C $project --json diff saved-run --stat
```

개선 결과는 원래 harness와의 diff로 검토합니다. `eval`은 baseline/candidate를 같은 과제로
비교하는 단계이고, `apply --dry-run`은 적용 계획을 보는 단계입니다. 실제 `apply`는 프로젝트
파일을 수정하므로 자동 실행하지 말고, 별도 검토 checkout과 사용자 변경을 보존한 상태에서
구체적인 diff를 승인한 뒤 수행해야 합니다. 현재 Windows의 전체 평가·적용 경로는 검증 완료가
아니며, 저장된 결과가 없으면 diff나 적용 계획도 만들 수 없습니다.

바깥 Codex가 이 CLI를 도구처럼 호출하는 것과 CLI 내부의 별도 `codex exec`는 다릅니다.
향후 실험은 별도 프로세스의 사용량·시간·권한을 관리해야 합니다. 기존 resume은 완료 단계를
재사용하는 기능이며 중단된 Codex 대화 자체를 이어 주는 보장은 아닙니다.

## 오프라인 테스트

포크 저장소 루트에서 다음 명령을 실행합니다. 설치된 Python만 사용하며 프로젝트 설치나
Codex·키·로그인이 필요하지 않습니다. 임시 메타데이터와 작업폴더는 테스트용으로 격리합니다.

```powershell
py -3.12 -X utf8 -B scripts/run_windows_offline.py --output .test-temp/windows-offline
```

기본 74개와 Demo fixture 기반 회귀 11개를 별도 프로세스로 실행하고 JSON·로그를 남깁니다.
어느 그룹이든 실패하면 최종 종료 코드가 0이 아닙니다. 전체 원본 테스트가 아닌 명시한 85개
범위이며, 생성할 수 없는 실제 junction과 POSIX 전용 제어는 skip 사유에 표시됩니다.

## 현재 제한과 다음 단계

- Windows live `run`, `eval`, `judge`, `chat`, `doctor --live`, live stop/detach와
  범용 POSIX 셸 executor는 차단되어 있습니다. 문서 때문에 차단을 해제하지 않습니다.
- 기존 budget 코드는 동시 호출 예약이 없어 제한 3회가 4회가 될 수 있습니다. 기존 병렬
  context 디렉터리 생성도 접근 오류 시 fallback하여 총 30회가 29회가 되는 사례가 있습니다.
  두 원인은 원본 커밋에서도 재현했고 **아직 수정하지 않았습니다**. 단일 성공 테스트가 안정성을
  입증하지 않습니다. Codex 비용 `0.0`도 무료 사용을 뜻하지 않으며 USD 한도를 엄격한 상한으로
  신뢰하면 안 됩니다.
- 프로세스 소유권·stop/resume·시간 제한, 비용·평가 집계, CRLF/binary patch 보존,
  사용자 변경을 보존하는 적용 트랜잭션을 후속 검증해야 합니다.
- Linux 전체 지원도 이번 결과로 보증하지 않습니다. 일반 CLI·benchmark plugin의 범용 기능은
  아래 upstream 참고 내용이며 Windows 지원 상태와 구분합니다.

## Upstream 참고 문서

아래 소개·원본 설치 URL·범용 실행 예시·CI 배지는 **3ae3ae/harness2-cli의 참고 문서**입니다.
이 포크의 현재 Windows 사용법은 위 안내를 따르세요. 출처·논문·라이선스와 기존 유용한 설명은
보존합니다. 특히 아래의 실모델 run/login/detach/eval 예시는 현재 Windows 지원 명령이 아닙니다.

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
