# SysPanic — Implementation Plan (v0.1.0)

**Status:** Approved source of truth · 2026-11-16
**Target:** functional v0.1.0 in one focused day (~10 h with buffer)
**Docs:** [PRD](01-prd.md) · [Architecture](02-architecture.md) · [UI/UX](03-ui-ux.md) · [Diagnostics](04-diagnostics.md)

## 1. Baseline

| Item | Value |
|---|---|
| Python | 3.14.10 in `.venv` (project requires ≥3.12) |
| PySide6 | 6.12.0 (Essentials, Addons, shiboken6 installed) |
| pytest | 9.2.0 |
| ruff | 0.17.5 |
| Build backend | hatchling (pin when installed) |
| OS | Fedora Linux 44, KDE Plasma, Wayland (verified Python/Qt only; GUI not yet run) |

**Commands (source-run, no install required):**

```bash
PYTHONPATH=src .venv/bin/python -m syspanic
PYTHONPATH=src .venv/bin/python -m syspanic --demo
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/pytest -q
.venv/bin/ruff check .
```

`pyproject.toml` sets `pythonpath = ["src"]` for pytest. Sync the prepared venv with `.venv/bin/pip install -r requirements.txt` (exact pins, including pytest transitives). Optional editable install: `.venv/bin/pip install -e ".[dev]"`. If the build backend cannot be downloaded, keep the `PYTHONPATH` commands and record the deviation in the milestone report; do not add alternatives that expand scope.

**Environment facts that shape acceptance:**

- `journalctl` is readable by the current user; previous boots are present.
- `kernel.dmesg_restrict=1` and `/sys/fs/pstore` is inaccessible; these must appear as coverage states, not failures.
- `/var/crash` does not exist; vmcore rules must handle absence without error.
- `journalctl --boot=<dashed-uuid>` is rejected; normalize to 32-hex.
- `lspci -Dnnk` is available; `lsblk` is not used.

## 2. Milestones

Dependency order is strict. Each task ends with its tests passing and `ruff check .` clean. Do not start a milestone before the previous acceptance criteria are met.

### M0 — Runnable desktop shell (75 min)

| Task | Work | Acceptance | Tests |
|---|---|---|---|
| **T-001** | `pyproject.toml`, `src/syspanic/{__init__,__main__,app,constants}.py`, placeholder `MainWindow`, `--demo` flag parsed | `python -m syspanic` opens a window titled `SysPanic`; `--version`/`--demo` parse; package imports | import smoke |
| **T-002** | Dual-theme tokens + shared QSS/QPalette (Dark default + Soft Light), centralized `ThemeManager`, sidebar branding/tagline + Light/Dark switcher, disabled boot selector + Analyze in the Overview session card, ≈224px nav, 5-page `QStackedWidget`, footer, 1280×720 minimum, QSettings `appearance/theme` persistence (demo session-only) | Nav switches all five pages; window matches [03-ui-ux.md](03-ui-ux.md) skeleton; theme switches immediately in place, preserves page/control state, persists and restores across restart (isolated settings in tests); Dark default on missing/invalid/unreadable preference; write failures degrade gracefully; demo never writes real preferences; no crash at minimum size; automated verification is offscreen only, real GUI execution is manual | `tests/test_smoke_gui.py`, `tests/test_theme.py`, `tests/test_icons.py` (offscreen) |

**Milestone gate:** the first milestone is a runnable minimal PySide6 app with verified setup and passing offscreen smoke.

### M1 — Domain model (25 min)

| Task | Work | Acceptance | Tests |
|---|---|---|---|
| **T-003** | Enums, dataclasses from [02-architecture.md](02-architecture.md) §5, `validate_report()` | Invalid findings (no evidence, unknown rule, duplicate IDs), unsorted timeline, and duplicate coverage are rejected | `tests/test_models.py` |

### M2 — Safe command runner (25 min)

| Task | Work | Acceptance | Tests |
|---|---|---|---|
| **T-004** | `run(argv, timeout_s, max_bytes, cancel)` with Popen, bounded read, termination, state mapping | Missing binary → `not_found`; permission error → `permission_denied`; timeout kills within ~1 s → `timeout`; oversized output → `truncated` with tail unreliable; cancel stops the child; empty stdout → `empty` | `tests/test_runner.py` (uses `.venv/bin/python -c`, no shell) |

