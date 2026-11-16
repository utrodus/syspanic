# AGENTS.md — SysPanic Working Rules

**Status:** Approved source of truth · 2026-11-16

SysPanic turns Linux journal and crash evidence into a deterministic, evidence-cited diagnostic report. **Don't panic. Diagnose.** These rules apply to every human or automated contributor.

## 1. Source of truth

Read the relevant documents before coding:

1. [docs/02-architecture.md](docs/02-architecture.md) — modules, contracts, security boundary
2. [docs/04-diagnostics.md](docs/04-diagnostics.md) — evidence model, rule catalog, wording
3. [docs/01-prd.md](docs/01-prd.md) — scope and acceptance criteria
4. [docs/03-ui-ux.md](docs/03-ui-ux.md) — pages, states, copy
5. [docs/05-implementation-plan.md](docs/05-implementation-plan.md) — milestones, tests, QA

Operational context (subordinate to the SoT): [Memory.md](Memory.md) holds working context and the current handoff; [docs/implementation-tracker.md](docs/implementation-tracker.md) is the authoritative record of actual task progress and verification. Neither can override approved requirements.

**Precedence:** explicit user instruction → Source of Truth documents → this file → defaults. The six documents are **Approved source of truth** (2026-11-16); do not implement against an unapproved change to them. Never silently change an approved product or technical decision. If a requirement contradicts the documents or the code — or the repository, tracker, and approved SoT disagree — stop and report the discrepancy with evidence and options before implementing conflicting work.

## 2. Workflow

