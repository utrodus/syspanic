# SysPanic — Architecture (v0.1.0)

**Status:** Approved source of truth · 2026-11-16
**Scope:** MVP architecture. Product requirements: [01-prd.md](01-prd.md). Diagnostic semantics: [04-diagnostics.md](04-diagnostics.md). UI: [03-ui-ux.md](03-ui-ux.md).

## 1. Context and constraints

| Constraint | Consequence |
|---|---|
| Linux desktop, Fedora KDE first, systemd journal assumed | Collectors target `journalctl` + `/proc` + `/sys`; no distribution packages, no non-systemd log paths |
| Never root, never sudo | Read access is whatever the user already has; denial is a first-class state |
| Offline, privacy-first | No network imports, no telemetry, no temp files, no log persistence |
| Read-only | Only user-chosen report export writes to disk |
| Python + PySide6 Qt Widgets | QtCore/QtGui/QtWidgets only; no QML, WebEngine, or third-party UI kits |
| One-day MVP | Single-process desktop app; synchronous engine, one background worker; no async framework |
| MIT project, LGPL-compatible deps | PySide6/Qt LGPLv3 used as a dynamically linked wheel; pytest/ruff are MIT |

## 2. System context

```
┌───────────────────────────── user session ─────────────────────────────┐
│  SysPanic GUI (Qt Widgets)                                             │
│    MainWindow ─ Controller ─ QThread ─ CollectionWorker                │
│                        │                                               │
│                        ▼                                               │
│  Collectors (stdlib subprocess / file reads)                           │
│    journalctl ── /proc ── /sys ── /var/crash ── pstore ── lspci        │
│                        │                                               │
│                        ▼                                               │
│  Diagnostic engine (pure Python) ── rules ── timeline ── coverage      │
│                        │                                               │
│                        ▼                                               │
│  Sanitizer ── Markdown renderer ── preview ── user-saved .md file      │
└────────────────────────────────────────────────────────────────────────┘
        no network · no elevation · no background daemon · no database
```

## 3. Module layout

```
src/syspanic/
  __init__.py              __version__ = "0.1.0"
  __main__.py              argparse entry point (`--demo`, `--version`), construct QApplication
  app.py                   app bootstrap, theme, MainWindow, exit handling
  constants.py             caps, timeouts, source names, app metadata
  domain/
    enums.py               Severity, EvidenceStrength, SourceState, TimelineKind, ArtifactAssociation
    models.py              dataclasses + validate_report()
  collectors/
    base.py                CollectionContext, CollectorResult, Collector protocol
    runner.py              bounded subprocess execution + error taxonomy
    boots.py               journal boot enumeration + /proc fallback
    journal.py             journal JSON slices, normalization, dedupe
    system.py              os-release, uname, cpuinfo, meminfo, lspci, DMI
    artifacts.py           bounded kdump incident subdirs, association, vmcore-dmesg, pstore, crash-kernel
    orchestrator.py        runs collectors with budget/cancel, merges coverage
  diagnostics/
    registry.py            ordered rule list, unique-ID assertion
    engine.py              evaluate rules -> findings, validate, sort
    timeline.py            key-event extraction and cap
    coverage.py            coverage aggregation + overall completeness
    rules/
      shutdown.py          SHD-001..004, BOT-001
      panic.py             PNC-001..004
      cpu_mce.py           MCE-001..002
      gpu.py               GPU-001..004
      memory.py            MEM-001..002
      pcie.py              PCI-001..003
      storage.py           STO-001..003
      thermal.py           THM-001..002
      artifacts.py         ART-001..003
      kernel_health.py     KRN-001
  report/
    sanitize.py            token-based redaction over rendered text
    markdown.py            IncidentReport -> sanitized Markdown
  ui/
    main_window.py         header, nav, QStackedWidget, footer, close handling
    controller.py          Qt-facing state machine, worker lifecycle, stale detection
    worker.py              QObject worker in a QThread; progress/cancel signals
    theme.py               design tokens
    theme.qss              Qt stylesheet
    pages/
      overview.py, timeline.py, evidence.py, system_info.py, report.py
    widgets/
      boot_selector.py, severity_badge.py, coverage_strip.py,
      state_panel.py, demo_banner.py
    table_models.py        QAbstractTableModel for timeline
  demo_data/
    boots.json
    journal_current.jsonl
    journal_previous.jsonl
    system.json
    vmcore-dmesg.txt
    pstore_oops.txt
    expected_findings.json
tests/                     unit, fixture integration, offscreen smoke
```

