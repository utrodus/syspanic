# SysPanic — Diagnostics Specification (v0.1.0)

**Status:** Approved source of truth · 2026-11-16
**Model:** deterministic rules over collected evidence. No AI, no statistical scoring, no binary dump parsing, no live sensors.
**Catalog:** 29 rules in 10 families; 27-rule core is release-blocking, with ART-002/ART-003 classification and artifact corroboration deferred (artifact collection remains mandatory). The GPU family is split into GPU-001 timeout, GPU-002 reset, GPU-003 VM fault, and GPU-004 Xid; the former BOT-002 reboot-correlation content is folded into BOT-001 and SHD-001, keeping the catalog at 29 IDs. Both rebalances are approved (2026-11-16).

## 1. Boundaries

SysPanic reads what the system already recorded: journal entries for one boot, optional `dmesg`, and accessible crash artifacts. It does not observe the crash, measure sensors, reproduce the fault, or inspect a vmcore. Every statement must therefore be traceable to a line of evidence or explicitly marked as unknown.

The engine is a pure function of a `CollectionBundle`: identical input yields identical findings, ordering, and wording. No rule may use wall-clock time, randomness, locale-dependent formatting, or network data.

## 2. Evidence model

- Each normalized journal entry is an `EvidenceItem` (`JRN-*`), `dmesg` line is `DMS-*`, pstore text is `PST-*`, and `vmcore-dmesg.txt` text is `VMD-*`. Boot records are `BTM-*` metadata and artifact records are `AFM-*` metadata; both are resolvable evidence, never content.
- A `Finding` must contain at least one `EvidenceRef` (`evidence_id` + excerpt). `validate_report()` rejects findings without resolvable references.
- Findings separate four fields: **observed evidence** (`evidence`), **interpretation** (deterministic explanation), **suspected causes** (candidate mechanisms, each explicitly unconfirmed), and **unknowns** (what the logs cannot establish).
- Evidence excerpts are bounded: at most 3 references per finding and at most 3 lines / 300 characters per reference. The interpretation states the total match count when more exist.
- Artifact metadata (path, size, mtime, association) is evidence of presence and association only, never of content. Binary `vmcore` is never opened.
- Journal `EvidenceItem`s retain the boot ID (`_BOOT_ID`) and the provenance metadata needed by the rules (`_TRANSPORT`, `_COMM`, `_EXE`, `_SYSTEMD_UNIT`, `SYSLOG_IDENTIFIER` when present) so provenance checks are reproducible from evidence.

## 3. Accuracy contract

1. No finding without source evidence.
2. Never claim a component is defective, failing, or the cause of the incident based on kernel logs. Report observed errors and candidate mechanisms.
3. Never infer PSU or power-supply failure. Missing shutdown markers cannot distinguish power loss from hard reset, hang, watchdog, firmware reset, or journal flush loss.
4. Missing or unreadable logs are not evidence of health. The report must state what was unavailable.
5. Absence-based findings are allowed only for completed, non-current boots with non-empty journal sources whose tails were reliably collected; they use `circumstantial` strength and list alternatives.
6. Current hardware inventory, firmware fields, and any current counters are labeled "collected now" and never presented as crash-time measurements.
7. No confidence percentages or scores. Severity expresses potential impact; strength expresses evidence directness.
8. Do not equate a panic trigger (for example, an amdgpu fault) with a root cause (for example, hardware failure, driver bug, or memory corruption).
9. Truncated or rate-limited logs may hide events; never claim "no errors occurred."
10. A shutdown-sequence marker does not prove the boot was error-free, and `Journal stopped` alone does not prove a clean system shutdown.
11. Artifact corroboration requires a `matched` boot association; unverified or unrelated dumps never upgrade strength.

## 4. Severity and evidence strength

| Severity | Meaning |
|---|---|
| **Critical** | Boot-terminating event, uncorrectable hardware error, or crash artifact indicating a kernel crash |
| **Warning** | Recoverable error or degraded subsystem; may be transient |
| **Notice** | Corrected error, noteworthy state change, or forced administrator action |
| **Info** | Context, transitions, taint, or clean-shutdown evidence |

| Strength | Definition |
|---|---|
| **circumstantial** | Inferred from absence or sequence; alternatives must be stated |
| **direct** | Explicit kernel/driver message or artifact content |
| **corroborated** | Direct evidence confirmed by an independent source (journal + artifact, or MCE + EDAC) |

