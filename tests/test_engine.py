"""T-010: engine assembly, ordering, corroboration, demo integration, guards."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from rule_fixtures import entry, make_bundle
from syspanic.collectors.demo import (
    DEMO_CURRENT_BOOT_ID,
    DEMO_PREVIOUS_BOOT_ID,
    DemoCollector,
)
from syspanic.diagnostics import engine
from syspanic.domain.enums import EvidenceStrength, Severity
from syspanic.domain.models import BANNED_TERMS, validate_report

NOW = datetime(2026, 11, 16, 10, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def demo():
    return DemoCollector()


def test_demo_previous_core_findings_exact(demo):
    report = engine.analyze(demo.collect(DEMO_PREVIOUS_BOOT_ID), now=NOW)
    expected = demo.expected_findings[DEMO_PREVIOUS_BOOT_ID]["core"]
    assert sorted(f.rule_id for f in report.findings) == sorted(expected)


def test_demo_current_core_findings_exact(demo):
    report = engine.analyze(demo.collect(DEMO_CURRENT_BOOT_ID), now=NOW)
    expected = demo.expected_findings[DEMO_CURRENT_BOOT_ID]["core"]
    assert sorted(f.rule_id for f in report.findings) == sorted(expected)


def test_deferred_rules_never_emitted(demo):
    report = engine.analyze(demo.collect(DEMO_PREVIOUS_BOOT_ID), now=NOW)
    assert not any(f.rule_id in ("ART-002", "ART-003") for f in report.findings)


def test_findings_sorted_by_severity_then_rule_id(demo):
    report = engine.analyze(demo.collect(DEMO_PREVIOUS_BOOT_ID), now=NOW)
    order = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.NOTICE: 2, Severity.INFO: 3}
    keys = [(order[f.severity], f.rule_id) for f in report.findings]
    assert keys == sorted(keys)


def test_one_finding_per_rule(demo):
    report = engine.analyze(demo.collect(DEMO_PREVIOUS_BOOT_ID), now=NOW)
    ids = [f.rule_id for f in report.findings]
    assert len(ids) == len(set(ids))


def test_deterministic_report(demo):
    bundle = demo.collect(DEMO_PREVIOUS_BOOT_ID)
    first = engine.analyze(bundle, now=NOW)
    second = engine.analyze(bundle, now=NOW)
    assert first == second


def test_report_passes_validation(demo):
    for boot_id in (DEMO_CURRENT_BOOT_ID, DEMO_PREVIOUS_BOOT_ID):
        bundle = demo.collect(boot_id)
        report = engine.analyze(bundle, now=NOW)
        validate_report(report, bundle)
        assert report.demo is True
        assert report.app_version
        assert report.generated_at == NOW


def test_evidence_refs_resolve_and_bounded(demo):
    report = engine.analyze(demo.collect(DEMO_PREVIOUS_BOOT_ID), now=NOW)
    ids = {e.evidence_id for e in report.evidence}
    for finding in report.findings:
        assert 1 <= len(finding.evidence) <= 3
        for ref in finding.evidence:
            assert ref.evidence_id in ids
            lines = ref.excerpt.splitlines()
            assert len(lines) <= 3
            assert all(len(line) <= 300 for line in lines)


def test_no_banned_terms_in_findings(demo):
    for boot_id in (DEMO_CURRENT_BOOT_ID, DEMO_PREVIOUS_BOOT_ID):
        report = engine.analyze(demo.collect(boot_id), now=NOW)
        for finding in report.findings:
            text = " ".join(
                [finding.title, finding.interpretation, *finding.suspected_causes,
                 *finding.unknowns, *finding.next_steps]
            ).lower()
            for term in BANNED_TERMS:
                assert term not in text


def test_empty_evidence_yields_no_findings():
    bundle = make_bundle([])
    report = engine.analyze(bundle, now=NOW)
    assert report.findings == ()
    validate_report(report, bundle)


def test_mce_edac_corroboration_separate_lines():
    entries = [
        entry("mce: [Hardware Error]: Machine Check Exception Uncorrected (UC) bank 4", index=0),
        entry("EDAC MC0: 1 UE uncorrected error on DIMM#0", index=1),
    ]
    report = engine.analyze(make_bundle(entries), now=NOW)
    by_rule = {f.rule_id: f for f in report.findings}
    assert by_rule["MCE-001"].strength is EvidenceStrength.CORROBORATED
    assert by_rule["MEM-002"].strength is EvidenceStrength.CORROBORATED


def test_mce_edac_same_line_not_corroborated():
    entries = [entry("mce: [Hardware Error]: EDAC UE Uncorrected error", index=0)]
    report = engine.analyze(make_bundle(entries), now=NOW)
    by_rule = {f.rule_id: f for f in report.findings}
    assert "MCE-001" in by_rule
    assert "MEM-002" not in by_rule
    assert by_rule["MCE-001"].strength is EvidenceStrength.DIRECT


def test_diagnostics_package_is_qt_free():
    root = Path(__file__).resolve().parents[1] / "src" / "syspanic" / "diagnostics"
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "PySide6" not in text
        assert "from Qt" not in text
        assert "import Qt" not in text