### M3 — Boots and journal (50 min)

| Task | Work | Acceptance | Tests |
|---|---|---|---|
| **T-005** | Boot enumeration: `--list-boots -o json`, text fallback, `/proc` fallback, normalization, current-boot verification | JSON and text fixtures parse; dashed/undashed IDs handled; zero previous boots handled; journal failure yields current boot + coverage | `tests/test_boots.py` |
| **T-006** | Journal collector: kernel + system slices, JSON lines, message decoding, control-char stripping, cursor dedupe, boot window, kernel release, directional truncation/tail reliability | Malformed lines skipped and counted; byte-array messages decoded; duplicate kernel lines removed; entries sorted; caps enforced; permission path mapped; `BootInfo.kernel_release` extracted when a `Linux version` line exists; `-n` cap sets head-truncated with reliable tail; byte-cap/timeout/denial/error sets tail unreliable; dmesg collected only for the current boot, historical boots yield `unsupported` dmesg coverage | `tests/test_journal.py`, `tests/test_journal_parse.py` |

### M4 — System profile and crash artifacts (35 min)

| Task | Work | Acceptance | Tests |
|---|---|---|---|
| **T-007** | OS/kernel/arch/CPU/memory/GPU/firmware collectors from the allowlist | Missing paths produce coverage, not exceptions; DMI serial/UUID never read; `/proc/cmdline` never collected; `lspci` parse handles empty output | `tests/test_system.py` |
| **T-008** | Artifact collector: `/var/crash` root + immediate kdump incident subdirs, pstore, kexec, `vmcore-dmesg.txt` cap, association | Uses `os.scandir(path)` plus `entry.is_file/is_dir(follow_symlinks=False)`; symlinks/non-files skipped; binary vmcore never opened (assert no read call); text caps enforced; mtime and association recorded; matched/possibly/unknown covered (timestamp + kernel release alone is only possibly_related); denied paths reported | `tests/test_artifacts.py` (tmp dirs, mocked allowlist) |

### M5 — Demo data (25 min)

| Task | Work | Acceptance | Tests |
|---|---|---|---|
| **T-009** | Two-boot fixtures from [04-diagnostics.md](04-diagnostics.md) §12, demo collector via `importlib.resources`, `expected_findings.json` | `--demo` produces a `CollectionBundle` with `demo=True` and both boots; no system calls; fake identifiers present for sanitizer tests | `tests/test_demo.py` |

### M6 — Diagnostic engine (120 min)

| Task | Work | Acceptance | Tests |
|---|---|---|---|
| **T-010** | Rule protocol, registry with unique IDs, finding assembly, severity ordering, corroboration upgrades, validation | Catalog metadata exposes 29 unique IDs in 10 families; v0.1.0 evaluates the 27 core IDs; deferred ART-002/ART-003 are tracked as disabled, never silently omitted; ordering deterministic; corroboration table applied only as specified | `tests/test_engine.py`, `tests/test_registry.py` |
| **T-011** | Rules: SHD-001..004, BOT-001, PNC-001..004, MCE-001..002 | Positive/negative cases; SHD-002 never fires for current boot, unavailable journal, or unreliable tail; Journal stopped alone is not clean-shutdown proof; kernel-only signatures require `_TRANSPORT=kernel` with spoofed-`SYSLOG_IDENTIFIER` negative tests; MCE unspecified → Notice | `tests/test_rules_shutdown.py`, `test_rules_panic.py`, `test_rules_cpu_mce.py` |
| **T-012** | Rules: GPU-001..004 (core), MEM-001..002, PCI-001..003, STO-001..003, THM-001..002, ART-001 (core), KRN-001; ART-002/ART-003 deferred | GPU timeout and reset are separate; Xid 79 critical; AER fatal vs non-fatal; PCIe Bus Error alone is not PCI-003; EDAC/MCE line-scoped; artifact association labels; only matched artifacts corroborate; taint G is not adverse; deferred rules tracked | `tests/test_rules_gpu.py`, `test_rules_memory.py`, `test_rules_pcie.py`, `test_rules_storage.py`, `test_rules_thermal.py`, `test_rules_artifacts.py` |
| **T-013** | Timeline builder: boot boundaries, first occurrence per rule, markers, cap 200 | Sorted, deduplicated, capped, no artifact mtimes; boot boundaries reference `BTM-*` | `tests/test_timeline.py` |
| **T-014** | Coverage aggregation + overall completeness + head/tail reliability | Each attempted source once; `complete`/`partial`/`minimal`; SHD-002 gated on reliable tails; head truncation distinguished from tail loss | `tests/test_coverage.py` |

