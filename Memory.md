# Memory.md — SysPanic Working Memory

Persistent, concise context for coding sessions. Subordinate to the approved Source of Truth (SoT);
never overrides it. Detailed task progress lives in [docs/implementation-tracker.md](docs/implementation-tracker.md).
Last updated: 2026-11-16 (M0 VERIFIED — functional + final visual manual QA PASS; M1 awaiting authorization).

## 1. Current Project Context

- **Product:** SysPanic — "Don't panic. Diagnose." Local-only, read-only Linux crash/journal diagnostic report tool.
- **Version target:** v0.1.0 (one-day MVP). **License:** MIT.
- **Stack:** Python ≥3.12, PySide6 6.12 (Qt Widgets only); pytest + ruff as the only dev tools.
- **Platform:** Linux desktop, Fedora KDE first (Wayland).
- **Phase:** Implementation — M0 `VERIFIED` (functional + final visual manual QA PASS, both 2026-11-16). M1 awaiting authorization.
- **SoT status:** all six documents `Approved source of truth · 2026-11-16`; docs/03 carries the user-approved "Modern Diagnostic Workstation" visual revision; the three accuracy corrections below remain in force.

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

## 3. Pending Decisions

No pending product decisions. M0 is fully VERIFIED (functional + visual). Remaining gate is procedural:

- Explicit user authorization before each subsequent milestone (M1 / T-003 next).

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
- Icon rendering fix: glyphs use a 24×24 coordinate system scaled by `physical/24`; set `QPixmap.setDevicePixelRatio(scale)` AFTER `painter.end()` — setting it before painting makes QPainter double-scale and clip at high-DPI/small sizes. Keep a stroke margin (paths within ~3..21, stroke 1.8) and verify bounds via alpha bbox in tests (tests/test_icons.py). Semantic names: dashboard/history/file_search/cpu/file_text/shield_check (+pulse/search).

## 6. Known Issues and Blockers

| ID | Description | Impact | State | Reference |
|---|---|---|---|---|
| BLK-001 | Final SoT approval was missing | Blocked all implementation | CLOSED 2026-11-16 — approved with three final corrections | docs status lines; docs/02 D-13 |

No other actionable issues.

## 7. Current Handoff

- **Last completed work:** M0 (T-001/T-002) VERIFIED — automated checks (ruff clean, 38/38 offscreen incl. 3 icon + 7 E2E) plus user functional manual GUI QA PASS and final visual QA PASS on the real desktop. "Modern Diagnostic Workstation" direction + final polish accepted.
- **Active milestone/task:** none.
- **Next actionable step:** explicit user authorization for M1 / T-003 (domain models + `validate_report()`).
- **Required approvals:** M1 authorization; any further design change beyond the revised docs/03 needs user approval.
- **Relevant files:** src/syspanic/ui/ (theme, icons, widgets, main_window, pages), docs/03-ui-ux.md, docs/implementation-tracker.md.
- **Verification state:** M0 automated PASS + functional manual PASS + visual manual PASS; later milestones' GUI QA pends to M8/M9.

## Memory maintenance rules

- Keep this file under ~120 lines; update facts in place, do not append session summaries.
- Store durable context and discoveries only; never duplicate the PRD, catalog, or task list.
- This file cannot override approved SoT requirements; remove stale entries when superseded.
- Never store real logs, dumps, serials, hostnames, credentials, or user data here.
- Link to [docs/implementation-tracker.md](docs/implementation-tracker.md) for task-level progress.