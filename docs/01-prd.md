# SysPanic — Product Requirements (v0.1.0)

**Status:** Approved source of truth · 2026-11-16
**Tagline:** Don't panic. Diagnose.
**License:** MIT · **Platform:** Linux desktop, Fedora KDE first · **Stack:** Python 3.12+ / PySide6 6.12 (Qt Widgets)

## 1. Problem

After an unexpected reboot, freeze, GPU hang, or kernel panic, a Linux user has the evidence on their machine but no practical way to read it. The journal is verbose, sometimes unreadable, and easy to misread: a missing shutdown marker looks like power loss, an AMDGPU reset looks like a dead GPU, and a corrected PCIe error looks like a failing motherboard. Existing crash tooling targets kernel developers and dump files, not the person who just wants to know what happened.

SysPanic converts locally available journal entries and crash artifacts into a deterministic, evidence-cited incident report. It reports what the logs show, what they suggest, and what remains unknown — without uploading data, escalating privileges, or pretending to diagnose hardware it cannot test.

## 2. Target users

| Persona | Situation | Needs |
|---|---|---|
| Fedora KDE user | Desktop rebooted or froze unexpectedly | A plain-language answer, the exact log lines, and next steps |
| Developer / homelab operator | Intermittent GPU hangs or I/O errors | A chronological incident view and a report attachable to a bug tracker |
| Support engineer | Helping someone else remotely | A redacted Markdown report with coverage gaps stated |

Daily operation is non-root. A user who cannot read the system journal is still a supported user: SysPanic explains the gap rather than working around it.

## 3. Product principles

1. **Evidence over verdicts.** Every finding cites source lines. Facts, suspected causes, and unknowns are separate fields.
2. **Read-only and local.** No writes outside the user-chosen export, no network, no telemetry, no privilege escalation.
3. **Honest degradation.** Missing, truncated, denied, or malformed sources are displayed, never treated as health.
4. **One screen per question.** Overview (what happened), Timeline (when), Evidence (proof), System Information (context), Report (share).
5. **Fast to first answer.** Default selection is the current boot; one click starts analysis; the UI never blocks.
6. **KISS.** Small modules, standard library first, Qt Widgets only, no database, plugin system, or background daemon.

## 4. MVP functional requirements

Each requirement is testable and owned by one page or module. Page names match [03-ui-ux.md](03-ui-ux.md); technical contracts are defined in [02-architecture.md](02-architecture.md).

