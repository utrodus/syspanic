"""T-012: MEM-001/002 — EDAC CE/UE, precedence, unknown tokens."""

from rule_fixtures import entry, make_bundle
from syspanic.diagnostics.rules import memory
from syspanic.domain.enums import Severity


def by_rule(findings):
    return {f.rule_id: f for f in findings}


def test_mem001_corrected_warning():
    entries = [entry("EDAC MC0: 1 CE correctable error on CPU_SrcID#0_MC#0_Chan#0_DIMM#0", 0)]
    findings = by_rule(memory.evaluate(make_bundle(entries)))
    assert findings["MEM-001"].severity is Severity.WARNING
    assert "MEM-002" not in findings


def test_mem002_uncorrected_critical():
    for message in (
        "EDAC MC0: 1 UE uncorrected error on DIMM#0",
        "EDAC MC0: Fatal memory error detected",
    ):
        findings = by_rule(memory.evaluate(make_bundle([entry(message, 0)])))
        assert findings["MEM-002"].severity is Severity.CRITICAL


def test_edac_without_ce_ue_no_finding():
    entries = [entry("EDAC MC0: giving out non-atomic events", 0)]
    assert memory.evaluate(make_bundle(entries)) == ()


def test_ue_dominates_when_both_tokens():
    entries = [entry("EDAC MC0: CE corrected and UE uncorrected errors", 0)]
    findings = by_rule(memory.evaluate(make_bundle(entries)))
    assert "MEM-002" in findings
    assert "MEM-001" not in findings


def test_leading_edac_over_mce():
    entries = [entry("EDAC MC0: mce: [Hardware Error] UE uncorrected", 0)]
    findings = by_rule(memory.evaluate(make_bundle(entries)))
    assert "MEM-002" in findings


def test_leading_mce_skips_memory():
    entries = [entry("mce: [Hardware Error]: EDAC UE uncorrected", 0)]
    assert memory.evaluate(make_bundle(entries)) == ()


def test_userspace_edac_ignored():
    from syspanic.constants import SOURCE_JOURNAL_SYSTEM

    entries = [
        entry(
            "EDAC MC0: 1 CE corrected error",
            0,
            source=SOURCE_JOURNAL_SYSTEM,
            transport="stdout",
            extra={"SYSLOG_IDENTIFIER": "kernel"},
        )
    ]
    assert memory.evaluate(make_bundle(entries)) == ()
