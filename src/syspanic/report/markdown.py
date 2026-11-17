"""IncidentReport -> sanitized Markdown (docs/04 §11 report contract)."""

from syspanic.diagnostics.coverage import (
    TAIL_UNRELIABLE_NOTE,
    UNAVAILABLE_SOURCE_NOTE,
    overall_completeness,
    tail_reliable,
)
from syspanic.domain.enums import SourceState
from syspanic.domain.models import IncidentReport
from syspanic.report.sanitize import local_identity_seeds, sanitize

_COUNTS_PLACEHOLDER = "@@REDACTION_COUNTS@@"
_READ_STATES = (SourceState.AVAILABLE, SourceState.TRUNCATED, SourceState.EMPTY)
NO_FINDINGS_TEXT = (
    "No supported crash signatures were found in the available evidence. "
    "This does not establish that the hardware is healthy."
)
BEST_EFFORT_TEXT = "Redaction is best-effort; review the preview before sharing."


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _fence(text: str) -> str:
    fence = "```"
    while fence in text:
        fence += "`"
    return f"{fence}text\n{text}\n{fence}"


def _bullets(items: tuple[str, ...]) -> str:
    if not items:
        return "- None stated.\n"
    return "".join(f"- {item}\n" for item in items)


def _metadata(report: IncidentReport) -> str:
    boot = report.boot
    window = "unknown"
    if boot.first_entry is not None and boot.last_entry is not None:
        window = f"{boot.first_entry.isoformat()} .. {boot.last_entry.isoformat()}"
    kind = "current" if boot.is_current else "historical"
    return (
        "## Metadata\n\n"
        f"- App version: {report.app_version}\n"
        f"- Boot ID (short): {boot.boot_id[:8]}\n"
        f"- Boot ID (full): {boot.boot_id}\n"
        f"- Boot window: {window}\n"
        f"- Selected boot: index {boot.index} ({kind})\n"
        f"- Generated at: {report.generated_at.isoformat()}\n"
        "- Timezone: UTC\n\n"
    )


def _scope(report: IncidentReport) -> str:
    lines = [
        "## Scope and limitations\n\n",
        f"- Overall completeness: {overall_completeness(report.coverage)}\n",
    ]
    for coverage in report.coverage:
        if coverage.state not in _READ_STATES:
            detail = f" {coverage.detail}" if coverage.detail else ""
            lines.append(
                f"- `{coverage.source}`: {coverage.state.value}.{detail} "
                f"{UNAVAILABLE_SOURCE_NOTE}\n"
            )
    if not tail_reliable(report.coverage):
        lines.append(f"- {TAIL_UNRELIABLE_NOTE}\n")
    lines.append("- Missing or unreadable sources are not evidence of health.\n")
    lines.append(
        "- Inventory and sensor details describe the system when collected, not at crash time.\n\n"
    )
    return "".join(lines)


def _summary(report: IncidentReport) -> str:
    counts = {"critical": 0, "warning": 0, "notice": 0, "info": 0}
    for finding in report.findings:
        counts[finding.severity.value] += 1
    lines = [
        "## Summary\n\n",
        f"- Critical: {counts['critical']}\n",
        f"- Warning: {counts['warning']}\n",
        f"- Notice: {counts['notice']}\n",
        f"- Info: {counts['info']}\n",
        f"- Total findings: {len(report.findings)}\n\n",
    ]
    if not report.findings:
        lines.append(f"{NO_FINDINGS_TEXT}\n\n")
    return "".join(lines)


def _coverage_table(report: IncidentReport) -> str:
    lines = [
        "## Evidence coverage\n\n",
        "| Source | State | Entries | Head truncated | Tail reliable | Detail |\n",
        "|---|---|---|---|---|---|\n",
    ]
    for coverage in report.coverage:
        lines.append(
            f"| {_cell(coverage.source)} | {coverage.state.value} | {coverage.entry_count} "
            f"| {str(coverage.head_truncated).lower()} | {str(coverage.tail_reliable).lower()} "
            f"| {_cell(coverage.detail)} |\n"
        )
    return "".join(lines) + "\n"