Rules: `domain/`, `collectors/`, `diagnostics/`, and `report/` must not import Qt. `ui/` must not call subprocess or parse logs directly.

## 4. Data flow

1. **Boot discovery** — `journalctl --list-boots --output=json` → `list[BootInfo]`; current boot verified against `/proc/sys/kernel/random/boot_id`.
2. **Collection** — orchestrator runs journal, system, and artifact collectors for the selected boot; each returns a payload plus `SourceCoverage` entries and issues.
3. **Normalization** — journal JSON lines become immutable `EvidenceItem`s (`JRN-*`, `DMS-*`, `VMD-*`, `PST-*`) retaining the boot ID and provenance metadata (`_TRANSPORT`, `_COMM`, `_EXE`, `_SYSTEMD_UNIT`, `SYSLOG_IDENTIFIER` when present); boot-list records become `BTM-*` metadata items and artifact records become `AFM-*` metadata items. Metadata items carry only non-secret fields (boot index/ID, path, size, mtime, association), never file contents.
4. **Analysis** — rule registry evaluates a `CollectionBundle`; findings reference evidence IDs; timeline and coverage are derived.
5. **Presentation** — controller receives one `IncidentReport` containing the findings and the complete normalized evidence used by the Evidence and Timeline pages; all five pages render from that object.
6. **Export** — Markdown is rendered from bounded excerpts, sanitized, previewed, then optionally written to a user-chosen path.

Analysis is a pure function of the bundle: same bundle → same findings, IDs, order, and wording.

## 5. Domain model

| Type | Key fields | Invariants |
|---|---|---|
| `BootInfo` | `index`, `boot_id` (32 lowercase hex), `is_current`, `first_entry`, `last_entry` (UTC, optional), `kernel_release` (optional) | `boot_id` validated; current boot unique; `kernel_release` is parsed from the selected boot's journal when available, never assumed from current inventory |
| `EvidenceItem` | `evidence_id`, `source`, `boot_id`, `timestamp` (UTC, optional), `priority`, `identifier`, `message`, `line_no`, `provenance` (`_TRANSPORT`, `_COMM`, `_EXE`, `_SYSTEMD_UNIT`, `SYSLOG_IDENTIFIER` when present) | Message has control characters removed, max 1,000 chars; journal items carry the boot ID and provenance metadata needed by rule checks; IDs unique and namespaced: `JRN-`, `DMS-`, `VMD-`, `PST-`, `BTM-` (boot metadata), `AFM-` (artifact metadata); journal entries require a timestamp, artifact/metadata text may omit it |
| `SourceCoverage` | `source`, `state`, `detail`, `entry_count`, `head_truncated`, `tail_reliable`, `elapsed_ms` | One entry per attempted source; `detail` user-safe; `tail_reliable=False` for byte-cap termination, timeout, cancellation, permission denial, non-zero exit, or collection failure; head truncation alone preserves a reliable tail |
| `SystemProfile` | `os_name`, `os_version_id`, `kernel`, `arch`, `cpu_model`, `cpu_cores`, `microcode`, `mem_total_kib`, `gpus`, `bios_*`, `board_*`, `collected_at` | No serials/UUIDs; `collected_at` mandatory; no kernel command line is collected |
| `GpuInfo` | `pci_address`, `vendor`, `model`, `driver` | Parsed from `lspci -Dnnk` |
| `ArtifactInfo` | `path`, `kind`, `size_bytes`, `mtime`, `readable`, `association`, `association_reason`, `incident_dir`, `note` | Path inside allowlist; `association` is `matched` / `possibly_related` / `unknown`; `matched` requires proven boot identity (boot ID or stronger incident identity); mtime or timestamp + kernel release alone never yields `matched`; binary `vmcore` never opened |
| `CrashArtifacts` | `vmcore_files`, `vmcore_dmesg`, `pstore_records`, `crash_kernel_loaded`, `notes` | Presence ≠ analyzed; association travels with each artifact |
| `Finding` | `finding_id`, `rule_id`, `category`, `title`, `severity`, `strength`, `evidence`, `interpretation`, `suspected_causes`, `unknowns`, `next_steps`, `sources` | ≥1 evidence ref; no banned claims; wording from rule |
| `EvidenceRef` | `evidence_id`, `excerpt` | Excerpt ≤3 lines / 300 chars per line; always resolvable in `IncidentReport.evidence` |
| `TimelineEvent` | `timestamp`, `kind`, `summary`, `severity`, `evidence_id` | Sorted ascending; ≤200; `evidence_id` may reference `JRN-*` or `BTM-*` |
| `CollectionBundle` | `boot`, `boots`, `entries`, `system`, `artifacts`, `coverage`, `issues`, `demo`, `hostname_hint` | Hostname hint is internal and never exported; `boots` supplies `BTM-*` evidence for the selector and boot boundaries |
| `IncidentReport` | `boot`, `findings`, `timeline`, `coverage`, `system`, `artifacts`, `evidence`, `generated_at`, `app_version`, `demo` | `evidence` is the complete normalized set needed by the Evidence and Timeline pages; validated by `validate_report()` before UI/export |