Strength upgrades are limited to the table in §7. Severity is never upgraded by strength.

## 5. Shutdown detection

**Terminal markers (observations, not proof of a clean system shutdown):**

- `systemd-shutdown[...]: Powering off.` or `systemd-shutdown[...]: Rebooting.` — orderly systemd shutdown/reboot marker.
- `reboot: Power down` or `reboot: Restarting system` — kernel reboot/power-down marker.
- `kexec_core: Starting new kernel` — an orderly kexec transition, not a power cycle.
- `Journal stopped` — journald stopped; by itself it does **not** prove a clean kernel/system shutdown.

Markers are accepted only with trusted source metadata: kernel signatures require `_TRANSPORT=kernel`; `SYSLOG_IDENTIFIER=kernel` alone is sender-controlled and is **not** trusted provenance. systemd-shutdown markers require trusted process/unit metadata (`_SYSTEMD_UNIT=systemd-shutdown.service`, or `_COMM`/`_EXE` identifying the systemd-shutdown binary); `Journal stopped` requires `_SYSTEMD_UNIT=systemd-journald.service` or `_COMM=systemd-journal` (the 15-character comm truncation of `systemd-journald`). User-space messages that merely contain marker text, or spoof `SYSLOG_IDENTIFIER`, are ignored.

**Algorithm:**

1. Use the merged journal for the selected boot, sorted by timestamp.
2. Determine tail reliability. Both `journal.kernel` and `journal.system` must be non-empty, in `available` or `truncated` state, and have `tail_reliable=True`. Byte-cap termination, timeout, cancellation, permission denial, non-zero exit, or collection failure makes the tail unreliable.
3. If the tail is unreliable, suppress `SHD-002` entirely and record a coverage limitation: shutdown absence could not be assessed. Head truncation alone does not suppress it.
4. Inspect the final 20 entries (or all if fewer).
5. Any trusted marker → `SHD-001` (Info). Distinguish marker quality: systemd/kernel shutdown markers support an orderly shutdown or reboot sequence; `kexec` supports an orderly kexec transition; `Journal stopped` alone records only journald stopping. Two or more distinct trusted marker families → strength `corroborated`.
6. No marker, boot is **not current**, both journal tails are reliable, both sources are non-empty, and ≥20 entries exist → `SHD-002` (Warning, `circumstantial`).
7. Never apply absence logic to the current boot: it has not ended.

**Caveats that must appear in `SHD-002` interpretation:** a hard reset, hang, watchdog reset, firmware reset, power loss, journal flush failure, or journal corruption can all produce the same absence. `SHD-001` does not prove the boot was error-free; `Journal stopped` alone does not prove the system shut down cleanly.

## 6. Rule catalog

Rules emit one finding per rule per boot. Patterns match normalized message text and tolerate representative kernel prefixes, for example `amdgpu 0000:0a:00.0: amdgpu: ring …` or `amdgpu 0000:0a:00.0: ring …`. Journal sources are `journal.system` + `journal.kernel` unless stated. All next steps are suggestions, not automatic actions.

**Trusted journal metadata (kernel-only signatures):**

| Signature class | Required metadata |
|---|---|
| Kernel/driver messages (PNC, MCE, GPU, EDAC, AER, storage, thermal, taint, `reboot:`) | `_TRANSPORT=kernel`; the `dmesg` source is accepted as kernel provenance for the current boot only (§9) |
| systemd shutdown markers | `_SYSTEMD_UNIT=systemd-shutdown.service`, or `_COMM`/`_EXE` identifying the systemd-shutdown binary |
| `Journal stopped` | `_SYSTEMD_UNIT=systemd-journald.service` or `_COMM=systemd-journal` |

`_TRANSPORT`, `_COMM`, `_EXE`, and `_SYSTEMD_UNIT` are journald-generated (trusted) metadata; `SYSLOG_IDENTIFIER` is sender-controlled and spoofable, and message text is untrusted. A user-space process that prints "Kernel panic" or "amdgpu: ring timeout" — including one that sets `SYSLOG_IDENTIFIER=kernel` — without `_TRANSPORT=kernel` must not trigger these rules. Spoofed-identifier cases require negative tests. Artifact text is evaluated only by ART rules and is labeled as artifact content.

### 6.1 Shutdown and boot (SHD, BOT)

