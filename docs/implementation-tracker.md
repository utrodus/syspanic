# SysPanic — Implementation Tracker

Authoritative operational record of **actual** implementation progress. Not a requirements document:
scope, dependencies, and acceptance criteria remain owned by [05-implementation-plan.md](05-implementation-plan.md)
and the approved Source of Truth. Working context: [../Memory.md](../Memory.md).
Last updated: 2026-11-16 (M3 IMPLEMENTED_UNVERIFIED — automated PASS 219/219; M2 pushed `2501d26`; M0 VERIFIED).

## 1. Project status summary

- **Phase:** Implementation — M0 `VERIFIED` (dual-theme automated + visual QA PASS, pushed). M1 implemented and pushed (`eedff6d`…`a0b475a`): T-003 `IMPLEMENTED_UNVERIFIED` (automated PASS; manual QA NOT_APPLICABLE — pure logic, no GUI). M2 implemented and pushed (`56d3129`…`2501d26`): T-004 `IMPLEMENTED_UNVERIFIED` (automated PASS; pure logic, manual QA N/A). M3 implemented: T-005/T-006 `IMPLEMENTED_UNVERIFIED` (automated PASS 2026-11-16; no GUI surface). M4 awaiting authorization.
- **SoT status:** all six documents `Approved source of truth · 2026-11-16`; docs/03 carries the "Modern Diagnostic Workstation" visual revision + final polish + the approved dual-theme revision (Dark + Soft Light, §2/§2.1); docs/02 D-14 records the decision; three final accuracy corrections still in force.
- **Tasks:** 6 of 26 implemented · 2 of 26 VERIFIED (T-001, T-002). **Milestones:** 4 of 10 implemented · 1 of 10 VERIFIED (M0).
- **Repository state (verified 2026-11-16):** all prior M0 work is committed (`23d0f92` docs/CONTRIBUTING … `003c4db` scaffold; earlier tracker note "only LICENSE committed" was stale and is corrected here). The dual-theme refinement (17 modified files + new `tests/test_theme.py`) was committed 2026-11-16 via the maintainer-approved 4-commit plan (SoT docs → feat → test → status docs) with push target `origin/main` (pushed, fast-forward `23d0f92..048e126`). M1 was committed 2026-11-16 via the approved 3-commit plan and pushed (fast-forward `048e126..a0b475a`). M2 was committed 2026-11-16 via the approved 3-commit plan and pushed (fast-forward `a0b475a..2501d26`). M3 changes are uncommitted.

## 2. Current active milestone and task

- **Last completed task:** T-006 (M3) — journal collector per docs/02 §8. Status `IMPLEMENTED_UNVERIFIED` (automated PASS 2026-11-16, TDD RED→GREEN). T-005 likewise. No active task.
- **Prior task:** T-004 (M2) — IMPLEMENTED_UNVERIFIED, committed `56d3129`…`2501d26` and pushed.
- **Next milestone:** M4 — System profile and crash artifacts (T-007–T-008; not authorized yet).
- **Gate:** M3 handoff on automated acceptance per plan (no GUI surface); collection-related manual QA steps (plan §4.3–8) pend to M8/M9. M4 requires explicit user authorization (offered 2026-11-16; user deferred).

## 3. Milestone progress