`validate_report()` rejects duplicate finding IDs, unknown rule IDs, unsorted timeline, duplicate coverage sources, demo-flag mismatch, and any evidence ref that does not resolve in `IncidentReport.evidence`.

## 6. Collector contract

```python
class Collector(Protocol):
    name: str
    def collect(self, ctx: CollectionContext) -> CollectorResult: ...

@dataclass(frozen=True)
class CollectorResult:
    payload: object
    coverage: tuple[SourceCoverage, ...]
    issues: tuple[CollectionIssue, ...] = ()
```

- `CollectionContext` carries the selected `BootInfo`, cancel event, and shared runner.
- Each collector owns its source names; the orchestrator merges results, rejects duplicate source names, and continues after individual failures.
- One collector failure becomes an `error`/`timeout` coverage entry; it never aborts the whole run.
- **Source names:** `journal.boots`, `journal.kernel`, `journal.system`, `dmesg`, `system.os`, `system.cpu`, `system.memory`, `system.gpu`, `system.firmware`, `crash.vmcore`, `crash.vmcore_dmesg`, `crash.pstore`, `crash.kexec`.

## 7. Command execution policy

```python
def run(argv: Sequence[str], *, timeout_s: float, max_bytes: int,
        cancel: threading.Event | None = None) -> CommandResult
```

| Rule | Detail |
|---|---|
| Invocation | argv list, `shell=False`, fixed commands only (`journalctl`, `lspci`, `dmesg --time-format iso`) |
| Environment | copy of environment + `LC_ALL=C`, `LANG=C`, `SYSTEMD_PAGER=cat`, `SYSTEMD_COLORS=0`, `PAGER=cat`, `NO_COLOR=1` |
| Timeouts | journal 30 s, `lspci` 10 s, `dmesg` 10 s, overall run budget 120 s |
| Bounds | read at most `max_bytes`; kernel journal 16 MiB, system journal 8 MiB, dmesg 2 MiB; terminate on overflow |
| Cancellation | cancel event checked before spawn and in the read loop; terminate, then kill, then mark cancelled |
| States | `available`, `not_found`, `permission_denied`, `timeout`, `error`, `empty` (mapped from exit code, exception, and known stderr hints) |
| Output | stdout parsed; stderr retained only as a short, user-safe coverage detail (no log content) |
| Side effects | none: no temp files, no writes, no network |

Known mapping: `FileNotFoundError` → `not_found`; `PermissionError` or stderr `Permission denied` / `Operation not permitted` / `No journal files were opened due to insufficient permissions` → `permission_denied`; timeout → `timeout`; non-zero otherwise → `error`. Exit 0 with no stdout → `empty`. If `dmesg --time-format` is unsupported or a line has no parseable timestamp, the entries are still collected without a timestamp and excluded from the timeline; the coverage detail records the limitation. A completed journal read that returns exactly the `-n` cap is `head_truncated=True` and `tail_reliable=True`; byte-cap termination, timeout, cancellation, permission denial, non-zero exit, or parse/collection failure sets `tail_reliable=False`. `dmesg` is collected only for the current boot; for historical boots its coverage is `unsupported` with an explanation, and current-boot kernel evidence is never mixed into historical incidents.

