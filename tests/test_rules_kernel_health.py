"""KRN-001: taint flag parsing — G is the untainted placeholder."""

from rule_fixtures import entry, make_bundle
from syspanic.diagnostics.rules import kernel_health
from syspanic.domain.enums import Severity


def test_krn001_active_flags():
    entries = [entry("CPU: 1 PID: 1 Comm: demo Tainted: P O E 6.17.8 #1", 0)]
    findings = kernel_health.evaluate(make_bundle(entries))
    finding = findings[0]
    assert finding.rule_id == "KRN-001"
    assert finding.severity is Severity.INFO
    for flag in ("P", "O", "E"):
        assert flag in finding.interpretation


def test_krn001_g_placeholder_not_adverse():
    entries = [entry("CPU: 1 PID: 1 Comm: demo Tainted: G 6.17.8 #1", 0)]
    findings = kernel_health.evaluate(make_bundle(entries))
    assert len(findings) == 1
    assert "no adverse" in findings[0].interpretation.lower()


def test_krn001_warning_and_died_flags():
    entries = [entry("CPU: 1 PID: 1 Comm: demo Tainted: G      D    W 6.17.8 #1", 0)]
    finding = kernel_health.evaluate(make_bundle(entries))[0]
    assert "D" in finding.interpretation
    assert "W" in finding.interpretation


def test_no_taint_line_no_finding():
    assert kernel_health.evaluate(make_bundle([entry("kernel: normal boot", 0)])) == ()


def test_userspace_taint_ignored():
    from syspanic.constants import SOURCE_JOURNAL_SYSTEM

    entries = [
        entry(
            "Tainted: P O E",
            0,
            source=SOURCE_JOURNAL_SYSTEM,
            transport="stdout",
            extra={"SYSLOG_IDENTIFIER": "kernel"},
        )
    ]
    assert kernel_health.evaluate(make_bundle(entries)) == ()