def _findings(report: IncidentReport) -> str:
    lines = ["## Findings\n\n"]
    if not report.findings:
        return "## Findings\n\nNo findings for this boot.\n\n"
    for finding in report.findings:
        lines.append(f"### {finding.rule_id} — {finding.title}\n\n")
        lines.append(f"- Severity: {finding.severity.value}\n")
        lines.append(f"- Evidence strength: {finding.strength.value}\n\n")
        lines.append("**Excerpts (bounded evidence):**\n\n")
        for ref in finding.evidence:
            lines.append(f"`{ref.evidence_id}`:\n\n{_fence(ref.excerpt)}\n\n")
        lines.append(f"**Interpretation:** {finding.interpretation}\n\n")
        lines.append("**Suspected causes (unconfirmed):**\n\n")
        lines.append(_bullets(finding.suspected_causes))
        lines.append("\n**Unknowns:**\n\n")
        lines.append(_bullets(finding.unknowns))
        lines.append("\n**Next steps:**\n\n")
        lines.append(_bullets(finding.next_steps))
        lines.append(f"\n**Sources:** {', '.join(finding.sources)}\n\n")
    return "".join(lines)


def _timeline(report: IncidentReport) -> str:
    lines = ["## Timeline\n\n"]
    if not report.timeline:
        return "## Timeline\n\nNo timeline events.\n\n"
    lines.append("| Time (UTC) | Kind | Severity | Summary | Evidence |\n")
    lines.append("|---|---|---|---|---|\n")
    for event in report.timeline:
        lines.append(
            f"| {event.timestamp.isoformat()} | {event.kind.value} | {event.severity.value} "
            f"| {_cell(event.summary)} | {event.evidence_id} |\n"
        )
    return "".join(lines) + "\n"


def _system(report: IncidentReport) -> str:
    lines = ["## System snapshot\n\n"]
    system = report.system
    if system is None:
        lines.append(f"System inventory was not collected. {UNAVAILABLE_SOURCE_NOTE}\n\n")
        return "".join(lines)
    lines.append(
        f"CPU and GPU details were collected at {system.collected_at.isoformat()}, "
        "not at crash time.\n\n"
    )
    lines.append(f"- OS: {system.os_name} {system.os_version_id}\n")
    lines.append(f"- Kernel: {system.kernel}\n")
    lines.append(f"- Architecture: {system.arch}\n")
    lines.append(f"- CPU: {system.cpu_model} ({system.cpu_cores} cores)\n")
    if system.microcode:
        lines.append(f"- Microcode: {system.microcode}\n")
    lines.append(f"- Memory: {system.mem_total_kib // 1024} MiB\n")
    for gpu in system.gpus:
        driver = f", driver {gpu.driver}" if gpu.driver else ""
        lines.append(f"- GPU: {gpu.pci_address} {gpu.vendor} {gpu.model}{driver}\n")
    if system.bios_vendor or system.bios_version:
        lines.append(
            f"- BIOS: {system.bios_vendor or ''} {system.bios_version or ''} "
            f"({system.bios_date or 'date unknown'})\n"
        )
    if system.board_vendor or system.board_name:
        lines.append(f"- Board: {system.board_vendor or ''} {system.board_name or ''}\n")
    return "".join(lines) + "\n"