| ID | Trigger | Sev / strength | Conditions and interpretation | Next steps |
|---|---|---|---|---|
| **SHD-001** | Trusted `systemd-shutdown` with `Powering off.`/`Rebooting.`; `reboot: Power down`/`Restarting system`; `kexec_core: Starting new kernel`; or trusted `Journal stopped` | Info / direct | A shutdown-sequence marker exists. Systemd/kernel markers support an orderly shutdown or reboot; kexec supports an orderly transition; `Journal stopped` alone records only journald stopping and is not proof of a clean system shutdown. Earlier errors may still exist. | No action. If an incident followed, analyze the next boot. |
| **SHD-002** | No trusted terminal marker in the final 20 entries | Warning / circumstantial | Only for a completed, non-current boot with both journal tails reliably collected, both sources non-empty, and ≥20 entries. Suppress when tail coverage is uncertain. State all alternative explanations from §5; never state that power was lost. | Review the final entries on Evidence; check `ART-*` findings; confirm whether the journal is persistent. |
| **SHD-003** | `EXT4-fs` + `recovery` or `orphan`; `BTRFS` + `replay` or `recovery`; `XFS` + `log recovery` | Notice / direct | A filesystem was mounted after an unclean stop. The recovery message often appears in the boot *after* the stop, so it may refer to a different boot than the one selected. | Back up important data; correlate with the prior boot's `SHD-002`; run filesystem checks manually if errors persist. |
| **SHD-004** | `Remounting filesystem read-only`; `Emergency Remount R/O`; `BTRFS info` + `forced readonly` | Warning / direct | The kernel forced read-only mode in response to an error. Treat as a consequence; find the preceding cause. | Inspect entries immediately before the remount; correlate `STO-*`; back up data. |
| **BOT-001** | Boot list contains a boot indexed after the selected boot | Info / direct | The selected boot is historical and was followed by another boot. Provides orientation, not a fault claim. | Select and analyze the later boot for aftermath. |

### 6.2 Panic and kernel faults (PNC)

| ID | Trigger | Sev / strength | Conditions and interpretation | Next steps |
|---|---|---|---|---|
| **PNC-001** | Kernel-provenance `Kernel panic - not syncing`; `Kernel panic` | Critical / direct | The kernel halted. The panic string identifies a trigger at most, not a root cause. Upgraded to `corroborated` only by a `matched` ART-002/ART-003 panic signature when the deferred artifact rules are implemented. | Preserve the report and any dump; inspect findings immediately preceding the panic; report upstream with kernel version and reproduction details. |
| **PNC-002** | Kernel-provenance `Oops:`; `BUG: unable to handle kernel`; `general protection fault`; `kernel BUG at`; `invalid opcode:` | Warning / direct | An oops may recover or precede a panic. A function or module in the trace is a lead, not a verdict. Upgraded to `corroborated` only by a `matched` ART-002 oops signature when the deferred artifact rules are implemented. | Identify the function/module; correlate GPU, MCE, EDAC, and storage findings; report upstream if reproducible. |
| **PNC-003** | `watchdog: BUG: soft lockup`; `hard LOCKUP`; `rcu_` + `detected stalls`; `blocked for more than` + `seconds` | Warning / direct | A CPU or task stopped making progress; often precedes a watchdog reset. Possible causes include driver deadlock, overload, storage stall, or hardware. | Inspect stack traces; correlate thermal, MCE, and storage; note reproducibility. |
| **PNC-004** | `sysrq: SysRq :` except `Emergency Remount R/O` | Notice / direct | An administrator or watchdog invoked SysRq. This is an action, not evidence of a hardware fault. | Confirm who/what triggered it; review preceding events. |

### 6.3 CPU and machine checks (MCE)

| ID | Trigger | Sev / strength | Conditions and interpretation | Next steps |
|---|---|---|---|---|
| **MCE-001** | Kernel-provenance `mce: [Hardware Error]` or `Machine Check` containing `Uncorrected`, `UE`, or `Fatal` | Critical / direct | An explicitly uncorrected machine check was reported. Possible sources include CPU, cache, memory, interconnect, or firmware; the log cannot localize it. Upgraded to `corroborated` only with a separate `MEM-002` evidence item. | Preserve evidence; check firmware and microcode versions; use vendor diagnostics externally; correlate EDAC findings. |
| **MCE-002** | Kernel-provenance `mce: [Hardware Error]` or `Machine check events logged` with explicit `Corrected`/`CE`, or without any correctability token (including `Machine Check Exception`) | Warning if explicitly corrected; Notice if correctability is not stated / direct | A machine check was logged. When correctability is unspecified, the interpretation must say so; do not place unknown events in the uncorrected category. Frequency and bank matter; one event is not a defect verdict. | Note frequency and bank; check firmware/microcode; escalate if events recur. |