- Work on **one milestone at a time**, in the order defined in the implementation plan.
- Use the stable task IDs (`T-001`…`T-026`). Do not reorder or rename them without approval.
- Mark a task complete only when its acceptance criteria and tests pass.
- Keep changes inside the active milestone. No opportunistic refactors, no future-proofing, no unrequested features.
- Prefer KISS. Standard library first, Qt Widgets only, small pure functions, no new abstractions unless a second concrete use exists.
- Add no runtime dependency without approval. Dev tools: pytest and ruff only. No GPL-only dependencies. Keep the project MIT.
- Keep the diagnostic engine free of Qt imports; Qt belongs in `ui/` only.
- **Conventional Commits always.** Every commit message follows [Conventional Commits](https://www.conventionalcommits.org): a type prefix (`feat:`, `fix:`, `docs:`, `test:`, `build:`, `chore:`, `refactor:`, `perf:`, `ci:`), optional scope, imperative concise subject (≤72 chars), and an optional body explaining *why*. No free-form commit messages.
- **Repository writes require a user command.** Never commit, push, tag, or release without an explicit user instruction/approval. Local file edits, lint, and tests are free; saving to the repository is gated. Keep `.venv/`, tool caches, build artifacts, and any real logs/dumps/screenshots out of commits (maintain `.gitignore`).
- **After each manual QA PASS:** immediately prepare a commit-and-push plan — logically grouped ("pilah") conventional commits, the exact message for each, the files per commit, and the push target (remote/branch). Present the plan to the user and request approval. Execute `git commit` and `git push` only after the user approves; never push silently. If QA fails, do not commit/push.

### Session bootstrap

At the beginning of a coding session or milestone:

1. Read this file (AGENTS.md).
2. Read [Memory.md](Memory.md) for current context and handoff.
3. Read [docs/implementation-tracker.md](docs/implementation-tracker.md) for actual progress and the next task.
4. Read the relevant approved SoT sections and the implementation-plan acceptance criteria.
5. Inspect the working tree and relevant code before changing anything.

Never assume Memory.md or the tracker is more authoritative than approved requirements. Resolve any repository/tracker/SoT discrepancy before implementing conflicting work.

### Task lifecycle

Before implementing a task: confirm it is within the authorized milestone, confirm its dependencies and acceptance criteria, and mark it `IN_PROGRESS` in the tracker.

After implementing a task: run the relevant automated checks; record actual results in the tracker; mark it `IMPLEMENTED_UNVERIFIED` only after its required automated checks pass; record blockers or deviations honestly; never promote it to `VERIFIED` automatically.

At the end of a milestone: update the tracker with the milestone result and verification evidence; update Memory.md with durable learnings, unresolved issues, and the next handoff; provide concise manual QA steps in the response; stop at the authorized milestone boundary.

After the user reports manual QA: record the actual `PASS`/`FAIL`/`BLOCKED` results; promote to `VERIFIED` only when the user explicitly confirms the required QA passed; if QA fails, record the failure and do not proceed past an unmet milestone gate.

### Milestone verification gates

- M0 requires the user's manual GUI QA before M1 may start.
- Later milestones without integrated GUI functionality may hand off on passing automated acceptance criteria; GUI-dependent manual QA may remain pending until M8/M9.
- Always obtain explicit user authorization before starting the next milestone. Never bypass an applicable verification gate.

### Context and token efficiency

- Read Memory.md and the tracker first to recover context; read relevant SoT sections instead of reloading unrelated documents for every task.
- Do not skip an applicable requirement to save tokens.
- Keep Memory.md and tracker updates concise; avoid duplicate planning, handoff, or status documents.
- Never transfer real system logs or crash dumps into agent context.

## 3. Security non-negotiables

- Never run the GUI as root, never invoke `sudo`, never request elevation, never modify journal configuration, groups, permissions, or system settings.
- Subprocesses: argv arrays, `shell=False`, explicit timeouts, bounded output, cancellation support. Fixed commands only.
- Read only the allowlisted paths in [docs/02-architecture.md](docs/02-architecture.md) §10. Artifact scans use `os.scandir(path)` plus `is_file/is_dir(follow_symlinks=False)`: `/var/crash` root plus immediate kdump incident subdirectories only (bounded), pstore depth 1, no deeper recursion. Trusted fixed system paths (for example `/etc/os-release`, `/sys/kernel/kexec_crash_loaded`) may be symlinks; artifact-derived paths may not. Never follow artifact symlinks.
- Never open binary `vmcore` or any crash dump; metadata only. Text artifacts are capped. Never collect `/proc/cmdline`.
- Never read DMI serials, product UUIDs, chassis serials, or `/etc/machine-id`.
- No network, telemetry, cloud, AI APIs, or external uploads. No temp files, no log persistence. The single persistence exception is the local appearance preference (`appearance/theme` = `light`/`dark` via QSettings, organization/application `SysPanic`); never store diagnostic data, journal content, artifacts, or identifiers there. Demo mode and automated tests use session-only or isolated stores and never write real user preferences. Never transmit real host logs, crash dumps, or screenshots to coding agents, AI services, or external tools. Automated verification uses synthetic fixtures only.
- Treat log content as untrusted: plain-text widgets, no HTML/rich text, strip control characters, fence Markdown excerpts.
- Sanitize before preview/export, and require preview. Reports never contain hostname, username, home path, IP, MAC, email, serial, UUID, or machine ID. Credential/token/connection-string redaction is best-effort (`CRED_n`) and must be described honestly. Boot IDs are retained by design and stated in the report.
- Never commit real logs, crash dumps, screenshots with identifiers, serials, hostnames, or user data. Demo fixtures must be synthetic and sanitized.
- Collection runs off the UI thread and remains cancellable. Never call `QThread.terminate()` or destroy a running thread; if cancellation has not completed, keep the window open.

## 4. Diagnostic accuracy

- Every finding cites real evidence; no evidence → no finding.
- Separate observed fact, suspected cause, and unknown. No confidence percentages or scores.
- Never call a component defective, broken, or faulty based on logs. Never infer PSU/power-supply failure.
- Missing shutdown markers alone do not prove power loss; list alternatives (hard reset, hang, watchdog, firmware reset, journal flush loss). `Journal stopped` alone does not prove a clean system shutdown.
- Missing or unreadable logs are **not** evidence of health. Surface coverage and say what could not be assessed.
- Absence-based findings only for completed, non-current boots with both journal tails reliably collected; suppress SHD-002 when tail coverage is uncertain. Head truncation is not tail loss.
- Kernel-only signatures require `_TRANSPORT=kernel` journal metadata; `SYSLOG_IDENTIFIER=kernel` alone is spoofable and untrusted. User-space lookalikes and spoofed identifiers are ignored (negative tests required). systemd shutdown markers use trusted process/unit metadata. GPU timeouts and reset attempts are separate findings. MCE/EDAC classification is line-scoped; unknown correctability stays unknown. `PCIe Bus Error` alone is not a link reset. Taint `G` is the untainted proprietary-slot placeholder, not an adverse flag.
- Crash artifacts carry `matched` / `possibly_related` / `unknown` boot association; `matched` requires proven boot identity — mtime or timestamp + kernel release alone never matches; only matched artifacts corroborate. Never imply an unverified dump belongs to the selected incident.
- `dmesg` is collected and analyzed only for the current boot; historical boots mark it `unsupported` with an explanation. Never mix current-boot kernel evidence into historical incidents.
- Current inventory/sensors are "collected now", never crash-time measurements.
- No rule may use wall-clock time, randomness, locale-dependent formatting, or network data.
- Wording follows [docs/04-diagnostics.md](docs/04-diagnostics.md) §10. Banned in user-facing strings: `defective`, `broken`, `faulty`, `hardware failure`, `PSU failure`, `power supply failure`, `confirmed cause`, `100%`, `guaranteed`, `must replace`, `certainly`.
- New rules follow the authoring checklist and include positive, negative, missing/truncated-source, and tail-unreliable tests. The catalog has 29 IDs; the v0.1.0 release-blocking core is 27, with ART-002/ART-003 classification deferred and tracked.

## 5. Verification

Run from the repository root:

```bash
.venv/bin/ruff check .
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/pytest -q
# User-only manual GUI; never run this in agent verification:
PYTHONPATH=src .venv/bin/python -m syspanic --demo
```

- Run the tests relevant to the milestone after each task, and the full suite before reporting.
- Agent verification must use non-interactive offscreen smoke tests (`QT_QPA_PLATFORM=offscreen`) and logic tests. Do not launch the real GUI or automate desktop interaction; real GUI execution is manual by the user.
- Do not add pytest-qt.
- GUI correctness is verified by the manual QA script in [docs/05-implementation-plan.md](docs/05-implementation-plan.md) §4.
- Never use real host logs, crash dumps, or screenshots as test input or in agent prompts; use synthetic fixtures.
- If a command cannot run in the environment, report it with the exact error and the fallback used (`PYTHONPATH` run, offscreen platform).

## 6. Status and reporting

- After implementation and automated checks, mark the work `IMPLEMENTED_UNVERIFIED`.
- Only the user promotes it to `VERIFIED` after manual GUI QA.
- Final report for a milestone: status, files changed, commands run with results, deviations, and the manual GUI QA steps the user must perform.
- Never claim GUI success without manual verification; state explicitly when only code-level checks were run.

## 7. Blockers

Report blockers immediately in this format:

1. **What is blocked** (task ID and requirement)
2. **Evidence** (file/line, command output, document contradiction)
3. **Options** (2–3 concrete choices with trade-offs)
4. **Recommendation** (one, with rationale)

Do not work around a blocked security or accuracy requirement. Do not guess at product intent; ask.

## 8. Scope guardrails

Out of scope for v0.1.0: real-time/background monitoring, stress testing, automatic repair or kdump setup, binary vmcore parsing, AI/cloud, authentication, telemetry, database, plugin architecture, microservices, `.desktop`/packaging, localization, live sensors, QML/WebEngine. Propose changes to scope; do not implement them unasked.

## 9. Quick file map

```
docs/01-prd.md .. 05-implementation-plan.md   Source of truth
docs/implementation-tracker.md   actual task progress and verification record
Memory.md                   working memory and handoff (subordinate to SoT)
src/syspanic/domain/        models and enums (no Qt)
src/syspanic/collectors/    journal, system, artifacts, runner, orchestrator
src/syspanic/diagnostics/   registry, engine, rules, timeline, coverage
src/syspanic/report/        sanitizer and Markdown renderer
src/syspanic/ui/            Qt Widgets only; controller + pages + widgets
src/syspanic/demo_data/     synthetic fixtures shared by demo and tests
tests/                      pytest unit, integration, offscreen smoke
```