def _artifacts(report: IncidentReport) -> str:
    lines = ["## Crash artifacts\n\n"]
    artifacts = report.artifacts
    groups = (
        ("vmcore (binary dump)", artifacts.vmcore_files if artifacts else ()),
        ("vmcore-dmesg (text)", artifacts.vmcore_dmesg if artifacts else ()),
        ("pstore (text)", artifacts.pstore_records if artifacts else ()),
    )
    if not any(items for _, items in groups):
        lines.append("No crash artifacts were found for this boot.\n\n")
    for label, items in groups:
        if not items:
            continue
        lines.append(f"### {label}\n\n")
        for artifact in items:
            mtime = artifact.mtime.isoformat() if artifact.mtime else "unknown"
            note = artifact.note or "metadata only"
            lines.append(f"- Path: {artifact.path}\n")
            lines.append(f"- Size: {artifact.size_bytes} bytes\n")
            lines.append(f"- Modified: {mtime}\n")
            lines.append(
                f"- Association: {artifact.association.value} — {artifact.association_reason}\n"
            )
            lines.append(f"- Note: {note}\n\n")
    lines.append("Binary dump contents are never read or included; metadata only.\n")
    if artifacts is not None:
        loaded = artifacts.crash_kernel_loaded
        state = "unknown" if loaded is None else ("yes" if loaded else "no")
        lines.append(f"- Crash kernel loaded: {state}\n")
        for note in artifacts.notes:
            lines.append(f"- {note}\n")
    return "".join(lines) + "\n"


def _redaction() -> str:
    return (
        "## Redaction summary\n\n"
        f"- {BEST_EFFORT_TEXT}\n"
        "- Credential/token/connection-string redaction is best-effort; "
        "unrecognized secrets may remain.\n"
        "- Boot IDs are retained by design (random identifiers needed for correlation); "
        "PCI addresses, kernel version, timestamps, and error counts are retained.\n"
        f"{_COUNTS_PLACEHOLDER}\n"
        "- No hostname, username, home path, IP, MAC, email, serial, UUID, or machine ID "
        "is included by design; /proc/cmdline is never collected.\n\n"
    )


def _disclaimer(report: IncidentReport) -> str:
    return (
        "## Disclaimer\n\n"
        f"SysPanic {report.app_version} — Don't panic. Diagnose. Findings cite observed "
        "evidence only; suspected causes are unconfirmed, and missing evidence is not "
        "evidence of health.\n"
    )


def _render_raw(report: IncidentReport) -> str:
    parts = ["# SysPanic Diagnostic Report\n\n"]
    if report.demo:
        parts.append("**DEMO DATA — not collected from this machine**\n\n")
    parts.extend(
        (
            _metadata(report),
            _scope(report),
            _summary(report),
            _coverage_table(report),
            _findings(report),
            _timeline(report),
            _system(report),
            _artifacts(report),
            _redaction(),
            _disclaimer(report),
        )
    )
    return "".join(parts)


def render_report_with_counts(
    report: IncidentReport, *, hostnames=(), usernames=()
) -> tuple[str, dict[str, int]]:
    local_hosts, local_users = local_identity_seeds()
    host_seeds = set(hostnames) | set(local_hosts)
    for item in report.evidence:
        hostname = item.provenance.get("_HOSTNAME")
        if hostname:
            host_seeds.add(hostname)
    user_seeds = tuple(dict.fromkeys((*usernames, *local_users)))
    raw = _render_raw(report)
    sanitized, counts = sanitize(
        raw,
        hostnames=sorted(host_seeds, key=lambda h: (-len(h), h)),
        usernames=user_seeds,
    )
    if counts:
        parts = []
        for kind, count in sorted(counts.items()):
            span = f"{kind}_1" if count == 1 else f"{kind}_1..{kind}_{count}"
            parts.append(f"{span} (count {count})")
        counts_line = f"- Redaction tokens applied: {', '.join(parts)}"
    else:
        counts_line = "- Redaction tokens applied: none"
    return sanitized.replace(_COUNTS_PLACEHOLDER, counts_line), counts


def render_report(report: IncidentReport, *, hostnames=(), usernames=()) -> str:
    text, _ = render_report_with_counts(report, hostnames=hostnames, usernames=usernames)
    return text
