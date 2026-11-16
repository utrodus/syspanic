# Contributing to SysPanic

Thanks for your interest in improving SysPanic. This guide is for developers and contributors.
For a product overview and how to run the app, see the [README](README.md).

SysPanic is a focused, one-day-MVP desktop tool. The working rules in [AGENTS.md](AGENTS.md)
apply to every human or automated contributor; this guide summarizes them and points to the
approved Source of Truth (SoT) for detail.

## Scope and ground rules

- **KISS.** Standard library first, small pure functions, no new abstractions unless a second
  concrete use exists. No opportunistic refactors, no future-proofing, no unrequested features.
- **Qt Widgets only** (`QtCore`, `QtGui`, `QtWidgets`). No QML, WebEngine, chart library,
  external icon pack, or third-party UI kit. Icons are local QPainter outlines — never emoji,
  never remote assets.
- **MIT project.** No GPL-only dependencies. **No new runtime dependency without approval.**
  Dev tools are **pytest and ruff only**. **Do not add pytest-qt.**
- Keep changes inside the active milestone. Propose scope changes; do not implement them unasked.

## Source of Truth and precedence

Read the relevant documents before coding:

1. [docs/02-architecture.md](docs/02-architecture.md) — modules, contracts, security boundary
2. [docs/04-diagnostics.md](docs/04-diagnostics.md) — evidence model, rule catalog, wording
3. [docs/01-prd.md](docs/01-prd.md) — scope and acceptance criteria
4. [docs/03-ui-ux.md](docs/03-ui-ux.md) — pages, states, copy
5. [docs/05-implementation-plan.md](docs/05-implementation-plan.md) — milestones, tests, QA

**Precedence:** explicit maintainer instruction → SoT documents → [AGENTS.md](AGENTS.md) →
defaults. The six SoT documents are approved (2026-11-16). Never silently change an approved
product or technical decision. If a requirement contradicts the documents or the code — or the
repository, [tracker](docs/implementation-tracker.md), and SoT disagree — stop and report the
discrepancy with evidence and options before implementing conflicting work.

[Memory.md](Memory.md) and the tracker are operational context, subordinate to the SoT; they
record reality, not intent, and cannot override approved requirements.

## Environment setup

Python ≥ 3.12 (verified on 3.14.10). From the repository root:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`requirements.txt` pins the complete dev environment (including pytest transitives) for
reproducibility. Optional editable install when network is available:

```bash
.venv/bin/pip install -e ".[dev]"
```

The build backend is hatchling. If it cannot be downloaded, keep the `PYTHONPATH=src` source-run
commands below and record the deviation; do not add alternatives that expand scope.

## Repository layout

**Present today (M0 shell + M1 domain):**

```
src/syspanic/
  __init__.py            __version__ = "0.1.0"
  __main__.py            module entry point
  app.py                 argparse (--demo, --version), QApplication, theme, MainWindow
  constants.py           app metadata, window/nav sizing, page names
  domain/
    enums.py             Severity, EvidenceStrength, SourceState, TimelineKind, ArtifactAssociation
    models.py            frozen dataclasses (docs/02 §5) + validate_report()
  ui/
    main_window.py       sidebar, nav, QStackedWidget, footer, shortcuts, close handling
    theme.py             dual-theme tokens, QPalette/QSS, ThemeManager, appearance preference
    icons.py             local QPainter outline icons (24x24, DPR-aware), theme re-rendering
    pages/__init__.py    Overview + idle/empty-state pages
    widgets/__init__.py  Card, PageHeader, EmptyState, ThemeSwitch, capability_card, section_title
tests/                   conftest, test_args, test_smoke_import, test_smoke_gui,
                         test_icons, test_theme, test_e2e_m0, test_models
docs/                    approved SoT + implementation tracker
AGENTS.md  Memory.md  pyproject.toml  requirements.txt  LICENSE  README.md
```

**Planned (M2–M7, not yet created):** `collectors/`, `diagnostics/`, `report/`,
`demo_data/`, and the Qt-facing `ui/controller.py` / `ui/worker.py`. The target module map is in
[architecture §3](docs/02-architecture.md) and [AGENTS.md §9](AGENTS.md). Do not document planned
modules as if they already exist.