## 8. Journal access model

1. **Boot enumeration:** `journalctl --list-boots --output=json --no-pager`. If JSON fails, parse the text table. If both fail, fall back to `/proc/sys/kernel/random/boot_id` and expose only the current boot.
2. **Boot ID normalization:** journal IDs are undashed 32-hex. `BootInfo.boot_id` is stored undashed; display uses the first 8 characters. `--boot=<id>` must use the undashed form (dashed UUIDs are rejected by systemd).
3. **Current boot:** index `0`, confirmed by matching `/proc/sys/kernel/random/boot_id`; a mismatch is recorded in coverage detail.
4. **Slices:** kernel `journalctl --boot=<id> --kernel --output=json --no-pager -n 20000`; system `journalctl --boot=<id> --output=json --no-pager -n 5000`. The system slice includes kernel entries; deduplicate by `__CURSOR`, preferring the kernel slice.
5. **Parsing:** one JSON object per line; `__REALTIME_TIMESTAMP` (µs) → UTC `datetime`; `PRIORITY` → int; `MESSAGE` may be a string or a byte array and is decoded UTF-8 with replacement; ANSI/CSI sequences and C0 controls (except `\n`, `\t`) are stripped; malformed lines are skipped and counted.
6. **Ordering:** merge slices and sort by `(timestamp, cursor)`.
7. **Boot window and kernel release:** derive first/last timestamps and `kernel_release` from collected entries (first `Linux version` line) when available. `--list-boots` timestamps are display hints only (observed inconsistent on real systems).
8. **Directional truncation and tail reliability:** a slice that returns exactly `-n` entries after a clean exit has a retained tail and a truncated head (`head_truncated=True`, `tail_reliable=True`). A byte-cap termination, timeout, cancellation, permission denial, non-zero exit, or collection failure makes the tail incomplete (`tail_reliable=False`), even if some entries were parsed. The merged shutdown tail is reliable only when both kernel and system slices are non-empty and tail-reliable. Head truncation limits early-boot claims but does not invalidate a shutdown marker actually observed; an incomplete tail always suppresses absence-based shutdown findings ([04-diagnostics.md](04-diagnostics.md)).
9. **Time display:** UTC internally; local timezone with offset in the UI and report; the report states the analysis machine's timezone.

## 9. Threading and UI boundary

- `AnalysisController` (Qt) owns one `QThread` and one `CollectionWorker`.
- Worker signals: `progress(source, index, total)`, `finished(IncidentReport)`, `failed(message, issues)`, `cancelled()`.
- Only the controller mutates widgets; the worker owns no widgets and never touches the UI.
- One analysis at a time; Analyze is disabled while running. Selection changes during a run are applied after results arrive and trigger the stale-results banner.
- `closeEvent`: set cancel and wait up to 5 s. If the thread is still running, ignore the close event, keep the window open, and show `Finishing collection before closing…`; close automatically only after the worker acknowledges cancellation. Never call `QThread.terminate()` and never destroy a running `QThread`.
- If the selected boot changes after a run, results remain visible with a banner naming the analyzed boot; export uses the analyzed boot's data.

## 10. Security model

**Read-only path allowlist** (files and depth-1 directories):

| Path | Purpose |
|---|---|
| `/etc/os-release` | OS identity |
| `/proc/sys/kernel/osrelease`, `/proc/cpuinfo`, `/proc/meminfo` | Kernel, CPU, RAM |
| `/proc/sys/kernel/random/boot_id` | Current boot fallback |
| `/sys/class/dmi/id/{bios_vendor,bios_version,bios_date,board_vendor,board_name}` | Firmware/board identity |
| `/sys/kernel/kexec_crash_loaded`, `/sys/kernel/kexec_crash_size` | Crash-kernel state |
| `/var/crash/` (root + immediate kdump incident subdirs, bounded) | vmcore metadata and `vmcore-dmesg.txt` |
| `/sys/fs/pstore/` (depth 1) | pstore records |
| `/var/lib/systemd/pstore/` (depth 1, if present) | systemd-forwarded pstore records |