| ID | Requirement | Acceptance criteria |
|---|---|---|
| **FR-01** | **Boot selection.** List boots from the systemd journal, mark the current boot, display a short boot ID and start time. Default to the current boot. | Selector lists all journal boots; current is marked; previous boots are selectable; refresh (F5) re-reads the list; if the journal is unavailable, the current boot ID from `/proc` is shown with a coverage warning; zero previous boots is a handled empty state. |
| **FR-02** | **Journal collection.** Collect kernel and system journal slices for the selected boot using `journalctl --output=json`, bounded and timestamped. | Kernel slice capped at 20,000 entries and system slice at 5,000; duplicates removed by cursor; malformed JSON lines are counted and skipped, not fatal; head truncation and tail reliability are reported separately; an incomplete tail is never treated as a completed journal; `dmesg` is collected only for the current boot and marked `unsupported` for historical boots. |
| **FR-03** | **System profile.** Collect OS, kernel, architecture, CPU model/cores/microcode, RAM total, GPU PCI address/model/driver, and BIOS/board vendor/name/version. | Values render on System Information with a "collected now" notice; unavailable sources show a state, not a fabricated value; no serial numbers or DMI UUIDs are read. |
| **FR-04** | **Event classification.** Run the 29-rule catalog in 10 families over collected evidence; v0.1.0 releases the 27-rule core, with ART-002/ART-003 classification and artifact corroboration deferred while artifact collection remains mandatory. | Rules cover shutdown/boot, panic/oops, MCE, GPU, EDAC, PCIe/AER, storage, thermal, crash artifacts, and kernel taint; kernel-only signatures require `_TRANSPORT=kernel` journal metadata; GPU timeouts and reset attempts are separate findings; MCE/EDAC classification is line-scoped; every finding has ≥1 evidence reference and exposes observed evidence, suspected causes, unknowns, and next steps; demo fixtures produce the core expected rule IDs (see [04-diagnostics.md](04-diagnostics.md)). |
| **FR-05** | **Evidence display.** Show normalized entries with source, timestamp, identifier, journal priority, and message; allow search and source filtering. | Evidence page lists every journal/artifact source with entry counts and states; search filters within the selected source; permission/empty states are explicit. |
| **FR-06** | **Incident timeline.** Build a chronological view of key events: boot boundaries, shutdown markers, and the first occurrence of each finding. | Events sort ascending by timestamp; capped at 200 with a visible note; no live or current-sensor events are mixed into the historical timeline. |
| **FR-07** | **Coverage reporting.** Report each attempted source as available, empty, truncated, permission-denied, not-found, unsupported, timeout, or error, plus head/tail truncation and journal tail reliability, and an overall completeness banner. | Every attempted source appears exactly once; overview banner shows "N of M sources available"; missing evidence is never described as healthy; absence-based shutdown findings are disabled when either journal tail is not reliably collected. |
| **FR-08** | **Crash artifacts.** Detect and list vmcore metadata, `vmcore-dmesg.txt`, pstore records, and crash-kernel state when accessible; associate each artifact with the selected boot as matched, possibly related, or unknown. | Artifacts show path, size, mtime, and boot association; bounded inspection covers immediate kdump incident subdirectories under `/var/crash`, never follows artifact symlinks, and never opens binary `vmcore`; association requires content/metadata correlation, never mtime alone; `matched` requires proven boot identity, and timestamp proximity + kernel release alone is only possibly_related; unrelated or unverified artifacts never corroborate an incident. |
| **FR-09** | **Sanitized Markdown report.** Preview and export a best-effort redacted Markdown report with findings, coverage, limitations, and a redaction summary. | Preview is mandatory before export; export requires an explicit Save dialog; bounded excerpts only (≤3 lines × 3 references per finding); no full journal appendix; filename `syspanic-report-<bootid8>-<UTC>.md`; no hostname, username, home path, IP, MAC, email, serial, DMI UUID, or machine ID (boot IDs are retained by design and disclosed); common credential patterns (passwords, tokens, API keys, connection strings) are replaced with `CRED_n`; the report states that redaction is best-effort, not a guarantee. |
| **FR-10** | **Demo fixtures.** Provide `--demo` mode using packaged sanitized fixtures through the same pipeline. | No system probing in demo mode; two boots are analyzable; UI and report display a persistent demo watermark; tests reuse the same fixtures. |
| **FR-11** | **Responsive collection.** Execute collection in a background worker with progress and cancellation. | Window remains interactive during analysis; Analyze is disabled while running; Cancel stops between sources and terminates a running subprocess; results, not partial widgets, are applied atomically. |
| **FR-12** | **Graceful failure.** Handle unavailable commands, permission denial, missing previous boots, incomplete logs, malformed entries, timeouts, and empty results. | Each case maps to a coverage state and a specific hint; partial analysis still renders; the application does not crash or hang. |

## 5. Non-goals (v0.1.0)

- Real-time sensor monitoring or a background daemon.
- Hardware stress testing.
- Automatic system repair, BIOS tuning, or kdump configuration.
- Binary vmcore parsing.
- AI APIs, cloud services, authentication, telemetry, or external data uploads.
- Database, plugin architecture, microservices, or unnecessary abstraction.

## 6. Accuracy, privacy, and security requirements

- **Accuracy:** deterministic rules only; no confidence percentages; no component-defect claims; no PSU or power-loss inference from missing markers; kernel-only signatures require `_TRANSPORT=kernel` journal metadata; shutdown absence requires a reliably collected tail; current inventory is never presented as crash-time data; artifact corroboration requires a confirmed boot association. Full contract: [04-diagnostics.md](04-diagnostics.md).
- **Privacy:** all analysis is local; reports are best-effort redacted before preview/export, and preview is mandatory; real logs, crash dumps, serials, hostnames, or screenshots are never committed and never transmitted to coding agents, AI APIs, or external services; automated verification uses synthetic fixtures only. The only persisted preference is the local appearance choice (`appearance/theme` via QSettings); no diagnostic data, journal content, artifacts, or identifiers are ever stored, and demo mode never writes real preferences.
- **Security:** never run as root, never invoke sudo, never modify journal configuration, groups, or system permissions; subprocesses use argv arrays, `shell=False`, timeouts, and bounded output; collection runs off the UI thread. Full contract: [02-architecture.md](02-architecture.md) and [AGENTS.md](../AGENTS.md).

