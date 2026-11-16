# SysPanic

> Don't panic. Diagnose.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB.svg)](pyproject.toml)
[![PySide6: 6.12](https://img.shields.io/badge/PySide6-6.12-41CD52.svg)](requirements.txt)
[![Status: early development](https://img.shields.io/badge/Status-early%20development-orange.svg)](docs/implementation-tracker.md)

Local-only, evidence-cited Linux crash diagnostics. SysPanic turns the journal and crash
evidence already on your machine into a deterministic incident report that says what the logs
show, what they suggest, and what remains unknown — without uploading data, escalating
privileges, or pretending to diagnose hardware it cannot test.

## Project status

**Early development — v0.1.0 in progress.** The runnable desktop shell (milestone **M0**) is
implemented: a five-page window with designed idle/empty states and two themes — Dark (default)
and Soft Light — switched globally from the sidebar and remembered between sessions. The
dual-theme refinement passed manual visual QA (2026-11-16); M0 is verified. The
diagnostic engine, collectors, timeline, evidence rendering, sanitization, and report export
are **not yet implemented**. The boot selector and **Analyze** button are disabled placeholders,
and `--demo` currently shows a persistent demo banner over those placeholder pages (packaged
synthetic fixtures and an end-to-end demo arrive in **M5**).

See the [implementation tracker](docs/implementation-tracker.md) for the authoritative progress
record and the [roadmap](#roadmap) below for what comes next. Nothing here presents fake
findings, hardware readings, or analysis results.

## What is SysPanic?

After an unexpected reboot, freeze, GPU hang, or kernel panic, the evidence is on your machine
but hard to read: the journal is verbose, sometimes unreadable, and easy to misread. A missing
shutdown marker looks like power loss, an AMDGPU reset looks like a dead GPU, and a corrected
PCIe error looks like a failing motherboard. Existing crash tooling targets kernel developers
and dump files, not the person who just wants to know what happened.

SysPanic converts locally available journal entries and crash artifacts into a deterministic,
evidence-cited incident report. Every finding cites real source lines and separates three
things:

- **Observed fact** — what the logs actually show.
- **Suspected cause** — an interpretation, always labeled as unconfirmed.
- **Unknown** — what the logs cannot determine.

It reports coverage honestly: missing, truncated, denied, or malformed sources are displayed as
gaps, never treated as health. It does not claim a component is defective, infer power-supply
failure, or show confidence percentages.

## Who it's for

| Persona | Situation | What they get |
|---|---|---|
| Fedora KDE user | Desktop rebooted or froze unexpectedly | A plain-language answer, the exact log lines, and next steps |
| Developer / homelab operator | Intermittent GPU hangs or I/O errors | A chronological incident view and a report attachable to a bug tracker |
| Support engineer | Helping someone else remotely | A redacted Markdown report with coverage gaps stated |

Daily operation is **non-root**. A user who cannot read the system journal is still a supported
user: SysPanic explains the gap rather than working around it.

## Privacy and security

SysPanic is built to be safe to run on a personal machine:

- **Local only.** No network, no telemetry, no cloud, no AI APIs, no external uploads. Analysis
  never leaves your machine.
- **Read-only.** The only disk write is a report you explicitly choose to save. No temp files,
  no log persistence, no system configuration changes.
- **Never root.** No `sudo`, no privilege escalation, no polkit, no journal/group/permission
  changes. Read access is whatever your user already has; denial is a first-class, explained
  state.
- **Least-privilege collection.** Subprocesses use argv arrays with `shell=False`, explicit
  timeouts, bounded output, and cancellation. Only allowlisted paths are read. Artifact scans
  never follow symlinks and **never open binary `vmcore`** — metadata only. `/proc/cmdline`,
  DMI serials, product UUIDs, chassis serials, and `/etc/machine-id` are never read.
- **Best-effort redaction (report pipeline, M7–M8).** Exported reports are sanitized to remove
  hostname, username, home paths, IP, MAC, email, serials, UUIDs, and machine IDs; common
  credential patterns become `CRED_n`. Redaction is **best-effort, not a guarantee**, and a
  preview is mandatory before any copy or save. Boot IDs are retained by design and disclosed.
- **Untrusted log text.** Evidence is shown in plain-text widgets (no HTML/rich text), control
  characters are stripped, and Markdown excerpts are fenced.

Full contracts: [architecture §10–11](docs/02-architecture.md) and
[diagnostics](docs/04-diagnostics.md).

## The five pages

One screen per question, in a single window:

| Page | Question | Content |
|---|---|---|
| **Overview** | What happened? | Incident summary, severity counts, findings with evidence, coverage strip, crash artifacts, next steps |
| **Timeline** | When? | Chronological key events: boot boundaries, shutdown markers, first occurrence per finding |
| **Evidence** | What is the proof? | The exact normalized lines behind every finding, with per-source coverage states |
| **System Information** | What context applies? | OS/kernel, CPU, memory, GPUs, firmware/board — always labeled "collected now", never crash-time |
| **Report** | What can I share? | A sanitized Markdown report with bounded excerpts, coverage, limitations, and a redaction summary |

The shell currently shows designed idle/empty states for each page; real content lands with the
collection and GUI-integration milestones (M3–M8).

## Requirements

- **Linux desktop**, Fedora KDE first (Wayland). systemd journal assumed.
- **Python ≥ 3.12** (verified on 3.14.10).
- **PySide6 6.12.0** (Qt Widgets — only `QtCore`, `QtGui`, `QtWidgets` are imported). The PySide6
  meta-package also pulls the Pdf and WebEngine wheels, but SysPanic does not use them.
- `journalctl` readable by your user is optional — inaccessible sources degrade visibly rather
  than failing. No root required.

## Quick start

Run from source; no installation is required.

```bash
git clone https://github.com/utrodus/syspanic.git
cd syspanic
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
PYTHONPATH=src .venv/bin/python -m syspanic
```

- **Demo mode** (synthetic data, no system probing):

  ```bash
  PYTHONPATH=src .venv/bin/python -m syspanic --demo
  ```

  Until M5 this shows the demo banner over the placeholder pages.

- **Version** (Qt-free):

  ```bash
  PYTHONPATH=src .venv/bin/python -m syspanic --version
  ```

- **Optional editable install** (when network is available):

  ```bash
  .venv/bin/pip install -e ".[dev]"
  ```

  The build backend is hatchling. If it cannot be downloaded, keep the `PYTHONPATH` commands
  above — they are the supported source-run path.

`requirements.txt` pins the complete environment (including pytest transitives) for
reproducibility; `pyproject.toml` remains the package metadata source.

## Keyboard shortcuts

| Shortcut | Action | Availability |
|---|---|---|
| Ctrl+1 … Ctrl+5 | Switch page | Active now |
| Ctrl+R | Analyze / retry | With collection (M8) |
| Ctrl+E | Export report | With report export (M8) |
| F5 | Refresh boot list | With boot enumeration (M3) |
| Esc | Cancel collection | With collection (M8) |

Changing the boot selector never starts analysis automatically; Analyze is single-flight.

## Limitations (v0.1.0 non-goals)

Out of scope for v0.1.0: real-time/background monitoring or a daemon, hardware stress testing,
automatic repair or kdump setup, binary `vmcore` parsing, AI/cloud services, authentication,
telemetry, a database, plugin architecture, `.desktop`/distribution packaging, and localization.
SysPanic reads and explains evidence; it does not repair your system.

## Roadmap

Milestones are implemented in strict order; each ends with its tests passing and lint clean.
Status is recorded in the [tracker](docs/implementation-tracker.md).

| Milestone | Scope | Status |
|---|---|---|
| M0 | Runnable desktop shell | Verified |
| M1 | Domain model + `validate_report()` | Implemented |
| M2 | Safe bounded command runner | Planned |
| M3 | Boot enumeration + journal collection | Planned |
| M4 | System profile + crash artifacts | Planned |
| M5 | Demo fixtures + demo collector | Planned |
| M6 | Diagnostic engine (27 core rules) | Planned |
| M7 | Sanitization + Markdown report | Planned |
| M8 | GUI integration | Planned |
| M9 | Hardening + release candidate | Planned |

The rule catalog has 29 IDs; the v0.1.0 release-blocking core is 27, with ART-002/ART-003
classification deferred and tracked. Details: [implementation plan](docs/05-implementation-plan.md).

## Documentation

- [Product requirements](docs/01-prd.md)
- [Architecture](docs/02-architecture.md)
- [UI/UX specification](docs/03-ui-ux.md)
- [Diagnostics](docs/04-diagnostics.md)
- [Implementation plan](docs/05-implementation-plan.md)
- [Implementation tracker](docs/implementation-tracker.md)
- [Working rules (AGENTS.md)](AGENTS.md)

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) first — it covers
environment setup, the source-of-truth workflow, milestone gates, verification commands,
diagnostic-accuracy rules, and the commit policy. Highlights:

- **Conventional Commits** for every commit.
- **Synthetic fixtures only** — never commit or transmit real host logs, crash dumps, or
  screenshots with identifiers.
- **No new runtime dependency without approval**; dev tools are pytest and ruff only.
- Repository writes (commit/push/tag/release) require explicit maintainer approval.

## License

[MIT](LICENSE) © 2026 Utrodus Said Al Baqi