### 6.4 GPU (GPU)

| ID | Trigger | Sev / strength | Conditions and interpretation | Next steps |
|---|---|---|---|---|
| **GPU-001** | Kernel-provenance `amdgpu` with `ring` + `timeout`, or `drm:amdgpu_job_timedout`; tolerant of an `amdgpu <PCI address>:` prefix | Warning / direct | The AMDGPU driver reported unresponsive work. This is a timeout observation only; it does not by itself say whether a reset followed. Cause could be the driver, workload, power, thermal, or hardware. | Note the workload and time; correlate reset, thermal, MCE, and PCIe findings; test another kernel or driver; report upstream. |
| **GPU-002** | Kernel-provenance `amdgpu` + `GPU reset begin`, `GPU reset(`, `GPU reset end`, or `reset succeeded`; tolerant of an `amdgpu <PCI address>:` prefix | Warning / direct | The driver attempted or completed a GPU reset. Report whether the message indicates success, failure, or only an attempt; do not merge this observation into the timeout finding. | Correlate `GPU-001`; note reset count and outcome; test another kernel or driver; report upstream. |
| **GPU-003** | Kernel-provenance `amdgpu: VM fault`, `GPU fault detected`, `IH ring`, or `retry page fault`; tolerant of an `amdgpu <PCI address>:` prefix | Warning / direct | The GPU accessed invalid memory. Often follows a hang; possible driver bug or memory corruption. | Correlate `GPU-001`/`GPU-002`, MCE, and EDAC; note kernel version and reproducibility. |
| **GPU-004** | Kernel-provenance `NVRM: Xid (PCI:<address>): <code>` — regex `NVRM: Xid \(PCI:[0-9a-fA-F:.]+\): (\d+)` | Warning; **Xid 79 → Critical** / direct | The NVIDIA driver reported Xid code `<code>`. Meanings vary by code; 79 indicates the GPU fell off the bus. No defect claim. | Record the code and driver version; correlate thermal/power/PCIe; use vendor support for code-specific guidance. |

### 6.5 Memory and EDAC (MEM)

| ID | Trigger | Sev / strength | Conditions and interpretation | Next steps |
|---|---|---|---|---|
| **MEM-001** | Kernel-provenance `EDAC` with explicit `CE` or `corrected` | Warning / direct | The memory controller reported corrected errors. Corrected errors are not automatically a fault; frequency, bank, and rank matter. | Note counts; monitor recurrence; check firmware; run vendor memory diagnostics if errors repeat. |
| **MEM-002** | Kernel-provenance `EDAC` with explicit `UE`, `uncorrected`, or `Fatal` | Critical / direct | An uncorrectable memory error occurred; data integrity is at risk. Possible sources include DIMM, controller, or bus. Upgraded to `corroborated` only with a separate `MCE-001` evidence item. | Back up data; run vendor memory diagnostics externally; correlate machine-check findings. |

**MCE/EDAC classification precedence:** a line with `mce:`/`Machine Check` is classified only by MCE rules; a line with `EDAC` is classified only by MEM rules. If one line contains both, the leading marker decides (`mce:` → MCE, `EDAC` → MEM), and the line contributes to at most one side. Corroboration requires separate evidence items, never the same line. EDAC lines without an explicit CE/UE token produce no MEM finding and remain visible as evidence; unknown correctability is never forced into corrected or uncorrected.

### 6.6 PCIe and AER (PCI)