## Architecture rules

- **The diagnostic engine stays Qt-free.** `domain/`, `collectors/`, `diagnostics/`, and
  `report/` must not import Qt; Qt belongs in `ui/` only. `ui/` must not call subprocesses or
  parse logs directly.
- **Subprocess safety.** argv arrays, `shell=False`, explicit timeouts, bounded output,
  cancellation support, fixed commands only (`journalctl`, `lspci`, `dmesg --time-format iso`).
  No temp files, no writes, no network.
- **Allowlisted reads only** ([architecture §10](docs/02-architecture.md)). Artifact scans use
  `os.scandir(path)` plus `entry.is_file/is_dir(follow_symlinks=False)`: `/var/crash` root plus
  immediate kdump incident subdirectories only (bounded), pstore depth 1, no deeper recursion.
  Trusted fixed system paths may be symlinks; artifact-derived paths may not. **Never follow
  artifact symlinks.**
- **Never open binary `vmcore`** or any crash dump — metadata only. Text artifacts are capped.
  **Never collect `/proc/cmdline`. Never read DMI serials, product UUIDs, chassis serials, or
  `/etc/machine-id`.**
- **Log content is untrusted.** Plain-text widgets, no HTML/rich text, strip control characters,
  fence Markdown excerpts. Sanitize before preview/export and require preview.
- **Threading.** Collection runs off the UI thread and remains cancellable. Never call
  `QThread.terminate()` or destroy a running thread; if cancellation has not completed, keep the
  window open.

## Workflow and milestone gates

- Work on **one milestone at a time**, in the order defined in the
  [implementation plan](docs/05-implementation-plan.md).
- Use the stable task IDs (`T-001`…`T-026`). Do not reorder or rename them without approval.
- Before implementing: confirm the task is within the authorized milestone, confirm dependencies
  and acceptance criteria, and mark it `IN_PROGRESS` in the
  [tracker](docs/implementation-tracker.md).
- Mark a task complete only when its acceptance criteria and tests pass. Record actual results;
  after required automated checks pass, mark it `IMPLEMENTED_UNVERIFIED`. Record blockers or
  deviations honestly. **Never promote to `VERIFIED` automatically** — only the maintainer does
  that after manual GUI QA.
- **Explicit maintainer authorization is required before starting each next milestone.** M0
  requires the user's manual GUI QA before M1 may start. Never bypass an applicable gate.
- At the end of a milestone: update the tracker with the result and verification evidence, update
  [Memory.md](Memory.md) with durable learnings and the next handoff, provide concise manual QA
  steps, and stop at the authorized boundary.

## Verification

Run from the repository root:

```bash
.venv/bin/ruff check .
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/pytest -q
```

- Run the tests relevant to the milestone after each task, and the full suite before reporting.
- **Automated GUI checks are offscreen only** (`QT_QPA_PLATFORM=offscreen`). Do not launch the
  real GUI or automate desktop interaction; real GUI execution is **manual, by the maintainer**
  ([QA script, plan §4](docs/05-implementation-plan.md)). Do not add pytest-qt.
- **Tests use synthetic fixtures only** — generated text, `tmp_path`, or the packaged demo data.
  Never use real host logs, crash dumps, or screenshots as test input or in agent prompts, and
  never transmit them to coding agents, AI services, or external tools.
- New rules follow the authoring checklist and include positive, negative, missing/truncated-
  source, and tail-unreliable tests.
- If a command cannot run in the environment, report it with the exact error and the fallback
  used (`PYTHONPATH` run, offscreen platform).

## Diagnostic accuracy

Full contract: [docs/04-diagnostics.md](docs/04-diagnostics.md). Key rules:

- Every finding cites real evidence; **no evidence → no finding**. Separate observed fact,
  suspected cause, and unknown. No confidence percentages or scores.
- Never call a component defective, broken, or faulty based on logs. **Never infer PSU/power-
  supply failure.** Missing shutdown markers alone do not prove power loss; list alternatives
  (hard reset, hang, watchdog, firmware reset, journal flush loss). `Journal stopped` alone does
  not prove a clean system shutdown.
