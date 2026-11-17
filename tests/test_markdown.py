"""T-016: Markdown report contract — sections, bounds, redaction, determinism."""

import re
from datetime import UTC, datetime

import pytest

from rule_fixtures import entry, filler, make_bundle
from syspanic.collectors.demo import (
    DEMO_CURRENT_BOOT_ID,
    DEMO_HOSTNAME,
    DEMO_PREVIOUS_BOOT_ID,
    DemoCollector,
)
from syspanic.constants import SOURCE_JOURNAL_SYSTEM
from syspanic.diagnostics import engine
from syspanic.domain.models import BANNED_TERMS, MAX_TIMELINE_EVENTS
from syspanic.report.markdown import render_report
from syspanic.report.sanitize import sanitize

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)

SECTIONS = (
    "# SysPanic Diagnostic Report",
    "## Metadata",
    "## Scope and limitations",
    "## Summary",
    "## Evidence coverage",
    "## Findings",
    "## Timeline",
    "## System snapshot",
    "## Crash artifacts",
    "## Redaction summary",
    "## Disclaimer",
)

FAKE_IDENTIFIERS = (
    DEMO_HOSTNAME,
    "/home/demo",
    "192.0.2.10",
    "02:00:00:00:00:01",
    "demo@example.com",
    "DEMO-SERIAL-0001",
    "123e4567-e89b-12d3-a456-426614174000",
    "DemoPass123",
    "sk-demo-123",
    "tok-demo-456",
    "dbsecret",
    "eyJdemoTokenValue",
)


@pytest.fixture(scope="module")
def demo_reports():
    collector = DemoCollector()
    out = {}
    for boot_id in (DEMO_CURRENT_BOOT_ID, DEMO_PREVIOUS_BOOT_ID):
        bundle = collector.collect(boot_id)
        report = engine.analyze(bundle, now=NOW)
        out[boot_id] = (report, render_report(report, hostnames=(DEMO_HOSTNAME,)))
    return out


def test_required_sections_in_order(demo_reports):
    for _, markdown in demo_reports.values():
        positions = [markdown.index(section) for section in SECTIONS]
        assert positions == sorted(positions)
        assert len(set(positions)) == len(positions)


def test_demo_notice_exact(demo_reports):
    for _, markdown in demo_reports.values():
        assert "DEMO DATA — not collected from this machine" in markdown


def test_non_demo_report_has_no_demo_notice():
    report = engine.analyze(make_bundle([]), now=NOW)
    markdown = render_report(report)
    assert "DEMO DATA" not in markdown


def test_metadata_fields(demo_reports):
    report, markdown = demo_reports[DEMO_PREVIOUS_BOOT_ID]
    assert report.app_version in markdown
    assert report.boot.boot_id[:8] in markdown
    assert report.boot.boot_id in markdown
    assert NOW.isoformat() in markdown
    assert "UTC" in markdown
    assert report.boot.first_entry.isoformat() in markdown
    assert report.boot.last_entry.isoformat() in markdown


def test_no_findings_wording_exact():
    report = engine.analyze(make_bundle([]), now=NOW)
    markdown = render_report(report)
    assert (
        "No supported crash signatures were found in the available evidence. "
        "This does not establish that the hardware is healthy." in markdown
    )


def test_coverage_table_lists_every_source(demo_reports):
    report, markdown = demo_reports[DEMO_CURRENT_BOOT_ID]
    section = markdown.split("## Evidence coverage")[1].split("## Findings")[0]
    for coverage in report.coverage:
        assert coverage.source in section
    assert "| Source |" in section


def test_coverage_detail_pipe_escaped():
    bundle = make_bundle([])
    object.__setattr__(bundle.coverage[0], "detail", "a|b")
    report = engine.analyze(bundle, now=NOW)
    markdown = render_report(report)
    assert "a\\|b" in markdown


def test_finding_block_fields(demo_reports):
    _, markdown = demo_reports[DEMO_PREVIOUS_BOOT_ID]
    section = markdown.split("## Findings")[1].split("## Timeline")[0]
    assert "PNC-001" in section
    assert "critical" in section.lower()
    assert "direct" in section.lower()
    assert "```" in section
    assert "Suspected causes" in section or "Unknowns" in section
    assert "Next steps" in section
    assert "Sources" in section


def test_excerpts_fenced_and_bounded(demo_reports):
    for _, markdown in demo_reports.values():
        blocks = re.findall(r"```text\n(.*?)```", markdown, flags=re.DOTALL)
        assert blocks
        for block in blocks:
            lines = block.rstrip("\n").split("\n")
            assert len(lines) <= 3
            assert all(len(line) <= 300 for line in lines)