**Prohibitions and rules:**

- Never open `vmcore` or any binary dump; only names, sizes, and mtimes are read.
- Artifact roots: use `os.scandir(path)` (the API has no `follow_symlinks` argument), then inspect `entry.is_symlink()`, `entry.is_dir(follow_symlinks=False)`, and `entry.is_file(follow_symlinks=False)`. Reject symlinks and non-regular files. `/var/crash` may be scanned at its root plus one bounded level of immediate kdump incident directories (max 20 incident dirs, 50 entries total); no deeper recursion. `/sys/fs/pstore` and `/var/lib/systemd/pstore` are depth 1 only.
- Trusted fixed system paths may be symlinks or virtual files (`/etc/os-release`, `/sys/kernel/kexec_crash_loaded`); reading them through the fixed absolute path is allowed. Artifact-derived paths must be regular files and are never followed through symlinks.
- Read text artifacts with byte/line caps (256 KiB / 2,000 lines for `vmcore-dmesg.txt`; 64 KiB per pstore record; max 5 records).
- Allowlisted roots are module constants. Artifact collection may accept an explicit root list for tests only; production callers use the constants.
- Never collect `/proc/cmdline`; it is not required for v0.1.0 and can expose credentials or host-specific boot data.
- Never read `*_serial`, `product_uuid`, `chassis_serial`, or `/etc/machine-id`.
- No root check escalation, no sudo, no polkit, no journal/group/config changes.
- No network modules, no auto-update, no crash reporting, and no transmission of real host logs, crash dumps, or screenshots to coding agents, AI APIs, or external services.
- Log content is untrusted: plain-text widgets only, no HTML/rich-text rendering, control characters stripped, Markdown excerpts fenced.
- Reports are best-effort sanitized before they reach disk; raw evidence is never exported; preview is mandatory.
- The default boot is the current boot; absence-based findings require a completed boot with a reliably collected journal tail.

## 11. Sanitization and report boundary

Sanitization operates on the final rendered Markdown, not on the domain model, so nothing bypasses it on export. Seeds: `socket.gethostname()`, each captured journal `_HOSTNAME`, `getpass.getuser()`. Stable numbered tokens (`HOST_1`, `USER_1`, `IP_1`, `MAC_1`, `EMAIL_1`, `SERIAL_1`, `UUID_1`, `CRED_1`) preserve correlation inside one report. Credential redaction is best-effort: common `password=`/`passwd=`/`token=`/`api_key=`/`secret=` assignments, bearer tokens, `user:password@` URLs, and `postgres|mysql|redis|mongodb|https` connection strings are replaced; unrecognized secrets may remain.

Retained by design: boot IDs, PCI addresses, kernel version, timestamps, EDAC/MCE counts. Excluded: full logs, environment variables, `/proc/cmdline`, serials, DMI UUIDs, machine IDs. Preview is mandatory and explicitly states that redaction is best-effort; saving uses `QFileDialog` and UTF-8. Real host logs and crash dumps are never sent to coding agents, AI APIs, or external services.

## 12. Demo mode

`PYTHONPATH=src .venv/bin/python -m syspanic --demo` uses `DemoCollector` to load `src/syspanic/demo_data/` via `importlib.resources`, producing a normal `CollectionBundle` with `demo=True`. No system probing occurs. UI and report show `DEMO DATA — not collected from this machine`. The bundled fixtures are the same synthetic files used by the integration test, including artifact association metadata (see [04-diagnostics.md](04-diagnostics.md)).

## 13. Dependencies and packaging

| Item | Version |
|---|---|
| Python | `>=3.12` (verified on 3.14.10) |
| PySide6 | `==6.12.0` (transitive `shiboken6==6.12.0`) |
| pytest | `==9.2.0` |
| ruff | `==0.17.5` |
| Build backend | hatchling, pinned when installed |