| Milestone | Name | Tasks | Implementation | Automated gate | Manual QA | Status |
|---|---|---|---|---|---|---|
| M0 | Runnable desktop shell | T-001–T-002 | 2/2 | PASS | functional+visual PASS (dark shell); dual-theme visual PASS 2026-11-16 | VERIFIED |
| M1 | Domain model | T-003 | 1/1 | PASS | NOT_APPLICABLE | IMPLEMENTED_UNVERIFIED |
| M2 | Safe command runner | T-004 | 1/1 | PASS | NOT_APPLICABLE | IMPLEMENTED_UNVERIFIED |
| M3 | Boots and journal | T-005–T-006 | 2/2 | PASS | NOT_RUN (GUI steps pend to M8/M9) | IMPLEMENTED_UNVERIFIED |
| M4 | System profile and crash artifacts | T-007–T-008 | 0/2 | NOT_RUN | NOT_RUN | PLANNED |
| M5 | Demo data | T-009 | 0/1 | NOT_RUN | NOT_RUN | PLANNED |
| M6 | Diagnostic engine | T-010–T-014 | 0/5 | NOT_RUN | NOT_RUN | PLANNED |
| M7 | Sanitization and report | T-015–T-016 | 0/2 | NOT_RUN | NOT_RUN | PLANNED |
| M8 | GUI integration | T-017–T-023 | 0/7 | NOT_RUN | NOT_RUN | PLANNED |
| M9 | Hardening and release candidate | T-024–T-026 | 0/3 | NOT_RUN | NOT_RUN | PLANNED |

## 4. Complete task tracker

Statuses — implementation: `PLANNED` / `IN_PROGRESS` / `IMPLEMENTED_UNVERIFIED` / `VERIFIED` / `BLOCKED`.
Automated and manual QA: `NOT_RUN` / `PASS` / `FAIL` / `BLOCKED` / `NOT_APPLICABLE` (only when a check genuinely does not apply).
"Planned tests" are from the implementation plan; they do not exist yet.