def test_timeline_rows_bounded(demo_reports):
    for report, markdown in demo_reports.values():
        assert len(report.timeline) <= MAX_TIMELINE_EVENTS
        section = markdown.split("## Timeline")[1].split("## System snapshot")[0]
        rows = [line for line in section.splitlines() if line.startswith("| ")]
        assert len(rows) <= MAX_TIMELINE_EVENTS + 2


def test_system_snapshot_collected_now(demo_reports):
    report, markdown = demo_reports[DEMO_CURRENT_BOOT_ID]
    section = markdown.split("## System snapshot")[1].split("## Crash artifacts")[0]
    assert "not at crash time" in section
    assert report.system.collected_at.isoformat() in section
    assert report.system.os_name in section
    assert report.system.cpu_model in section
    for gpu in report.system.gpus:
        assert gpu.model in section


def test_artifacts_association_and_metadata(demo_reports):
    report, markdown = demo_reports[DEMO_PREVIOUS_BOOT_ID]
    section = markdown.split("## Crash artifacts")[1].split("## Redaction summary")[0]
    assert report.artifacts.vmcore_files
    artifact = report.artifacts.vmcore_files[0]
    assert artifact.association.value in section
    assert artifact.association_reason in section
    assert str(artifact.size_bytes) in section
    assert "binary" in section.lower()
    assert "127.0.0.1" not in section


def test_current_boot_no_artifacts_wording(demo_reports):
    _, markdown = demo_reports[DEMO_CURRENT_BOOT_ID]
    section = markdown.split("## Crash artifacts")[1].split("## Redaction summary")[0]
    assert "No crash artifacts" in section


def test_redaction_summary_wording(demo_reports):
    for _, markdown in demo_reports.values():
        section = markdown.split("## Redaction summary")[1].split("## Disclaimer")[0]
        assert "Redaction is best-effort; review the preview before sharing." in section
        assert "unrecognized secrets may remain" in section
        assert "Boot IDs are retained by design" in section
        assert "Redaction tokens applied:" in section


def test_credential_redaction_in_rendered_excerpt():
    tail = [
        entry(
            f"demo-app: config password=DemoPass123 token=tok-demo-{i}",
            22 + i,
            source=SOURCE_JOURNAL_SYSTEM,
            transport="stdout",
        )
        for i in range(3)
    ]
    report = engine.analyze(make_bundle(filler(22) + tail), now=NOW)
    markdown = render_report(report)
    assert "SHD-002" in markdown
    assert "DemoPass123" not in markdown
    assert "tok-demo-" not in markdown
    assert "password=CRED_" in markdown
    section = markdown.split("## Redaction summary")[1].split("## Disclaimer")[0]
    assert "CRED_" in section


def test_rendered_report_is_idempotent_under_resanitize(demo_reports):
    for _, markdown in demo_reports.values():
        again, counts = sanitize(markdown, hostnames=(DEMO_HOSTNAME,))
        assert again == markdown
        assert counts == {}


def test_fake_identifiers_absent(demo_reports):
    for _, markdown in demo_reports.values():
        for leak in FAKE_IDENTIFIERS:
            assert leak not in markdown, f"leaked: {leak}"


def test_boot_ids_retained(demo_reports):
    for report, markdown in demo_reports.values():
        assert report.boot.boot_id in markdown


def test_deterministic_output(demo_reports):
    collector = DemoCollector()
    for report, markdown in demo_reports.values():
        again = render_report(report, hostnames=(DEMO_HOSTNAME,))
        assert again == markdown
        bundle = collector.collect(report.boot.boot_id)
        report2 = engine.analyze(bundle, now=NOW)
        assert render_report(report2, hostnames=(DEMO_HOSTNAME,)) == markdown


def test_size_under_100_kib(demo_reports):
    for _, markdown in demo_reports.values():
        assert len(markdown.encode("utf-8")) < 100 * 1024


def test_no_banned_terms(demo_reports):
    for _, markdown in demo_reports.values():
        lowered = markdown.lower()
        for term in BANNED_TERMS:
            assert term not in lowered


def test_historical_boot_limitations(demo_reports):
    _, markdown = demo_reports[DEMO_PREVIOUS_BOOT_ID]
    scope = markdown.split("## Scope and limitations")[1].split("## Summary")[0]
    assert "dmesg" in scope
    assert "historical" in scope.lower()
    findings = markdown.split("## Findings")[1].split("## Timeline")[0]
    assert "hard reset" in findings.lower()
    assert "power loss" in findings.lower()


def test_no_raw_log_appendix(demo_reports):
    for _, markdown in demo_reports.values():
        assert "filler event" not in markdown


def test_summary_counts_match_findings(demo_reports):
    for report, markdown in demo_reports.values():
        section = markdown.split("## Summary")[1].split("## Evidence coverage")[0]
        critical = sum(1 for f in report.findings if f.severity.value == "critical")
        assert f"Critical: {critical}" in section
