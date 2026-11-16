# Memory.md — SysPanic Working Memory

Persistent, concise context for coding sessions. Subordinate to the approved Source of Truth (SoT);
never overrides it. Detailed task progress lives in [docs/implementation-tracker.md](docs/implementation-tracker.md).
Last updated: 2026-11-16 (M0 fully VERIFIED — dual-theme QA PASS; commit plan approved; M1/T-003 authorized by user).

## 1. Current Project Context

- **Product:** SysPanic — "Don't panic. Diagnose." Local-only, read-only Linux crash/journal diagnostic report tool.
- **Version target:** v0.1.0 (one-day MVP). **License:** MIT.
- **Stack:** Python ≥3.12, PySide6 6.12 (Qt Widgets only); pytest + ruff as the only dev tools.
- **Platform:** Linux desktop, Fedora KDE first (Wayland).
- **Phase:** Implementation — M0 fully `VERIFIED` (dual-theme refinement: automated PASS + user visual QA PASS 2026-11-16; dark-shell functional + visual PASS earlier same day). **M1 authorized 2026-11-16** — T-003 next.
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

No pending product decisions. All procedural gates closed 2026-11-16:

- Dual-theme visual QA: user PASS. Commit-and-push plan: maintainer approved (4 grouped commits → origin/main).
- M1 authorization: granted by the user 2026-11-16. Next milestone gate: M1 acceptance criteria (plan §2); later GUI QA pends to M8/M9.

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

## 6. Known Issues and Blockers

| ID | Description | Impact | State | Reference |
|---|---|---|---|---|
| BLK-001 | Final SoT approval was missing | Blocked all implementation | CLOSED 2026-11-16 — approved with three final corrections | docs status lines; docs/02 D-13 |

No other actionable issues.

## 7. Current Handoff

- **Last completed work:** T-002 dual-theme refinement (Dark + Soft Light, global switcher, QSettings appearance persistence) — VERIFIED: ruff clean, 79/79 offscreen tests pass (38 prior M0 + 41 new theme incl. contrast AA, persistence, demo isolation, 3 theme E2E); user manual visual QA of both themes PASS 2026-11-16. Dark-shell QA history preserved in the tracker.
- **Active milestone/task:** M1 / T-003 (domain models + validate_report()) — authorized, starting after the refinement commits.
- **Next actionable step:** execute the approved 4-commit plan + push origin/main; then mark T-003 IN_PROGRESS and implement with TDD per plan §2.
- **Required approvals:** none pending for M1 start; any design change beyond approved SoT needs user approval; repository writes beyond the approved plan need a new command.
- **Relevant files:** src/syspanic/ui/theme.py (ThemeManager/tokens), ui/widgets/ (ThemeSwitch), ui/icons.py (set_icon/retheme, sun/moon), ui/main_window.py, app.py, tests/test_theme.py, docs/03-ui-ux.md §2/§2.1.
- **Verification state:** all M0 automated + manual QA PASS; later milestones' GUI QA pends to M8/M9.

## Memory maintenance rules

- Keep this file under ~120 lines; update facts in place, do not append session summaries.
- Store durable context and discoveries only; never duplicate the PRD, catalog, or task list.
- This file cannot override approved SoT requirements; remove stale entries when superseded.
- Never store real logs, dumps, serials, hostnames, credentials, or user data here.
- Link to [docs/implementation-tracker.md](docs/implementation-tracker.md) for task-level progress.