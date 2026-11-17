"""T-012: PCI-001..003 — AER severity, link resets, Bus Error exclusion."""

from rule_fixtures import entry, make_bundle
from syspanic.diagnostics.rules import pcie
from syspanic.domain.enums import Severity


def by_rule(findings):
    return {f.rule_id: f for f in findings}


def test_pci001_corrected_notice():
    entries = [entry("pcieport 0000:00:01.1: AER: Corrected error received: 0000:0a:00.0", 0)]
    findings = by_rule(pcie.evaluate(make_bundle(entries)))
    assert findings["PCI-001"].severity is Severity.NOTICE
    assert "PCI-002" not in findings


def test_pci002_non_fatal_warning():
    entries = [entry("pcieport 0000:00:01.1: AER: Uncorrected (Non-Fatal) error received", 0)]
    findings = by_rule(pcie.evaluate(make_bundle(entries)))
    assert findings["PCI-002"].severity is Severity.WARNING
    assert "PCI-001" not in findings


def test_pci002_fatal_critical():
    entries = [entry("pcieport 0000:00:01.1: AER: Uncorrected (Fatal) error received", 0)]
    findings = by_rule(pcie.evaluate(make_bundle(entries)))
    assert findings["PCI-002"].severity is Severity.CRITICAL


def test_pci002_fatal_dominates_mixed():
    entries = [
        entry("pcieport 0000:00:01.1: AER: Uncorrected (Non-Fatal) error received", 0),
        entry("pcieport 0000:00:01.1: AER: Uncorrected (Fatal) error received", 1),
    ]
    findings = by_rule(pcie.evaluate(make_bundle(entries)))
    assert findings["PCI-002"].severity is Severity.CRITICAL


def test_pci003_link_down_and_resets():
    for message in (
        "pcieport 0000:00:01.1: Link Down",
        "pcieport 0000:00:01.1: link down detected",
        "pcieport 0000:00:01.1: slot reset complete",
        "pcieport 0000:00:01.1: bus reset issued",
    ):
        assert "PCI-003" in by_rule(pcie.evaluate(make_bundle([entry(message, 0)])))


def test_pcie_bus_error_alone_no_pci003():
    entries = [entry("pcieport 0000:00:01.1: PCIe Bus Error: severity=Corrected, type=Physical", 0)]
    findings = by_rule(pcie.evaluate(make_bundle(entries)))
    assert "PCI-003" not in findings
    assert "PCI-001" in findings


def test_pcie_bus_error_without_severity_only_evidence():
    entries = [entry("pcieport 0000:00:01.1: PCIe Bus Error: type=Physical Layer", 0)]
    assert pcie.evaluate(make_bundle(entries)) == ()


def test_userspace_aer_ignored():
    from syspanic.constants import SOURCE_JOURNAL_SYSTEM

    entries = [
        entry(
            "AER: Corrected error received",
            0,
            source=SOURCE_JOURNAL_SYSTEM,
            transport="stdout",
            extra={"SYSLOG_IDENTIFIER": "kernel"},
        )
    ]
    assert pcie.evaluate(make_bundle(entries)) == ()