## 7. UX requirements

Desktop-first for 1920×1080, usable at 1280×720. Five pages — Overview, Timeline, Evidence, System Information, Report — in a single window with a persistent boot selector, Analyze action, coverage status, and "Local only" footer. Dark (default) and Soft Light themes with a global sidebar switcher, immediate in-place switching, and local persistence of the appearance choice only; native widgets, no decorative imagery. Loading, empty, error, permission-denied, incomplete-evidence, tail-uncertain, cancelled, stale-results, and demo states are specified in [03-ui-ux.md](03-ui-ux.md).

## 8. v0.1.0 definition of done

- [ ] `PYTHONPATH=src .venv/bin/python -m syspanic` opens the five-page window; `--demo` runs end-to-end.
- [ ] Real collection works on the target Fedora KDE machine for at least the current boot; inaccessible sources degrade visibly.
- [ ] All 27 core rules (the 29-rule catalog minus deferred ART-002/ART-003 classification) have positive and negative unit tests; artifact collection and listing for vmcore/pstore remain tested; demo integration matches the core expected findings. Deferred rules are explicitly tracked, never silently removed.
- [ ] Sanitizer tests cover hostname-as-IP, home paths, serials, UUIDs, credential patterns, tokens, and connection strings; the report states redaction is best-effort; exported report contains no known PII.
- [ ] `ruff check .` and `pytest -q` pass; offscreen GUI smoke passes. Agents never launch the real GUI; manual GUI execution is user-only.
- [ ] Manual GUI QA script in [05-implementation-plan.md](05-implementation-plan.md) is completed by the user.
- [ ] Implementation is reported as `IMPLEMENTED_UNVERIFIED` until that QA completes.

## 9. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| System journal unreadable by the user | No evidence for some boots | Surface `permission_denied` with neutral guidance; never request elevation; demo mode remains usable |
| Journal is volatile or rotated | Previous boot missing or partial | Coverage state + "no previous boots" copy; derive boot windows from collected entries, not list metadata |
| `dmesg` restricted (`kernel.dmesg_restrict=1`) | One corroborating source lost | Kernel journal slice is primary; dmesg is optional, current-boot-only, and marked unavailable/unsupported as appropriate |
| Absence-based rules produce false alarms | Misleading incident narrative | Restrict to completed boots with a reliably collected journal tail; suppress SHD-002 when the tail is uncertain; label strength `circumstantial` |
| Truncated or rate-limited kernel logs | Missed early events | Distinguish head truncation from tail loss; never claim "no errors occurred"; findings cite only observed lines |
| Artifact timestamp misassociation | Old dump falsely corroborates current incident | Require matched association (proven boot identity: boot ID or stronger incident identity); timestamp proximity + kernel release alone is only possibly_related; mtime alone is insufficient; corroborate only with matched artifacts |
| Credential redaction miss | Secret exposure in an exported report | Best-effort credential patterns plus mandatory preview and explicit wording; never transmit real logs to agents or external services |
| pstore/vmcore permissions | Crash evidence missing | Treat as coverage, not health; list what is inaccessible |
| One-day MVP overrun | Incomplete polish | Core 27-rule pipeline first; ART-002/ART-003 classification and artifact corroboration deferred; stretch features ordered in [05-implementation-plan.md](05-implementation-plan.md) |

## 10. Post-MVP (explicitly not v0.1.0)

Import of externally supplied logs, `.desktop` launcher and icon, live monitoring, historical sensor collection, binary vmcore analysis, kdump setup assistance, distribution packaging (Flatpak/RPM), localization, and report themes.