| Milestone | Task | Name | Implementation | Automated | Manual QA | Evidence / notes (planned tests) |
|---|---|---|---|---|---|---|
| M0 | T-001 | Project scaffold and entry point | VERIFIED | PASS | PASS | pyproject.toml, src/syspanic/{__init__,__main__,app,constants}.py; import/arg/E2E tests pass; user QA PASS 2026-11-16 |
| M0 | T-002 | Theme tokens, dual-theme shell, 5-page nav | VERIFIED | PASS | functional+visual PASS (dark shell); dual-theme visual PASS 2026-11-16 | ui/{theme,icons,main_window,pages,widgets}; "Modern Diagnostic Workstation" + final polish (24×24 semantic QPainter icons with DPR-after-paint fix, complete empty-state copy + shield meta, Boot session field label, footer Idle, no duplicate "Local only"); 2026-11-16 dual-theme refinement: ThemeManager (Dark default + Soft Light), shared QSS/QPalette, sidebar Light/Dark switcher (sun/moon), QSettings appearance/theme persistence with demo/test isolation, WCAG AA contrast tests; 79 offscreen tests pass (38 prior + 41 theme); dark-shell functional + visual QA PASS and dual-theme visual QA PASS 2026-11-16 |
| M1 | T-003 | Domain models and validate_report() | IMPLEMENTED_UNVERIFIED | PASS | NOT_APPLICABLE | tests/test_models.py: 60 tests (RED verified first) — enums match SoT values; 29-ID catalog; boot_id format; frozen models; tail-reliability invariant; validate_report rejects no-evidence/unknown-rule/duplicate findings, unresolvable refs, excerpt bounds, banned terms, unsorted/duplicate/over-cap timeline, duplicate coverage/evidence, demo mismatch; Qt-free check. Full suite 139/139 |
| M2 | T-004 | Safe bounded command runner | IMPLEMENTED_UNVERIFIED | PASS | NOT_APPLICABLE | tests/test_runner.py: 23 tests (RED verified first) — available/empty/not_found/permission_denied (spawn + 3 stderr hints)/error/timeout/truncated states; exact byte cap; terminate→kill within tolerance; cancel pre-spawn + mid-run; C-locale env overrides; shell-string argv rejected; large stderr no deadlock; frozen result; Qt-free + no shell=True source scan. Full suite 162/162 |
| M3 | T-005 | Boot enumeration and normalization | IMPLEMENTED_UNVERIFIED | PASS | NOT_RUN | tests/test_boots.py: 25 tests (RED verified first) — JSON array + JSON-lines fixtures, text-table fallback, dashed/undashed/uppercase normalization (canonical dashed only), invalid-ID rejection, zero previous boots, current-boot /proc verification + mismatch/unverifiable detail, journal failure → /proc fallback + coverage state, total failure → issue, parse failure → ERROR. ruff clean |
| M3 | T-006 | Journal collector, truncation/tail reliability | IMPLEMENTED_UNVERIFIED | PASS | NOT_RUN (GUI steps pend to M8/M9) | tests/test_journal_parse.py (17) + tests/test_journal.py (15), RED verified first — malformed skipped+counted; byte-array MESSAGE decoded (invalid UTF-8 replaced); ANSI/OSC/C0 stripped (\n\t kept); 1000-char cap; cursor dedupe prefers kernel; (timestamp,cursor) sort; JRN-/DMS- sequential IDs; kernel_release from Linux version; boot window derived; -n cap → head-truncated reliable tail; byte-cap/timeout/denial/error → tail unreliable; permission mapped; dmesg current-boot only (historical unsupported, never run); iso time-format fallback to plain; provenance preserved; cancel passed through; fixed undashed argv. Full suite 219/219 |
| M4 | T-007 | System profile collectors | PLANNED | NOT_RUN | NOT_RUN | test_system.py |
| M4 | T-008 | Crash artifact collector and association | PLANNED | NOT_RUN | NOT_RUN | test_artifacts.py |
| M5 | T-009 | Demo fixtures and demo collector | PLANNED | NOT_RUN | NOT_RUN | test_demo.py |
| M6 | T-010 | Rule protocol, registry, finding assembly | PLANNED | NOT_RUN | NOT_RUN | test_engine.py, test_registry.py |
| M6 | T-011 | SHD/BOT/PNC/MCE rules | PLANNED | NOT_RUN | NOT_RUN | test_rules_shutdown.py, test_rules_panic.py, test_rules_cpu_mce.py |
| M6 | T-012 | GPU/MEM/PCI/STO/THM/ART rules | PLANNED | NOT_RUN | NOT_RUN | test_rules_gpu.py, test_rules_memory.py, test_rules_pcie.py, test_rules_storage.py, test_rules_thermal.py, test_rules_artifacts.py |
| M6 | T-013 | Timeline builder | PLANNED | NOT_RUN | NOT_RUN | test_timeline.py |
| M6 | T-014 | Coverage aggregation and tail gating | PLANNED | NOT_RUN | NOT_RUN | test_coverage.py |
| M7 | T-015 | Sanitizer and token redaction | PLANNED | NOT_RUN | NOT_RUN | test_sanitize.py |
| M7 | T-016 | Markdown report renderer | PLANNED | NOT_RUN | NOT_RUN | test_markdown.py |
| M8 | T-017 | AnalysisController + CollectionWorker | PLANNED | NOT_RUN | NOT_RUN | test_controller.py (offscreen) |
| M8 | T-018 | Overview page | PLANNED | NOT_RUN | NOT_RUN | test_smoke_gui.py |
| M8 | T-019 | Timeline page | PLANNED | NOT_RUN | NOT_RUN | smoke + model test |
| M8 | T-020 | Evidence page | PLANNED | NOT_RUN | NOT_RUN | smoke |
| M8 | T-021 | System Information page | PLANNED | NOT_RUN | NOT_RUN | smoke |
| M8 | T-022 | Report page and export | PLANNED | NOT_RUN | NOT_RUN | test_report_page.py |
| M8 | T-023 | State matrix and banners | PLANNED | NOT_RUN | NOT_RUN | smoke state test |
| M9 | T-024 | End-to-end demo pipeline test | PLANNED | NOT_RUN | NOT_RUN | test_pipeline.py |
| M9 | T-025 | Quality pass, wording test, README | PLANNED | NOT_RUN | NOT_APPLICABLE | test_wording.py; ruff clean |
| M9 | T-026 | Release checklist and QA handoff | PLANNED | NOT_APPLICABLE | NOT_RUN | manual (plan: version consistency, deferred status, handoff) |

