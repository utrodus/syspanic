"""T-011: MCE-001/002 — line-scoped classification, correctability precedence."""

from rule_fixtures import entry, make_bundle
from syspanic.diagnostics.rules import cpu_mce
from syspanic.domain.enums import Severity


def by_rule(findings):
    return {f.rule_id: f for f in findings}


def test_mce001_uncorrected_critical():
    entries = [entry("mce: [Hardware Error]: Machine Check Exception Uncorrected (UC) bank 4", 0)]
    findings = by_rule(cpu_mce.evaluate(make_bundle(entries)))
    assert findings["MCE-001"].severity is Severity.CRITICAL


def test_mce001_fatal_and_ue_tokens():
    for message in (
        "mce: [Hardware Error]: Fatal machine check",
        "Machine Check Exception: UE error detected",
    ):
        assert "MCE-001" in by_rule(cpu_mce.evaluate(make_bundle([entry(message, 0)])))


def test_mce002_corrected_warning():
    entries = [entry("mce: [Hardware Error]: Corrected error (CE) bank 2", 0)]
    findings = by_rule(cpu_mce.evaluate(make_bundle(entries)))
    assert findings["MCE-002"].severity is Severity.WARNING
    assert "MCE-001" not in findings


def test_mce002_unknown_correctability_notice():
    entries = [entry("mce: [Hardware Error]: Machine check events logged", 0)]
    findings = by_rule(cpu_mce.evaluate(make_bundle(entries)))
    assert findings["MCE-002"].severity is Severity.NOTICE
    assert "not stated" in findings["MCE-002"].interpretation.lower()
    assert "MCE-001" not in findings


def test_mce_exception_without_token_is_notice():
    entries = [entry("Machine Check Exception", 0)]
    findings = by_rule(cpu_mce.evaluate(make_bundle(entries)))
    assert findings["MCE-002"].severity is Severity.NOTICE


def test_leading_marker_decides_mce_over_edac():
    entries = [entry("mce: [Hardware Error]: EDAC MC0 UE uncorrected", 0)]
    findings = by_rule(cpu_mce.evaluate(make_bundle(entries)))
    assert "MCE-001" in findings


def test_leading_edac_skips_mce():
    entries = [entry("EDAC MC0: mce: [Hardware Error] UE uncorrected", 0)]
    assert cpu_mce.evaluate(make_bundle(entries)) == ()


def test_userspace_mce_text_ignored():
    from syspanic.constants import SOURCE_JOURNAL_SYSTEM

    entries = [
        entry(
            "mce: [Hardware Error]: Uncorrected",
            0,
            source=SOURCE_JOURNAL_SYSTEM,
            transport="stdout",
            extra={"SYSLOG_IDENTIFIER": "kernel"},
        )
    ]
    assert cpu_mce.evaluate(make_bundle(entries)) == ()


def test_no_mce_lines_no_findings():
    assert cpu_mce.evaluate(make_bundle([entry("kernel: everything ok", 0)])) == ()
