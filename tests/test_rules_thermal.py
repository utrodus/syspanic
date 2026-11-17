"""T-012: THM-001/002 — throttling vs critical thermal protection."""

from rule_fixtures import entry, make_bundle
from syspanic.diagnostics.rules import thermal
from syspanic.domain.enums import Severity


def by_rule(findings):
    return {f.rule_id: f for f in findings}


def test_thm001_throttling_variants():
    for message in (
        "CPU0: Core temperature above threshold, cpu clock throttled",
        "CPU1: Package temperature above threshold, cpu clock throttled",
        "thermal thermal_zone0: throttling activated",
        "x86/cpu: package_throttled event detected",
    ):
        findings = by_rule(thermal.evaluate(make_bundle([entry(message, 0)])))
        assert findings["THM-001"].severity is Severity.WARNING


def test_thm002_critical_temperature():
    for message in (
        "CPU0: critical temperature reached, shutting down",
        "thermal thermal_zone0: critical temperature reached (105 C), shutting down",
        "ACPI: thermal shutdown initiated",
    ):
        findings = by_rule(thermal.evaluate(make_bundle([entry(message, 0)])))
        assert findings["THM-002"].severity is Severity.CRITICAL


def test_thm002_critical_temperature_token():
    entries = [entry("CPU0: Critical temperature reached (100 C)", 0)]
    assert "THM-002" in by_rule(thermal.evaluate(make_bundle(entries)))


def test_no_thermal_lines_no_findings():
    assert thermal.evaluate(make_bundle([entry("kernel: idle loop", 0)])) == ()


def test_userspace_thermal_ignored():
    from syspanic.constants import SOURCE_JOURNAL_SYSTEM

    entries = [
        entry(
            "cpu clock throttled",
            0,
            source=SOURCE_JOURNAL_SYSTEM,
            transport="stdout",
            extra={"SYSLOG_IDENTIFIER": "kernel"},
        )
    ]
    assert thermal.evaluate(make_bundle(entries)) == ()