`pyproject.toml` defines `[project]` metadata (MIT, scripts `syspanic = "syspanic.app:main"`), runtime dependency PySide6, optional `dev` group for pytest/ruff, `tool.ruff` (`target-version = "py312"`, `line-length = 100`, select `E,F,W,I,B,UP,SIM`), and `tool.pytest.ini_options` (`testpaths = ["tests"]`, `pythonpath = ["src"]`, `addopts = "-q"`).

Run without installing: `PYTHONPATH=src .venv/bin/python -m syspanic`. Sync the prepared environment with `.venv/bin/pip install -r requirements.txt`; that file pins the complete dev environment (including pytest transitives) and mirrors this table, but `pyproject.toml` remains the package metadata source. Install when network is available: `.venv/bin/pip install -e ".[dev]"`. No runtime non-Qt dependencies; no GPL-only dependency.

## 14. Test architecture

| Layer | Focus |
|---|---|
| Unit | parsers (boot list, journal JSON, cpuinfo, lspci, artifacts), runner caps/timeouts, directional truncation/tail reliability, artifact association, each core rule positive+negative (plus deferred rule tests when implemented), timeline ordering, coverage aggregation |
| Fixture integration | demo bundle → core expected rule IDs for both demo boots (deferred IDs asserted separately when implemented); report sections, artifact association, and credential redaction |
| Smoke | `QT_QPA_PLATFORM=offscreen` constructs the app and all five pages with a demo report; asserts nav/page wiring and state transitions. Agents use offscreen smoke only; real GUI execution is manual |
| Guard | scan rule/report strings for banned claims ("defective", "PSU failure", confidence percentages) |

No real host logs, no network, no display automation, no pytest-qt. Tests use `tmp_path` and generated synthetic fixture text; the packaged demo data is the only shared fixture set.

## 15. Decision log

| ID | Decision | Rationale |
|---|---|---|
| D-01 | `src/syspanic` layout, Python ≥3.12, pinned Qt/pytest/ruff | Standard, reproducible, matches prepared venv |
| D-02 | Journal-first; dmesg optional; no elevation | Journal is the only reliable source without root; `dmesg_restrict=1` is common |
| D-03 | Parse journal JSON; normalize boot IDs undashed; skip malformed lines | Structured fields beat text parsing; systemd rejects dashed boot IDs |
| D-04 | Bounded argv-only subprocesses with timeouts and cancellation | Prevents hangs, memory blowups, and injection |
| D-05 | Severity + evidence strength, no percentages | Avoids fake certainty |
| D-06 | 29-rule catalog; 27-rule core release-blocking, ART-002/ART-003 classification deferred; GPU split to GPU-001 timeout / GPU-002 reset / GPU-003 VM fault / GPU-004 Xid, with former BOT-002 correlation folded into BOT-001 and SHD-001 | Preserves the 29-ID catalog while prioritizing an end-to-end pipeline; artifact collection remains mandatory |
| D-07 | Explicit coverage states; absence never equals health | Core product promise |
| D-08 | Sanitize rendered Markdown; bounded excerpts; best-effort credential redaction; mandatory preview | Single enforcement point; minimizes leak surface without claiming perfect secrecy |
| D-09 | Qt Widgets only, five-page stack, restrained dark theme | Meets scope and one-day constraint |
| D-10 | QThread worker, pure engine; close ignores until cancellation completes | Responsive UI without destroying a running thread |
| D-11 | One packaged synthetic fixture set shared by demo and tests | No fixture drift; QA without hardware crashes |
| D-12 | Fixed allowlist, regular-file artifact paths, bounded incident subdirs, no binary vmcore, association-gated corroboration | Read-only, least-privilege collection with honest artifact claims |
| D-13 | Final corrections (approved 2026-11-16): kernel signatures require `_TRANSPORT=kernel` only; systemd markers use trusted process/unit metadata; `dmesg` is current-boot-only (`unsupported` for historical boots); artifact `matched` requires proven boot identity — timestamp + kernel release alone is `possibly_related` | Spoofable identifiers and unproven associations must not drive findings |

## 16. Explicit exclusions

No database, ORM, plugin system, DI framework, async/event loop beyond Qt, QML/WebEngine, HTTP client, telemetry, background service, systemd unit, auto-update, binary parsing, live sensors, or automatic remediation. If a feature requires one of these, it is post-MVP and requires approval.