Manual QA is `NOT_APPLICABLE` only for pure logic/lint tasks with no direct step in the manual QA script
(T-003, T-004, T-025); T-026 has no automated test column in the plan. All other manual checks map to
[05-implementation-plan.md](05-implementation-plan.md) §4 and remain `NOT_RUN`.

## 5. Verification and manual QA status

- **Automated (dual-theme refinement, run 2026-11-16, repo root):**
  - `.venv/bin/ruff check .` → **All checks passed!** (after wrapping 9 long QSS lines and `--fix` for 2 trailing-newline W292 + 1 SIM300).
  - `QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/pytest -q` → **79 passed, exit 0** (38 prior M0 tests unchanged and passing + 41 new in `tests/test_theme.py`). New tests were written first and observed failing (ImportError / KeyError 'sun') before implementation. Coverage: Dark default on missing/invalid/unreadable preference; Light apply; repeated Light↔Dark switching with signal-count assertion; palette roles incl. disabled group; QSS uses only token colors (no hardcoded hex); opposite-theme colors absent; icon/nav retheme in place; navigation after switching; page/boot/placeholder state and widget identity preserved; no duplicate widgets/connections; isolated QSettings INI roundtrip + single-key assertion + corrupt-INI fallback; write-failure and unwritable-location graceful degradation; demo session-only store; WCAG AA contrast (≥4.5 text pairs, ≥3 accent/focus) for both themes; approved dark palette preserved; switcher a11y (checkable/exclusive/focus/tooltip/accessibleName), active state, click + Space-key activation, placement above privacy indicator; sun/moon glyph bounds/DPR (in `test_icons.py`); 3 theme E2E subprocess runs with private `XDG_CONFIG_HOME` (persist→restore across restart, demo never writes real prefs, missing pref starts Dark). Prior E2E helper now also isolates `XDG_CONFIG_HOME`.
  - `PYTHONPATH=src .venv/bin/python -m syspanic --version` → `SysPanic 0.1.0`.
  - Agent verification is offscreen/logic only; the real GUI was never launched or automated. Offscreen tests verify behavior and construction, not final visual appearance.
- **Automated (M1 / T-003, run 2026-11-16, repo root):**
  - `.venv/bin/ruff check .` → **All checks passed!** (after fixing UP017 `datetime.UTC` + 7 E501 wraps in the new test file).
  - `QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/pytest -q` → **139 passed, exit 0** (79 prior + 60 new in `tests/test_models.py`). RED verified first (`ModuleNotFoundError: syspanic.domain`), then GREEN. Acceptance covered: invalid findings (no evidence, unknown rule, duplicate IDs), unsorted timeline, and duplicate coverage rejected, plus refs/excerpts/banned terms/demo mismatch/evidence invariants.
  - `PYTHONPATH=src .venv/bin/python -m syspanic --version` → `SysPanic 0.1.0`.
  - No GUI surface in M1; manual QA NOT_APPLICABLE (pure logic). Domain layer verified Qt-free by source scan test.
- **Automated (M2 / T-004, run 2026-11-16, repo root):**
  - `.venv/bin/ruff check .` → **All checks passed!** (after SIM105 `contextlib.suppress` in runner + F401/E501 fixes in the new test file).
  - `QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/pytest -q` → **162 passed, exit 0** (139 prior + 23 new in `tests/test_runner.py`). RED verified first (`ModuleNotFoundError: syspanic.collectors`), then GREEN. Acceptance covered: missing binary → `not_found`; permission error → `permission_denied` (spawn PermissionError + all three stderr hints); timeout kills child quickly → `timeout`; oversized output → `truncated` with tail unreliable (exact byte cap); cancel stops child (pre-spawn + mid-run); empty stdout → `empty`. Plus env normalization, shell-string rejection, large-stderr drain, frozen result, Qt-free/no-shell source scan.
  - `PYTHONPATH=src .venv/bin/python -m syspanic --version` → `SysPanic 0.1.0`.
  - No GUI surface in M2; manual QA NOT_APPLICABLE (pure logic). Runner verified Qt-free and `shell=False` by source-scan test. Child processes are `sys.executable -c` synthetic programs only; no real host data.
