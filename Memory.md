# Memory.md — SysPanic Working Memory

Persistent, concise context for coding sessions. Subordinate to the approved Source of Truth (SoT);
never overrides it. Detailed task progress lives in [docs/implementation-tracker.md](docs/implementation-tracker.md).
Last updated: 2026-11-16 (M3 IMPLEMENTED_UNVERIFIED — automated PASS 219/219; M2 pushed `2501d26`; M0 VERIFIED).

## 1. Current Project Context

- **Product:** SysPanic — "Don't panic. Diagnose." Local-only, read-only Linux crash/journal diagnostic report tool.
- **Version target:** v0.1.0 (one-day MVP). **License:** MIT.
- **Stack:** Python ≥3.12, PySide6 6.12 (Qt Widgets only); pytest + ruff as the only dev tools.
- **Platform:** Linux desktop, Fedora KDE first (Wayland).
- **Phase:** Implementation — M0 `VERIFIED` and pushed (`048e126`). M1 pushed (`eedff6d`…`a0b475a`), M2 pushed (`56d3129`…`2501d26`). M3 implemented: T-005/T-006 `IMPLEMENTED_UNVERIFIED` (automated PASS 2026-11-16; no GUI surface). M4 awaiting authorization.
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

## 3. Pending Decisions

No pending product decisions. Remaining gates are procedural:

- M3 commit-and-push plan (3 grouped conventional commits → origin/main): awaiting maintainer approval; no repository writes before approval.
- M4 authorization: offered 2026-11-16 after M3; user chose "Jangan dulu" — stop at M3 until an explicit M4 command. M3 acceptance met on automated checks (plan §2); collection-related GUI QA pends to M8/M9.

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

## 6. Known Issues and Blockers

| ID | Description | Impact | State | Reference |
|---|---|---|---|---|
| BLK-001 | Final SoT approval was missing | Blocked all implementation | CLOSED 2026-11-16 — approved with three final corrections | docs status lines; docs/02 D-13 |

No other actionable issues.

## 7. Current Handoff

- **Last completed work:** T-005/T-006 (M3) — `collectors/{base,boots,journal}.py` + collection constants. IMPLEMENTED_UNVERIFIED: TDD RED→GREEN, ruff clean, 219/219 offscreen tests (57 new). M2 committed `56d3129`…`2501d26` and pushed.
- **Active milestone/task:** none — M3 implemented; M4 not authorized.
- **Next actionable step:** none authorized — M3 committed and pushed (approved 3-commit plan). Await explicit user authorization for M4 / T-007–T-008 (offered 2026-11-16, deferred).
- **Required approvals:** M4 authorization (deferred by user 2026-11-16); any design change beyond approved SoT needs user approval.
- **Relevant files:** src/syspanic/collectors/{base,boots,journal,runner}.py, src/syspanic/constants.py, tests/test_{boots,journal,journal_parse}.py; prior: domain/, ui/theme.py.
- **Verification state:** M0 all automated + manual QA PASS; M1/M2 automated PASS (manual N/A); M3 automated PASS (collection GUI QA pends to M8/M9).

## Memory maintenance rules

- Keep this file under ~120 lines; update facts in place, do not append session summaries.
- Store durable context and discoveries only; never duplicate the PRD, catalog, or task list.
- This file cannot override approved SoT requirements; remove stale entries when superseded.
- Never store real logs, dumps, serials, hostnames, credentials, or user data here.
- Link to [docs/implementation-tracker.md](docs/implementation-tracker.md) for task-level progress.