### M7 — Sanitization and report (40 min)

| Task | Work | Acceptance | Tests |
|---|---|---|---|
| **T-015** | Token redaction: hostname (including IP-like), user, home paths, IPv4/IPv6, MAC, email, serials, UUID/machine-id, common credentials/tokens/connection strings; counts | Fake fixture identifiers replaced; boot IDs/PCI addresses retained; credentials become `CRED_n`; tokens stable and numbered; idempotent on already-redacted text; wording states best-effort | `tests/test_sanitize.py` |
| **T-016** | Markdown renderer: required sections, coverage table, bounded excerpts, demo notice, limitations, artifact association, redaction summary | All required sections; no full logs; excerpts fenced; pipe escaping; deterministic output; association shown; best-effort redaction notice; <100 KiB on fixtures | `tests/test_markdown.py` |

### M8 — GUI integration (120 min)

| Task | Work | Acceptance | Tests |
|---|---|---|---|
| **T-017** | `AnalysisController` + `CollectionWorker` QThread, progress, cancel, stale detection, demo boot selection; controller receives one report containing complete evidence | UI stays responsive; single-flight; cancel acknowledged; results applied atomically; Evidence/Timeline render from `IncidentReport.evidence`; close waits ≤5 s, then keeps the window open until cancellation completes; never `terminate()` a running thread | `tests/test_controller.py` (logic, offscreen) |
| **T-018** | Overview page: summary, severity counts, findings (expand for evidence/causes/unknowns/next steps), coverage strip, artifacts, next steps, empty states | Renders demo report; zero findings copy exact; expandable detail works; evidence links navigate | `tests/test_smoke_gui.py` |
| **T-019** | Timeline page: table model, severity filter, double-click navigation | Sorted; filter retains order; evidence jump works | smoke + model test |
| **T-020** | Evidence page: source list + states, monospace viewer, filter, denied panel | All evidence-bearing sources listed with counts/states, including `BTM-*` boot metadata and `AFM-*` artifact metadata; head/tail truncation and tail reliability visible; the 13-source coverage appears on Overview and in the report; filter; no rich text; artifact metadata only | smoke |
| **T-021** | System Information page: cards, GPU table, "collected now" banner, missing-value states | Missing fields show `Not available`; no serials | smoke |
| **T-022** | Report page: preview, redaction summary, best-effort notice, copy, save dialog, filename, error handling | Preview is mandatory before copy/save; export disabled until preview; filename pattern; UTF-8; `CRED_n` summary; success/error feedback | `tests/test_report_page.py` |
| **T-023** | State matrix: idle, collecting, partial, tail-uncertain, permission, error, cancelled, stale, demo banners | Each state matches [03-ui-ux.md](03-ui-ux.md) §6; no modal progress; SHD-002 absent when tail uncertain | smoke state test |

### M9 — Hardening and release candidate (45 min)

| Task | Work | Acceptance | Tests |
|---|---|---|---|
| **T-024** | End-to-end demo integration: bundle → findings → timeline → coverage → markdown | Exact core expected rule IDs for both boots; deferred IDs asserted separately when implemented; artifact association; sanitizer removes fake PII and credentials; report sections present | `tests/test_pipeline.py` |
| **T-025** | Quality pass: banned-phrase test, ruff zero findings, remove dead code, README with run/QA/privacy notes | `ruff check .` clean; all tests pass; README matches commands; tests use synthetic fixtures only and never real host logs | `tests/test_wording.py` |
| **T-026** | Release checklist, version consistency (pyproject + `__version__`), manual QA handoff | Checklist complete; core 27 green; deferred status documented; status set to `IMPLEMENTED_UNVERIFIED`; no commit/push | manual |

**Stretch order if time runs out** (drop from the bottom): ART-002/ART-003 classification, artifact corroboration, timeline severity filters, evidence search, Overview "show all" expansion. Core artifact collection/listing, all 27 core rules, shutdown tail gating, association labels, sanitization, and the complete evidence contract are never cut.