- **Automated (M3 / T-005–T-006, run 2026-11-16, repo root):**
  - `.venv/bin/ruff check .` → **All checks passed!** (after canonical-dashed-only normalization fix, 2 E501 wraps in test_boots, list-key→tuple fixes in test_journal, 1 E501 wrap in journal.py).
  - `QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/pytest -q` → **219 passed, exit 0** (162 prior + 57 new: 25 test_boots, 17 test_journal_parse, 15 test_journal). RED verified first per task (`ModuleNotFoundError: syspanic.collectors.base` / `.journal`), then GREEN. T-005 acceptance: JSON array + JSON-lines + text fixtures parse; dashed/undashed handled; zero previous boots; journal failure → current boot from /proc + coverage; current-boot verification/mismatch detail. T-006 acceptance: all plan §2 items covered (see task row).
  - `PYTHONPATH=src .venv/bin/python -m syspanic --version` → `SysPanic 0.1.0`.
  - No GUI surface in M3; handoff on automated acceptance. All collector tests use injected fake runners/readers and synthetic fixtures — no real host journal, /proc, or subprocess reads.
- **Automated (prior M0 baseline, run 2026-11-16, preserved):** ruff clean; 38 passed (2 import, 3 arg-parsing, 23 offscreen GUI smoke, 3 icon-rendering, 7 offscreen E2E); `--version` → `SysPanic 0.1.0`. E2E covers CLI version/unknown flag, full lifecycle normal + demo, Ctrl+1..5, minimum-size clamping, close.
- **Deviations (M0):** QSS is generated from tokens in `ui/theme.py` instead of a separate `theme.qss` file (single token source; docs/02 §3 now matches this). Visual refinement (docs/03 revision): no top header bar — branding/tagline move to a ≈224px sidebar and the boot selector + Analyze move into the Overview "Analysis session" card; navigation icons are local QPainter outlines (`ui/icons.py`), no emoji/remote assets; reusable components in `ui/widgets/`. Boot selector and Analyze remain disabled placeholders; pages show designed idle/empty states; Ctrl+1..5 wired, other shortcuts deferred. No install performed; source-run via `PYTHONPATH` per plan §1 (hatchling not installed). Dual-theme refinement: Soft Light `text.secondary`/`text.muted`/`accent`/`nav_selected_text` and severity/state foregrounds were deepened from the initial proposal to meet WCAG AA (docs/03 §2 note); `MainWindow` constructed without an explicit manager defaults to a session-only store so tests never touch real preferences — only `app.main()` normal mode persists.
- **Manual QA:** all M0 QA PASS — user confirmed functional manual GUI QA and final visual QA of the polished dark shell on 2026-11-16 (real Fedora desktop), then confirmed the **dual-theme visual QA PASS** on 2026-11-16 (plan §4 steps 1–2, 15–17: both themes, switching, persistence across restart, demo isolation, 1280×720 + high-DPI). T-002/M0 promoted to `VERIFIED` on the user's explicit confirmation. Later milestones' GUI QA pends to M8/M9 per the gates. The user-only script is [05-implementation-plan.md](05-implementation-plan.md) §4 (17 steps), run as the normal desktop user, never root.
- **Status protocol:** `PLANNED → IN_PROGRESS → IMPLEMENTED_UNVERIFIED → VERIFIED`; `BLOCKED` for impasses.
  Only the user promotes to `VERIFIED` after manual QA (AGENTS.md §6, plan §7).
- **Evidence to record per task:** commands executed, actual test/lint outcomes, changed files, deviations, outstanding manual QA. No raw test output, real journal logs, or session transcripts.

## 6. Active blockers and next action