- Missing or unreadable logs are **not** evidence of health. Surface coverage and say what could
  not be assessed.
- Absence-based findings only for completed, non-current boots with both journal tails reliably
  collected; suppress SHD-002 when tail coverage is uncertain. Head truncation is not tail loss.
- Kernel-only signatures require `_TRANSPORT=kernel` journal metadata; `SYSLOG_IDENTIFIER=kernel`
  alone is spoofable and untrusted. systemd shutdown markers use trusted process/unit metadata.
  GPU timeouts and reset attempts are separate findings. MCE/EDAC classification is line-scoped;
  unknown correctability stays unknown. `PCIe Bus Error` alone is not a link reset. Taint `G` is
  the untainted proprietary-slot placeholder, not an adverse flag.
- Crash artifacts carry `matched` / `possibly_related` / `unknown` boot association; `matched`
  requires proven boot identity — mtime or timestamp + kernel release alone never matches; only
  matched artifacts corroborate.
- `dmesg` is collected and analyzed only for the current boot; historical boots mark it
  `unsupported`. Never mix current-boot kernel evidence into historical incidents.
- Current inventory/sensors are "collected now", never crash-time measurements.
- No rule may use wall-clock time, randomness, locale-dependent formatting, or network data.
- The catalog has 29 IDs; the v0.1.0 release-blocking core is 27, with ART-002/ART-003
  classification deferred and tracked.

**Banned in user-facing strings:** `defective`, `broken`, `faulty`, `hardware failure`,
`PSU failure`, `power supply failure`, `confirmed cause`, `100%`, `guaranteed`, `must replace`,
`certainly`. Wording follows [diagnostics §10](docs/04-diagnostics.md).

## Commits and repository writes

- **Conventional Commits always.** Every commit message follows
  [Conventional Commits](https://www.conventionalcommits.org): a type prefix (`feat:`, `fix:`,
  `docs:`, `test:`, `build:`, `chore:`, `refactor:`, `perf:`, `ci:`), optional scope, imperative
  concise subject (≤72 chars), and an optional body explaining *why*. No free-form messages.
- **Repository writes require an explicit maintainer command.** Never commit, push, tag, or
  release without approval. Local file edits, lint, and tests are free; saving to the repository
  is gated.
- **After each manual QA PASS:** prepare a logically grouped commit-and-push plan — the exact
  message for each commit, the files per commit, and the push target (remote/branch) — present it,
  and request approval. Execute `git commit` and `git push` only after approval; never push
  silently. If QA fails, do not commit/push.
- Keep `.venv/`, tool caches, build artifacts, and any real logs/dumps/screenshots out of commits
  (maintain [.gitignore](.gitignore)). Never commit real logs, crash dumps, screenshots with
  identifiers, serials, hostnames, or user data. Demo fixtures must be synthetic and sanitized.

## Status protocol and reporting

| Status | Meaning |
|---|---|
| `PLANNED` | In the plan, not started |
| `IN_PROGRESS` | Active milestone only |
| `IMPLEMENTED_UNVERIFIED` | Code and automated checks done; manual GUI QA pending |
| `VERIFIED` | Maintainer completed the manual QA script |
| `BLOCKED` | A contradiction, permission issue, or missing dependency prevents progress |

A milestone report includes: status, files changed, commands run with results, deviations, and
the manual GUI QA steps the maintainer must perform. Never claim GUI success without manual
verification; state explicitly when only code-level checks were run.

Report blockers immediately as: **what is blocked** (task ID + requirement), **evidence**
(file/line, command output, document contradiction), **options** (2–3 concrete choices with
trade-offs), and a **recommendation**. Do not work around a blocked security or accuracy
requirement; do not guess at product intent — ask.

## Where to start

M0 is `VERIFIED` (dual-theme visual QA PASS 2026-11-16). **M1 / T-003** (domain models +
`validate_report()`) is implemented with automated checks passing (139/139 offscreen tests;
manual QA not applicable — pure logic). The next task is **M2 / T-004** (safe bounded command
runner), which awaits explicit maintainer authorization. See the
[tracker](docs/implementation-tracker.md) and [plan §2](docs/05-implementation-plan.md).

## License

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).