| ID | Trigger | Sev / strength | Conditions and interpretation | Next steps |
|---|---|---|---|---|
| **PCI-001** | `AER: Corrected error`; `AER` + `corrected` | Notice / direct | A corrected PCIe error occurred; often transient. Repeated errors may suggest signal integrity or firmware issues. | Count occurrences; check firmware; no immediate action unless frequent. |
| **PCI-002** | `AER: Uncorrected (Non-Fatal)` → Warning; `AER: Uncorrected (Fatal)` → Critical | direct | An uncorrected PCIe error occurred; the device may have been reset or taken offline. | Identify the device and slot; check power/riser/firmware; correlate link resets. |
| **PCI-003** | Kernel-provenance `pcieport` with `Link Down`, `link down`, `slot reset`, `bus reset`, or an explicit `pcieport` reset message | Warning / direct | A PCIe link-down or reset transition was reported. `PCIe Bus Error` alone is **not** a link reset and must not trigger this rule; classify it only through PCI-001/PCI-002 when severity tokens are present, otherwise leave it as evidence. | Correlate `PCI-*` findings; check whether the device is still present. |

### 6.7 Storage (STO)

| ID | Trigger | Sev / strength | Conditions and interpretation | Next steps |
|---|---|---|---|---|
| **STO-001** | `I/O error, dev`; `critical medium error`; `Medium Error`; `blk_update_request: I/O error` | Warning / direct | The block layer reported an I/O failure. Possible causes include device, cable, controller, or filesystem. | Back up data; check SMART externally; inspect the named device. |
| **STO-002** | `nvme` + `I/O` + `timeout`; `nvme` + `controller is down`; `nvme` + `resetting controller`; `nvme` + `Abort status` | Warning / direct | An NVMe controller timed out or reset. Causes include firmware, thermal, power, or device issues. | Check SMART externally; update firmware; correlate thermal and PCIe findings. |
| **STO-003** | `EXT4-fs error`; `BTRFS error`; `XFS` + `error`; `XFS` + `corruption` | Warning / direct | A filesystem detected an inconsistency, often as a consequence of I/O errors or an unclean stop. | Back up data; run filesystem checks manually when appropriate; correlate storage findings. |

### 6.8 Thermal (THM)

| ID | Trigger | Sev / strength | Conditions and interpretation | Next steps |
|---|---|---|---|---|
| **THM-001** | `temperature above threshold`; `cpu clock throttled`; `thermal` + `throttl`; `package_throttled` | Warning / direct | Thermal or power throttling occurred. Cooling, workload, or policy may be responsible; this is not a defect claim. | Inspect cooling and airflow; review workload; check thermal policy. |
| **THM-002** | `critical temperature reached`; `thermal shutdown`; `Critical temperature` | Critical / direct | Thermal protection triggered and may have caused the shutdown. | Clean/inspect cooling and fans; review firmware thermal settings manually; correlate throttling events. |

### 6.9 Crash artifacts (ART)

Artifact association is assessed per artifact:

- **matched** — proven boot association: the artifact text/metadata contains the selected boot ID, or another stronger incident identity is established. Timestamp proximity plus a matching kernel release alone is **not** sufficient.
- **possibly_related** — the kdump incident timestamp falls within the selected boot's observed window plus a 5-minute margin and the kernel release matches, or mtime is near the boot window, or only one correlation is available — without proven boot identity.
- **unknown** — no usable correlation, unreadable metadata, or outside the window.

Mtime alone yields at most `possibly_related`; it never yields `matched`. Timestamp proximity plus kernel release also yields at most `possibly_related` unless stronger incident identity is established. Only `matched` artifacts may corroborate a finding. `/var/crash` inspection is bounded to its root plus immediate kdump incident subdirectories (no deeper recursion); symlinks and non-regular files are rejected; binary `vmcore` is never opened. ART-001 is core; ART-002/ART-003 classification is deferred, but their source files are still collected and listed.

| ID | Trigger | Sev / strength | Conditions and interpretation | Next steps |
|---|---|---|---|---|
| **ART-001** | Allowlisted `/var/crash` vmcore (root or immediate incident subdirectory) | Critical if matched; Warning if possibly related; Notice if unknown / direct | A crash dump exists. Only name, size, mtime, and association are read; binary contents are not analyzed. Association reason must be shown. | Preserve the dump; compare with the boot window; use dedicated crash tooling externally. |
| **ART-002** | Readable `vmcore-dmesg.txt` containing `Kernel panic`, `Oops:`, `BUG:`, or `general protection fault` (deferred) | Critical if matched; Warning if possibly related; Notice if unknown / direct | Captured kernel log contains a crash signature. Only a `matched` artifact may upgrade `PNC-001`/`PNC-002`; otherwise state the association limitation. | Preserve; include the excerpt; use external crash tooling. |
| **ART-003** | Accessible pstore text record containing panic/oops/backtrace markers (deferred) | Critical if matched; Warning if possibly related; Notice if unknown / direct | A firmware-persisted crash record exists. Only a `matched` record may upgrade `PNC-001`; otherwise do not imply it belongs to the selected boot. | Preserve the record; include association; compare timestamps. |