### Requirement traceability

| FR | Tasks |
|---|---|
| FR-01 Boot selection | T-001, T-002, T-005, T-017 |
| FR-02 Journal collection | T-006 |
| FR-03 System profile | T-007, T-021 |
| FR-04 Event classification | T-010, T-011, T-012 |
| FR-05 Evidence display | T-020 |
| FR-06 Incident timeline | T-013, T-019 |
| FR-07 Coverage reporting | T-014, T-018, T-023 |
| FR-08 Crash artifacts | T-008, T-021 |
| FR-09 Sanitized report | T-015, T-016, T-022 |
| FR-10 Demo fixtures | T-009, T-017 |
| FR-11 Responsive collection | T-017, T-023 |
| FR-12 Graceful failure | T-004, T-005, T-006, T-023 |

## 3. Test matrix summary

| Area | Files | Key assertions |
|---|---|---|
| Models | `test_models.py` | Validation and invariants |
| Runner | `test_runner.py` | Timeout, caps, permission, cancellation, no shell |
| Collectors | `test_boots.py`, `test_journal*.py`, `test_system.py`, `test_artifacts.py` | Parsing, normalization, symlink safety, no binary reads |
| Rules | `test_rules_*.py`, `test_registry.py` | 29 catalog IDs, 27 core evaluated, positive/negative, `_TRANSPORT=kernel` provenance with spoofed-identifier negatives, GPU timeout/reset separation, MCE/EDAC and PCIe negatives, tail gating, severity mapping |
| Report | `test_sanitize.py`, `test_markdown.py`, `test_wording.py` | Redaction including `CRED_n`, best-effort wording, sections, bounded excerpts, artifact association, banned phrases |
| Integration | `test_demo.py`, `test_pipeline.py` | Exact core expected findings, deferred separately, full pipeline, complete evidence refs |
| GUI | `test_smoke_gui.py`, `test_controller.py`, `test_report_page.py` | Offscreen construction, page wiring, state transitions, close safety, no pytest-qt |

All tests use generated text, `tmp_path`, or packaged synthetic demo fixtures. No real host logs, no network, no display automation, no transmission to coding agents or external AI services.

## 4. Manual GUI QA script

Run as the normal desktop user, never root.

1. `PYTHONPATH=src .venv/bin/python -m syspanic` — window opens at 1440×900, dark theme by default, five nav entries, Light/Dark switcher above the sidebar privacy indicator, footer says `Local only`.
2. Resize to 1280×720 — no clipped controls, tagline hidden, pages scroll.
3. Select the current boot, press Analyze — progress appears, window can be dragged, Analyze becomes Cancel; pages populate.
4. Cancel a second run — footer shows `Collection cancelled.` and previous results remain.
5. Verify coverage reflects this machine: `dmesg` denied, pstore denied/not found, journal available; head/tail truncation and tail reliability display correctly; no crash.
6. Select a previous boot if present, Analyze — timeline sorted, findings cite evidence, `Show evidence` and double-click navigation work.
7. Switch boot after analysis — stale banner names the analyzed boot; export remains available for the displayed report.
8. Evidence page: filter lines, switch sources, confirm unavailable sources show the denied/empty panel, not a blank pane; confirm `BTM-*`/`AFM-*` metadata and artifact association are visible.
9. System Information: verify the "collected now" banner, GPU table, `Not available` for missing sources, no serial numbers, and no kernel command line.
10. Report: inspect the best-effort redaction notice and summary (including `CRED_n`), preview, Copy, then Save to a writable path; confirm filename `syspanic-report-<bootid8>-<UTC>.md` and required sections; confirm no hostname/user/IP/serial, no credential assignments, and no full log.
11. Save to an unwritable path — inline error, app stays responsive.
12. `--demo` — demo banner visible, both boots analyzable, core expected findings appear; deferred ART-002/ART-003 may be absent, and the report begins with the demo notice.
13. Keyboard: Ctrl+1..5, Ctrl+R, Ctrl+E, F5, Esc during collection.
14. Close during collection — cancel is requested; if the worker has not stopped, the window stays open with `Finishing collection before closing…` and closes only after acknowledgment; never a forced thread teardown.
15. Appearance: switch to Light — the whole shell (sidebar, cards, controls, footer, icons, empty states) restyles immediately with no dark rectangles, no layout shift, and the current page preserved; switch back to Dark and repeat several times; keyboard (Tab + Space) reaches and activates both choices; tooltips and active state are clear.
16. Appearance persistence: select Light, close, relaunch — Light is restored; select Dark, relaunch — Dark is restored. At 1280×720 and with high-DPI scaling, both themes stay readable with no clipped icons or text.
17. Demo isolation: `--demo` starts Dark; switching themes works for the session, and after closing, the normal-mode preference is unchanged (demo never writes real settings).