| ID | Blocker | Impact | State | Reference |
|---|---|---|---|---|
| BLK-001 | Final SoT approval not given; alignment-patch decisions pending | Blocked M0 and all implementation | CLOSED 2026-11-16 — user approved the SoT with three final corrections (provenance, dmesg boot isolation, artifact association) | docs status lines; plan §7; docs/02 D-13 |

**Next action:** M3 commit-and-push approved and executed 2026-11-16 (3 commits → `origin/main`). M4 (T-007–T-008) was offered and the user chose to wait ("Jangan dulu") — stop at the M3 boundary until explicit M4 authorization.

## 7. Milestone completion history

| Milestone | Date | Result | Remaining QA | Next milestone |
|---|---|---|---|---|
| M0 | 2026-11-16 | VERIFIED — ruff clean, 38/38 offscreen tests pass (incl. 3 icon-rendering + 7 E2E); user functional manual GUI QA PASS and final visual QA PASS (real Fedora desktop). Visual direction "Modern Diagnostic Workstation" + final polish accepted. | none at the time; later GUI QA pends to M8/M9 | M1 (awaiting authorization) |
| M0 refinement (T-002) | 2026-11-16 | VERIFIED — authorized dual-theme refinement (Dark + Soft Light, global switcher, QSettings appearance persistence). ruff clean; 79/79 offscreen tests pass (41 new theme tests incl. contrast AA + 3 theme E2E); `--version` OK; user manual visual QA of both themes PASS. Prior VERIFIED history above preserved. Committed `173a760`…`048e126`, pushed to origin/main. | none for M0; later GUI QA pends to M8/M9 | M1 (authorized and completed) |
| M1 (T-003) | 2026-11-16 | IMPLEMENTED_UNVERIFIED — domain enums + frozen dataclasses (docs/02 §5) + `validate_report()` with 29-ID rule catalog. TDD RED→GREEN; ruff clean; 139/139 offscreen tests pass (60 new); `--version` OK. No GUI surface; handoff on automated acceptance per plan. Committed `eedff6d`…`a0b475a`, pushed to origin/main. | manual QA NOT_APPLICABLE (pure logic); user acknowledgment pending | M2 (authorized and completed) |
| M2 (T-004) | 2026-11-16 | IMPLEMENTED_UNVERIFIED — bounded subprocess runner (docs/02 §7): Popen `shell=False`, C-locale env, bounded select-based reads, terminate→kill on timeout/cancel/overflow, state taxonomy + tail reliability. TDD RED→GREEN; ruff clean; 162/162 offscreen tests pass (23 new); `--version` OK. No GUI surface; handoff on automated acceptance per plan. | manual QA NOT_APPLICABLE (pure logic); user acknowledgment pending | M3 (authorized and completed) |
| M3 (T-005–T-006) | 2026-11-16 | IMPLEMENTED_UNVERIFIED — boot enumeration (JSON/text//proc fallbacks, normalization, current-boot verification) + journal collector (kernel/system slices, cursor dedupe, directional truncation/tail reliability, kernel_release, boot window, current-boot-only dmesg) + collector contract base.py. TDD RED→GREEN; ruff clean; 219/219 offscreen tests pass (57 new); `--version` OK. No GUI surface; handoff on automated acceptance per plan. | collection-related manual QA (plan §4.3–8) pends to M8/M9 | M4 (awaiting authorization) |

Add one concise entry per completed milestone (not per session): result, verification evidence summary, remaining manual QA, next milestone.

## Progress rules

- Derive progress from actual task statuses; never invent percentages or completion.
- Report implemented and VERIFIED counts separately.
- A milestone is implemented only when all its tasks are implemented and its automated acceptance checks pass; it is `VERIFIED` only after the user confirms the required manual QA.
- Never promote a task or milestone to `VERIFIED` on the user's behalf.
- Deferred/stretch work (ART-002/ART-003 classification, artifact corroboration, filters, search, "show all") is not required unless the approved plan says so.
- The implementation plan remains the authority for scope, dependencies, and acceptance criteria; this tracker records reality, not intent.