### 6.10 Kernel health (KRN)

| ID | Trigger | Sev / strength | Conditions and interpretation | Next steps |
|---|---|---|---|---|
| **KRN-001** | Kernel-provenance `Tainted:` | Info / direct | Parse the fixed taint string and report active flags: `P` proprietary module, `O` out-of-tree, `E` unsigned, `W` warning, `D` died, `B` bad page, `C` staging, `M` machine check, `L` soft lockup. `G` is the untainted placeholder for the proprietary-module slot (GPL-compatible state), **not** "GPL-only symbol" and not an adverse taint; do not report it as a flag. Informational; does not assert a fault. | Note the active flags; correlate with related findings. |

## 7. Corroboration and aggregation

| Primary finding | Independent corroboration | Result |
|---|---|---|
| `PNC-001` | `ART-002` or `ART-003` panic signature with `matched` association | strength → `corroborated` |
| `PNC-002` | `ART-002` oops signature with `matched` association | strength → `corroborated` |
| `MCE-001` | `MEM-002` from a separate evidence item | strength → `corroborated` |
| `SHD-001` | ≥2 distinct trusted terminal marker families | strength → `corroborated` |

- No other upgrades. Corroboration never changes severity.
- ART-002/ART-003 classification and artifact corroboration are deferred in v0.1.0; until implemented, artifact presence never upgrades a journal finding. When implemented, only `matched` artifacts qualify; `possibly_related` and `unknown` never do.
- MCE/EDAC corroboration requires separate lines; one line is classified on one side only.
- `Journal stopped` alone does not corroborate an orderly system shutdown; it corroborates only that journald stopped.
- One finding per rule per boot; up to 3 evidence references; the interpretation reports the total match count.
- Findings sort by severity (`Critical`, `Warning`, `Notice`, `Info`) then rule ID.
- Overlapping rules are allowed only when claims differ (`PNC-001` and `PNC-002`; `SHD-002` and `PNC-001`; `GPU-001` and `GPU-002`). Interpretation text must cross-reference rather than restate.

## 8. Timeline derivation

- Kinds: `boot_start`, `boot_end`, `rule_match` (first occurrence per rule), `shutdown_marker`, `transition`.
- Timestamps come from journal evidence; boot boundaries reference `BTM-*` metadata and rule events reference `JRN-*`. Artifact mtimes are not placed on the timeline because association may be unverified.
- Sorted ascending; deduplicated by `(timestamp, kind, evidence_id)`; capped at 200 events with a visible truncation note.
- No current hardware or sensor data is ever added to the timeline.

## 9. Coverage semantics

| State | Meaning | Absence logic allowed |
|---|---|---|
| `available` | Source read successfully | Yes, tail-based only when `tail_reliable=True` |
| `empty` | Source read, no entries | No |
| `truncated` | Bounded read hit the entry cap after a clean exit; head truncated, tail retained | Tail-based only; `SHD-002` additionally requires both journal tails reliable |
| `permission_denied` | Access refused | No; tail is unreliable |
| `not_found` | Command or path missing | No |
| `unsupported` | Source not applicable (for example, pstore not mounted; `dmesg` for a historical boot) | No |
| `timeout` | Read exceeded its deadline | No; tail is incomplete |
| `error` | Other failure | No; tail is incomplete |

- `head_truncated` and `tail_reliable` are per-source fields. Head truncation limits early-boot claims but does not invalidate a terminal marker actually observed. Byte-cap termination, timeout, cancellation, permission denial, non-zero exit, or collection failure sets `tail_reliable=False` and suppresses `SHD-002`.
- **Boot isolation:** `dmesg` exposes only the current boot's kernel ring buffer. Collect and analyze it only when the selected boot is current; for historical boots mark `dmesg` coverage `unsupported` with the explanation that dmesg cannot provide historical-boot evidence. Current-boot kernel evidence is never mixed into a historical incident.
- **Required sources:** `journal.system` and `journal.kernel`. `journal.boots` is required for boot selection. All others are optional.
- Overall completeness: `complete` (all required available), `partial` (journal available, something missing), `minimal` (journal unavailable).
- Every attempted source appears once in coverage. A missing source never implies a healthy subsystem; reports state: "This source was unavailable, so related events could not be assessed." When a journal tail is unreliable, reports state: "The journal tail was not reliably collected; shutdown-sequence absence could not be assessed."

