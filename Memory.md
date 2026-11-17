# Memory.md — SysPanic Working Memory

Persistent, concise context for coding sessions. Subordinate to the approved Source of Truth (SoT);
never overrides it. Detailed task progress lives in [docs/implementation-tracker.md](docs/implementation-tracker.md).
Last updated: 2026-11-17 (M3–M8 VERIFIED — user confirmed full integrated manual QA PASS A1–A18/B1–B6/C1–C4 after QA fixes #1–#5; automated 533/533, Qt-heavy subset exit 0 clean, full-run teardown abort classified as harness GC artifact; M4–M8 uncommitted, grouped commit-and-push plan pending approval; M3 pushed `46b8572`; M9 NOT authorized). Post-QA boot-popup cap (option A) IMPLEMENTED_UNVERIFIED at 535/535; its manual QA pending.

## 1. Current Project Context

- **Product:** SysPanic — "Don't panic. Diagnose." Local-only, read-only Linux crash/journal diagnostic report tool.
- **Version target:** v0.1.0 (one-day MVP). **License:** MIT.
- **Stack:** Python ≥3.12, PySide6 6.12 (Qt Widgets only); pytest + ruff as the only dev tools.
- **Platform:** Linux desktop, Fedora KDE first (Wayland).
- **Phase:** Implementation — M0 `VERIFIED` and pushed (`048e126`). M1–M3 pushed (through `46b8572`); M1/M2 pure logic `IMPLEMENTED_UNVERIFIED` (manual N/A), M3 `VERIFIED`. M4–M8 implemented 2026-11-16 under the explicit user goal and `VERIFIED` 2026-11-17 (T-007…T-023; automated 533/533, ruff clean; full integrated manual QA A1–A18/B1–B6/C1–C4 user-confirmed PASS); all M4–M8 changes uncommitted, commit plan pending approval. M9 not authorized.
- **SoT status:** all six documents `Approved source of truth · 2026-11-16`; docs/03 carries the "Modern Diagnostic Workstation" visual revision plus the approved dual-theme revision (Dark + Soft Light, §2/§2.1); the three accuracy corrections below remain in force.

## 2. Established Decisions

User-approved 2026-11-16 (authoritative references in parentheses):

- v0.1.0 scope, architecture, UI/UX; Python + PySide6 Qt Widgets; MIT; Fedora KDE first (docs/01–03).
- 29-rule catalog, 27 release-blocking core; ART-002/ART-003 classification and artifact corroboration deferred; artifact collection stays mandatory (docs/04 header, docs/05 T-010/T-012).
- GPU rebalance (GPU-001 timeout / GPU-002 reset / GPU-003 VM fault / GPU-004 Xid) and BOT-002 folded into BOT-001 + SHD-001 (docs/02 D-06).
- **Final correction 1 — provenance:** kernel signatures require `_TRANSPORT=kernel` only; `SYSLOG_IDENTIFIER` is spoofable; systemd markers use trusted process/unit metadata; EvidenceItem retains boot ID + provenance; spoofed-identifier negative tests required (docs/04 §5–6, docs/02 §5, D-13).
- **Final correction 2 — boot isolation:** dmesg collected/analyzed only for the current boot; historical boots mark it `unsupported`; never mix current-boot kernel evidence into historical incidents (docs/02 §7, docs/04 §9).
- **Final correction 3 — association:** `matched` requires proven boot identity; timestamp proximity + kernel release alone is only `possibly_related`; corroboration stays deferred (docs/04 §6.9, docs/02 §5).
- Source-run only; current-boot default with previous selection; bounded excerpts; offscreen smoke + logic tests, no pytest-qt, real GUI manual/user-only; `/proc/cmdline` never collected (docs/02 §10/§13, docs/05 §1).
- Decision log D-01…D-13 in docs/02 §15 is approved.
- **Visual refinement (user-approved 2026-11-16, docs/03 revision):** "Modern Diagnostic Workstation" — canvas #101115, sidebar #16181E, surface #191B22, elevated #23262F, border #30343D, primary #E7EBF1, secondary #98A1AF, accent #62D8B2, nav-selected #294238; Inter→Noto Sans; heading 26–28/section 16/body 14/meta 12px; cards 12px radius, controls/nav 8px; ≈224px sidebar with QPainter outline icons (no emoji/remote); no top header bar — session controls live in the Overview "Analysis session" card; idle headline "Every crash leaves a clue."; no fabricated data. T-002 only; M0 behavior/entry points preserved.
- **Dual theme (user-approved 2026-11-16, docs/03 §2/§2.1, docs/02 D-14):** Dark (default, palette unchanged) + Soft Light; one centralized `ThemeManager` in `ui/theme.py` (QPalette + shared QSS from per-theme tokens, `themeChanged` signal); compact sidebar Light/Dark segmented switcher (sun/moon icons) above the privacy indicator; immediate in-place switching preserving page/state. **Only persistence exception:** QSettings `SysPanic`/`SysPanic`, key `appearance/theme` = light|dark; missing/invalid/unreadable → Dark; write failure never blocks switching; demo = deterministic Dark + session-only MemorySettings; tests use isolated stores (tmp INI / XDG_CONFIG_HOME). Light secondary/muted/accent/nav-text/severity values deepened for WCAG AA (enforced by contrast tests). No settings page, no system-theme sync.
- **Boot popup cap (user-approved 2026-11-17, option A):** Overview boot selector popup limited to 8 visible rows with the themed scrollbar (`ScrollBarAsNeeded`); short lists keep natural height; day-grouping and filter-as-you-type rejected as overkill. Implemented as `BootSelector.showPopup()` container clamp because Qt 6.12 ignores `maxVisibleItems`. Post-M8-verification refinement; own manual QA pending, then joins the commit plan.

## 3. Pending Decisions

No pending product decisions. Remaining gates are procedural:

- Manual QA complete: user confirmed the full integrated §4 script PASS (A1–A18, B1–B6, C1–C4) 2026-11-17 → M3–M8 `VERIFIED`.
- Commit-and-push plan for the uncommitted M4–M8 work + QA fixes #1–#5 + SoT updates: presented for approval (target `origin/main`); no repository writes before approval.
- Manual QA of the post-QA boot-popup cap refinement (option A): pending; the refinement joins the commit plan once approved.
- M9 authorization: not given; stop at the M8 boundary.

## 4. Environment Notes

Documented observations (docs/05 §1; recorded earlier, not re-probed):

- Fedora Linux 44, KDE Plasma, Wayland; real GUI never yet run.
- `journalctl` readable by the current user; previous boots present.
- `kernel.dmesg_restrict=1`; `/sys/fs/pstore` inaccessible; `/var/crash` absent → coverage states, not failures.
- `journalctl --boot=<dashed-uuid>` rejected → normalize to undashed 32-hex.
- `--list-boots` timestamps unreliable → derive boot windows from entries.
- `lspci -Dnnk` available; `lsblk` not used.

Newly verified 2026-11-16 (read-only checks): `.venv` Python 3.14.10, PySide6 6.12.0, pytest 9.2.0, ruff 0.17.5.

Run commands (source-run): `PYTHONPATH=src .venv/bin/python -m syspanic [--demo]`;
checks: `.venv/bin/ruff check .` and `QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/pytest -q`.
Never include real host logs, identifiers, credentials, or dumps in this file.

## 5. Implementation Learnings

- Offscreen smoke works with a session-scoped `QApplication` fixture; `tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen` via `pytest_configure` so bare `pytest` never touches the real display.
- Keep Qt imports inside `app.main()` so `--version`/arg parsing run without a Qt platform; tests import `build_parser` headlessly.
- `resizeEvent`-driven tagline hiding (below 1360px) is verifiable offscreen via `resize()` + `processEvents()`.
- The Write tool omitted trailing newlines → 12 ruff W292 findings; `ruff check . --fix` resolved them. Run ruff after file creation.
- QSS generated from the token dict in `ui/theme.py` (no separate theme.qss) keeps one token source; recorded as an M0 deviation in the tracker.
- PySide6 exposes `QApplication.exec` as a static method — a test driver wrapping it must call `real_exec()` without `self`.
- E2E without a real display: run the real `main()` in an offscreen subprocess with `QApplication.exec` wrapped to assert UI state, then `QTimer.singleShot(0, quit)` for a clean exit (tests/test_e2e_m0.py).
- Visual refinement: base `QWidget { background: transparent }` + explicit container backgrounds (canvas/sidebar/card) removes stray label rectangles; `QIcon` Normal/Selected modes give nav icon color states. Session controls moved into Overview but still exposed as `window.boot_selector`/`analyze_button` so existing tests/E2E keep passing.
- Icon rendering fix: glyphs use a 24×24 coordinate system scaled by `physical/24`; set `QPixmap.setDevicePixelRatio(scale)` AFTER `painter.end()` — setting it before painting makes QPainter double-scale and clip at high-DPI/small sizes. Keep a stroke margin (paths within ~3..21, stroke 1.8) and verify bounds via alpha bbox in tests (tests/test_icons.py). Semantic names: dashboard/history/file_search/cpu/file_text/shield_check (+pulse/search/sun/moon).
- Dual-theme wiring: `theme.tokens()` mirrors the last applied theme for construction-time lookups; `icons.set_icon(label, name, token, size)` tags QLabel properties and `icons.retheme(root)` re-renders them on `themeChanged` (no per-widget connections, no duplicates). Nav icons and the ThemeSwitch refresh via the same signal. `MainWindow(demo, theme_manager=None)` defaults to a session-only MemorySettings manager, so direct construction in tests never touches real QSettings; only `app.main()` in normal mode creates real QSettings. E2E subprocesses set `XDG_CONFIG_HOME` to a temp dir for isolation. pyproject `addopts="-q"` doubles with CLI `-q` and hides the pass summary — use `-o addopts=""` for a canonical count.
- Domain layer (M1): `StrEnum` values mirror SoT strings exactly; frozen dataclasses with tuple fields; `validate_report(report, bundle=None)` aggregates all violations into one `ReportValidationError` (bundle param exists because demo-flag mismatch needs a second source of truth). `RULE_IDS` (29) lives in `domain/models.py` so the M6 registry can cross-check without circular imports. Excerpt bound enforced as ≤3 lines AND ≤300 chars per line (docs/02 §5 + docs/04 §10; docs/04 §2's "per reference" shorthand reads looser). `CollectionIssue(source, detail)` is a minimal shape — SoT names the type but not its fields. ruff UP017 wants `datetime.UTC`, not `timezone.utc`.
- Runner (M2): `select` on stdout+stderr fds with 0.1 s slices keeps timeout/cancel responsive and drains large stderr without deadlock (storage capped at 4 KiB, but keep reading past the cap or the child blocks). Byte-cap hit → `TRUNCATED` + terminate child + `tail_reliable=False`; entry-cap truncation (`head_truncated=True`, tail reliable) belongs to the M3 journal collector, not the runner. `tail_reliable` is True only for clean AVAILABLE/EMPTY. Cancel maps to state ERROR + `cancelled` flag (SourceState has no cancelled value). ruff SIM105 wants `contextlib.suppress` for try/except/pass.
- Boots/journal (M3): `normalize_boot_id` accepts undashed 32-hex or canonical 8-4-4-4-12 dashed UUID only — strip-all-dashes was too lenient (a trailing-dash test caught it). `--list-boots -o json` emits an array (new systemd) or JSON-lines (old) — handle both. Entry-cap truncation = retained+skipped == cap after clean exit → TRUNCATED head_truncated=True tail reliable; runner byte-cap TRUNCATED → tail unreliable. dmesg iso uses comma fractional seconds — `datetime.fromisoformat` handles it (3.11+); unsupported `--time-format` → plain dmesg fallback with timestamp-less entries. `JournalEntry`/`SliceParse`/`JournalPayload` are collector-level shapes (cursor lives only in JournalEntry); `EvidenceItem` stays the bundle currency. `BOOTS_MAX_BYTES` (1 MiB) is a chosen bound — SoT specifies journal/dmesg caps only.
- Engine/report (M6–M7): severity StrEnum values are lowercase — use `Severity(value)`, not `Severity[name]`. Demo current boot has no crash artifacts (previous boot carries vmcore/vmcore-dmesg/pstore → AFM); current-boot demo report has zero redaction tokens, previous has IP ×1. `DemoCollector.boots()` returns previous-first; UI sorts current-first. `render_report_with_counts()` returns (text, counts) for the Report page; demo preview prepends "> DEMO DATA …" before the title.
- GUI threading (M8): worker QObject moveToThread; result signals → `thread.quit` via **DirectConnection**; `thread.finished` → queued cleanup (`_on_thread_finished`: running=False, deleteLater both, closeReady if closing). **Close is async/non-blocking (QA fix #5, A17):** `request_close` sets `_closing`, returns True only when idle; while running it calls `cancel()` and returns False so `closeEvent` ignores + shows "Finishing collection before closing…"; the window closes via `closeReady`→`close()` only after `_on_thread_finished` confirms the worker stopped. Never block the GUI thread in `QThread.wait()` — the old timed wait froze the UI and, on fast cancel, closed the window instantly with no visible worker stop (A17 FAIL). Never `terminate()`. Fake workers must poll their gate (~20 ms) and honor cancel. Host TZ is UTC+7 — display-time assertions use `.astimezone()`, never hardcode UTC. `QFont` family lists need `setFamilies([...])`; widget.font() doesn't reflect QSS fonts. Orchestrator injectable collectors receive ctx only; bind path kwargs with `functools.partial` solely when the collector `is` the real default.
- Evidence contract (M8 QA fix): `decode_message` must strip ALL control characters incl. `\n\t` (docs/02 §5) — keeping them made `validate_report` reject real boots whose messages contain tabs/newlines ("Collection failed: ReportValidationError"), while clean synthetic demo fixtures hid the bug. Lesson: collector output must satisfy the domain validator end-to-end; add a parse→analyze regression for character-class contracts, not just unit assertions on the cleaner.
- Real-tool contracts (M8 QA fix #2): journalctl has NO `--kernel` option (systemd 259: only `-k/--dmesg`, which implies current boot). Kernel slice uses the explicit match `journalctl --boot=<id> _TRANSPORT=kernel …` — no implicit boot semantics, matches the trusted-provenance model. Lesson: fake-runner tests verify argv shape, not option validity — when a command is prescribed in SoT, verify it against the real tool's `--help` (help text only, never log content) before trusting it; both QA bugs were invisible to synthetic fixtures.
- Page layout pattern (M8 QA fix #3): every ScrollPage content layout must end with `addStretch(1)` and add `results_wrap` WITHOUT a stretch factor (Timeline is the reference). Stretch on a hidden `results_wrap` leaves no stretch item in idle, so QScrollArea widgetResizable surplus height stretches PageHeader (title/subtitle spread apart) and the empty card. Geometry regression tests compare header height + header→content gap against TimelinePage offscreen (resize 1200×900 + show + processEvents).
- Evidence highlight (M8 QA fix #4, A9/A10): jump-to-evidence must highlight the WHOLE line, not just the ID substring — `viewer.find(id)` selects only the ID and fades when the viewer lacks focus. Use a persistent `QTextEdit.ExtraSelection` (PySide6 exposes ExtraSelection on QTextEdit, NOT QPlainTextEdit) with `cursor.select(LineUnderCursor)` and token colors `evidence.highlight`/`evidence.highlight_text` (soft yellow, both themes, WCAG AA ≥4.5). Re-apply at the end of `_render_group` and on `themeChanged` (MainWindow→`evidence_page.refresh_highlight()`); clear when the ID is absent. ExtraSelections are code-side, so the QSS-token-only test is unaffected; the new tokens are in REQUIRED_KEYS + the contrast pair.
- Qt 6.12 combo popup (boot cap refinement): `showPopup()` sizes the container to ALL rows, ignoring `maxVisibleItems`; the combo view's default vertical scrollbar policy is `AlwaysOff`; QListView scrolls in row units; `indexAt`/`visualRect` use viewport coordinates. Cap deterministically in a `showPopup()` override: clamp container to `row height × maxVisibleItems + (container.height() − view.height())`, re-anchor the bottom edge when the popup opens upward, then `layout().activate()`; set `ScrollBarAsNeeded` so the themed scrollbar shows only when capped. Offscreen popup probes need `show()` + `showPopup()` + `processEvents()`.

## 6. Known Issues and Blockers

| ID | Description | Impact | State | Reference |
|---|---|---|---|---|
| BLK-001 | Final SoT approval was missing | Blocked all implementation | CLOSED 2026-11-16 — approved with three final corrections | docs status lines; docs/02 D-13 |
| BLK-002 | docs/02 §8.4 kernel-slice command used `--kernel`, which journalctl does not support (only `-k/--dmesg`); kernel slice ERROR on real hosts → 5th unavailable source + tail banner | M3 contract, M8 QA A5 | CLOSED 2026-11-16 — user approved explicit `_TRANSPORT=kernel` match; SoT §8.4/§8.5 corrected (D-15), code + test fixed | journal.py kernel_argv; docs/02 D-15 |

No other actionable issues.

## 7. Current Handoff

- **Last completed work:** M4–M8 (T-007…T-023) under the user goal 2026-11-16 — system/artifact collectors, demo fixtures, engine + 27 core rules + timeline + coverage, sanitizer + Markdown renderer, orchestrator + QThread worker/controller + five real pages + state matrix/banners/export. `VERIFIED` 2026-11-17: TDD RED→GREEN, ruff clean, 533/533 offscreen tests after five QA fixes, `--version` OK, and the user confirmed the full integrated manual QA script PASS. All M4–M8 changes uncommitted.
- **Active milestone/task:** boot-popup cap refinement (option A, post-QA) `IMPLEMENTED_UNVERIFIED` — automated 535/535, ruff clean; popup manual QA pending. M3–M8 remain `VERIFIED` for the QA-confirmed scope; commit plan pending approval. M9 not authorized.
- **Next actionable step:** present the grouped ("pilah") Conventional Commit plan for all uncommitted M4–M8 work + QA fixes #1–#5 + SoT D-15/highlight + tracker/Memory (target `origin/main`); commit/push only after explicit approval. M9 (T-024–T-026) requires separate authorization.
- **Required approvals:** commit-and-push plan (after QA PASS — now); M9 authorization. Commit approval ≠ M9 go.
- **Relevant files:** src/syspanic/collectors/{system,artifacts,demo,orchestrator,metadata}.py, src/syspanic/diagnostics/, src/syspanic/report/{sanitize,markdown}.py, src/syspanic/ui/{worker,controller,table_models,main_window}.py, ui/pages/, ui/widgets/, ui/theme.py; tests/test_{system,artifacts,demo,registry,engine,rules_*,timeline,coverage,sanitize,markdown,orchestrator,controller,timeline_model,report_page,ui_pages,ui_integration}.py.
- **Verification state:** M0 automated + manual QA PASS (VERIFIED); M1/M2 automated PASS, manual N/A (IMPLEMENTED_UNVERIFIED, no GUI gate); M3–M8 VERIFIED — automated 533/533 after five QA fixes (control chars in decode_message; kernel-slice `_TRANSPORT=kernel` match BLK-002/D-15; Evidence/Report idle layout stretch; evidence whole-line soft-yellow highlight; async non-blocking close) and full integrated manual QA A1–A18/B1–B6/C1–C4 user-confirmed PASS 2026-11-17. Qt-heavy subset (controller+ui_integration+ui_pages+theme) 97 passed exit 0 clean. Full-suite interpreter-shutdown abort (QObject warning + varying C++ signatures: malloc tcache / pure-virtual, exit 134 AFTER 533 passed, reproduced 2×) is the same non-deterministic harness GC artifact classified earlier (Qt-heavy subset clean; real app event loop processes deleteLater; E2E close tests assert clean exits); no app-path change.

## Memory maintenance rules

- Keep this file under ~120 lines; update facts in place, do not append session summaries.
- Store durable context and discoveries only; never duplicate the PRD, catalog, or task list.
- This file cannot override approved SoT requirements; remove stale entries when superseded.
- Never store real logs, dumps, serials, hostnames, credentials, or user data here.
- Link to [docs/implementation-tracker.md](docs/implementation-tracker.md) for task-level progress.