Report results per milestone; screenshots optional and must not contain personal data.

## 5. Risk register

| Risk | Mitigation | Trigger to escalate |
|---|---|---|
| Journal unreadable | Coverage state + neutral hint; demo mode | No boot list at all on target machine |
| List-boots timestamps inconsistent | Derive windows from entries | Boot window uncomputable |
| dmesg/pstore denied | Treat as coverage; journal primary | Journal also unavailable |
| Subprocess hang | Timeouts + kill + cancel | Cancel does not return in 2 s |
| Qt thread lifecycle | Controller owns thread; ignore close until cancellation completes; never terminate; tests | App crash/hang on close |
| Artifact misassociation | Matched/possibly/unknown model; mtime or timestamp + kernel release alone insufficient; corroborate only matched | Any unverified dump upgrades a finding |
| Tail coverage loss | Head/tail fields; suppress SHD-002 when unreliable | SHD-002 fires without a reliable tail |
| Sanitizer miss | Fake PII/credential fixture tests + mandatory preview | Any real identifier or credential in exported report |
| Time overrun | Core 27 first; ART-002/003 deferred; stretch order above | M6 or M8 exceeds 2× estimate |
| Editable install offline | `PYTHONPATH` fallback documented | PySide6 import fails |
| False positives from absence | Current-boot exclusion, reliable-tail gate, circumstantial strength | Rule fires without evidence |

## 6. Release checklist (v0.1.0)

- [ ] All tests pass; `ruff check .` clean; offscreen smoke passes.
- [ ] 27 core rules implemented with positive and negative tests; 29 catalog IDs accounted for; ART-002/ART-003 deferred status explicit and approved.
- [ ] Demo core pipeline matches expected findings for both boots; deferred expectations tracked separately.
- [ ] Real collection verified on Fedora KDE, with permission and tail-reliability states correct.
- [ ] Artifact collection, bounded incident-subdir scan, association, and no-binary-vmcore tests pass.
- [ ] Manual GUI QA script completed by the user.
- [ ] Version `0.1.0` consistent in `pyproject.toml` and `syspanic.__version__`.
- [ ] README documents run commands, demo mode, privacy, best-effort redaction, and limitations.
- [ ] No real logs, dumps, serials, hostnames, or user identifiers in the repository; no real host logs or dumps sent to coding agents, AI APIs, or external services.
- [ ] MIT license intact; no GPL-only dependencies added.
- [ ] Status reported as `IMPLEMENTED_UNVERIFIED` until user QA passes.
- [ ] No commit, push, tag, or release without explicit approval.

## 7. Status protocol

The five Source of Truth documents and AGENTS.md are **Approved source of truth** (2026-11-16), including the three final corrections: trusted `_TRANSPORT=kernel` provenance, current-boot-only dmesg, and proven-identity artifact matching. Do not implement against an unapproved change to them.

| Status | Meaning |
|---|---|
| `PLANNED` | In the plan, not started |
| `IN_PROGRESS` | Active milestone only |
| `IMPLEMENTED_UNVERIFIED` | Code and automated checks done; manual GUI QA pending |
| `VERIFIED` | User completed the manual QA script |
| `BLOCKED` | A contradiction, permission issue, or missing dependency prevents progress |

Only the user can promote `IMPLEMENTED_UNVERIFIED` to `VERIFIED`. A milestone report includes: status, files changed, commands run with results, deviations from this plan, and remaining QA steps.

## 8. Recommended first task

**T-001 — project scaffold and runnable window.** Create `pyproject.toml`, the `src/syspanic` package skeleton, the argparse entry point (`--demo`, `--version`), and a minimal window; verify `PYTHONPATH=src .venv/bin/python -m syspanic`, `pytest -q`, and `ruff check .`. T-002 immediately follows to deliver the five-page dark shell.