## 10. Wording templates

| Context | Use | Avoid |
|---|---|---|
| Panic | "The kernel reported a panic at 08:27:41. The panic string names a trigger; it does not identify a root cause." | "The CPU crashed because of a hardware defect." |
| GPU | "The amdgpu driver reported a ring timeout. A reset attempt is reported separately when present." | "The GPU is broken." |
| EDAC | "The memory controller logged corrected errors." | "The RAM is failing." |
| AER | "PCIe corrected errors were reported." | "The motherboard is defective." |
| Shutdown marker | "A shutdown-sequence marker was observed in the retained tail." / "`Journal stopped` records only that journald stopped; it does not prove a clean system shutdown." | "The system shut down cleanly." |
| Missing shutdown marker | "No trusted shutdown-sequence messages were found in the reliably collected journal tail. A hard reset, hang, watchdog, firmware reset, journal flush failure, or power loss can produce this; the logs cannot distinguish them." | "The system lost power." / "The PSU failed." |
| Artifact association | "The dump is matched to this boot by boot ID" / "The dump is possibly related, not confirmed" / "The dump's boot association is unknown." | "The crash dump proves this incident." |
| Redaction | "Redaction is best-effort; review the preview before sharing." | "The report is safe to share." |
| No findings | "No supported crash signatures were found in the available evidence. This does not establish that the hardware is healthy." | "Everything is fine." |
| Current hardware | "CPU and GPU details were collected at 13:52, not at crash time." | "The GPU was at 80 °C during the crash." |
| Taint | "The kernel was tainted by an out-of-tree module (O); this is informational." | "The system is unstable because of a bad module." |

**Banned in user-facing strings:** `defective`, `broken`, `faulty`, `hardware failure`, `PSU failure`, `power supply failure`, `confirmed cause`, `100%`, `guaranteed`, `must replace`, `certainly`. A unit test scans rule and report strings for these terms.

**Excerpt rules:** at most 3 lines and 300 characters per line; preserve timestamp and identifier where present; render inside fenced code blocks in Markdown; never include full journal contents.

## 11. Report contract

Order: title + demo notice → metadata (app version, boot id8, boot window, generated at, timezone) → scope/limitations → summary → evidence coverage table → findings → timeline → system snapshot ("collected now") → crash artifacts with association → redaction summary → footer disclaimer.

- Each finding: severity, strength, rule ID, observation, excerpts, interpretation, suspected causes, unknowns, next steps, sources.
- No hostname, username, home path, IP, MAC, email, serial, DMI UUID, or machine ID. `/proc/cmdline` is never collected.
- Credential redaction is best-effort: common passwords, tokens, API keys, bearer tokens, `user:password@` URLs, and connection strings are replaced with `CRED_n`; the report states that unrecognized secrets may remain. Preview is mandatory before copy/save.
- Boot IDs are retained by design (random identifiers needed for correlation); this is stated in the redaction section.
- Artifacts show path, size, mtime, association, and association reason; binary content is never included.
- Target size < 100 KiB; timeline ≤ 200 rows; no raw log appendix; no binary content.

## 12. Demo fixtures and expected findings

Synthetic, sanitized, and packaged in `src/syspanic/demo_data/`. They intentionally include fake identifiers (`demo-host`, `demo`, `/home/demo`, `192.0.2.10`, `02:00:00:00:00:01`, `DEMO-SERIAL-0001`, example UUID, fake credential assignments) so the sanitizer is exercised. Artifact fixtures include association metadata; no real host data is used.

| Boot | ID | Scenario | Core expected rule IDs | Deferred expected |
|---|---|---|---|---|
| Current | `a1b2c3d4e5f60718293a4b5c6d7e8f90` | Live session after recoverable trouble: amdgpu ring timeout and successful reset, EDAC corrected error, corrected AER, thermal throttling, ext4 recovery, kernel taint | `SHD-003`, `GPU-001`, `GPU-002`, `MEM-001`, `PCI-001`, `THM-001`, `KRN-001` | none |
| Previous | `0f1e2d3c4b5a69788796a5b4c3d2e1f0` | GPU VM fault → oops → panic; no shutdown markers; vmcore metadata, matching `vmcore-dmesg.txt`, pstore oops record | `SHD-002`, `BOT-001`, `PNC-001`, `PNC-002`, `GPU-003`, `ART-001` | `ART-002`, `ART-003` |

`expected_findings.json` maps each boot ID to a `core` list and a `deferred` list. The integration test asserts exact set equality for the core list; deferred rules are asserted separately when implemented. Both demo journal slices are complete, non-empty, and `tail_reliable=True` with at least 20 entries so the historical boot can exercise `SHD-002`; a separate synthetic tail-unreliable fixture is used only in unit tests and must suppress `SHD-002`. The previous boot must **not** produce `SHD-001`, the current boot must **not** produce `SHD-002` or `BOT-001`, and only `matched` artifacts may corroborate. A deferred rule is never silently removed from the catalog.

**Representative positive and negative fixture requirements:**

| Area | Positive fixtures | Negative fixtures |
|---|---|---|
| Kernel provenance | `_TRANSPORT=kernel` with `amdgpu 0000:0a:00.0: ring gfx_0.0.0 timeout`; kernel AER, EDAC, MCE, taint lines | Identical text from a user-space process without kernel metadata → no kernel rule; spoofed `SYSLOG_IDENTIFIER=kernel` without `_TRANSPORT=kernel` → no kernel rule |
| GPU separation | Timeout-only line; reset-attempt line; both lines → `GPU-001` + `GPU-002` | Reset-only line → no `GPU-001`; timeout-only → no `GPU-002`; VM fault → `GPU-003` |
| MCE/EDAC | Explicit MCE UE, MCE CE, MCE unknown; EDAC CE and UE; separate MCE and EDAC lines for corroboration | One line containing both tokens classified once; EDAC without CE/UE → no MEM finding; unknown MCE → Notice, not uncorrected |
| PCIe | `pcieport` link-down/reset; AER corrected/non-fatal/fatal | `PCIe Bus Error` alone → no `PCI-003` |
| Taint | `Tainted: P O E` → active P/O/E; `Tainted: G` → no adverse flag | No taint line → no KRN-001 |
| Shutdown/tail | Trusted systemd marker; `Journal stopped` alone; head-truncated slice retaining a tail marker | Current boot no SHD-002; tail unreliable → SHD-002 suppressed; untrusted marker text ignored; `Journal stopped` alone not described as clean shutdown |
| Artifacts | Matched boot ID; possibly-related incident timestamp + kernel release; possibly-related mtime only; unknown old artifact; immediate kdump incident subdir | Nested/deeper directory ignored; artifact symlink rejected; `vmcore` never opened; mtime-only never `matched`; timestamp + kernel release alone never `matched`; unverified artifact never corroborates |
| Privacy/export | Fake credential assignments, tokens, and connection strings redacted to `CRED_n` | No `/proc/cmdline` collection; real host logs/dumps never used in tests |

## 13. Rule authoring checklist

- [ ] Trigger pattern is based on a real kernel/driver message format, tolerates documented prefixes, and is documented in the rule.
- [ ] Kernel-only signatures require `_TRANSPORT=kernel`; user-space lookalikes and spoofed `SYSLOG_IDENTIFIER` values are covered by negative tests.
- [ ] Minimum evidence and negative conditions are explicit; GPU timeout and reset are separate; MCE/EDAC precedence and PCIe Bus Error exclusion are enforced.
- [ ] Severity reflects impact; strength reflects directness; no percentages.
- [ ] Observation, interpretation, suspected causes, unknowns, and next steps are separate.
- [ ] Artifact rules carry matched/possibly-related/unknown association; only matched artifacts corroborate.
- [ ] Shutdown rules distinguish head truncation from tail loss; SHD-002 is suppressed when the tail is unreliable.
- [ ] No defect, power-loss, or certainty claims; banned phrases absent.
- [ ] Positive, negative, missing/truncated-source, and tail-unreliable tests exist.
- [ ] Evidence references are capped and resolve against `IncidentReport.evidence`.
- [ ] Rule is registered with a unique ID; demo core/deferred expectations updated if affected.
- [ ] No Qt, network, clock, or randomness dependency.
- [ ] Report and UI wording reviewed against this document.
