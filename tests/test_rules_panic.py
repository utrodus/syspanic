"""T-011: PNC-001..004 — kernel provenance, panic/oops/lockup/sysrq."""

from rule_fixtures import entry, make_bundle
from syspanic.constants import SOURCE_JOURNAL_SYSTEM
from syspanic.diagnostics.rules import panic
from syspanic.domain.enums import Severity


def ids(findings):
    return {f.rule_id for f in findings}


def test_pnc001_kernel_panic():
    findings = panic.evaluate(
        make_bundle([entry("Kernel panic - not syncing: Fatal exception", index=0)])
    )
    finding = next(f for f in findings if f.rule_id == "PNC-001")
    assert finding.severity is Severity.CRITICAL
    assert "root cause" in finding.interpretation


def test_pnc002_oops_and_bug_variants():
    for message in (
        "Oops: 0000 [#1] SMP NOPTI",
        "BUG: unable to handle kernel paging request",
        "general protection fault, probably for non-canonical address",
        "kernel BUG at mm/slub.c:372!",
        "invalid opcode: 0000 [#1] SMP",
    ):
        findings = panic.evaluate(make_bundle([entry(message, index=0)]))
        assert "PNC-002" in ids(findings)
        finding = next(f for f in findings if f.rule_id == "PNC-002")
        assert finding.severity is Severity.WARNING


def test_pnc002_warning_distinct_from_fatal_panic():
    entries = [
        entry("Oops: 0000 [#1] SMP NOPTI", index=0),
        entry("Kernel panic - not syncing: Fatal exception", index=1),
    ]
    findings = {f.rule_id: f for f in panic.evaluate(make_bundle(entries))}
    assert findings["PNC-001"].severity is Severity.CRITICAL
    assert findings["PNC-002"].severity is Severity.WARNING
    assert "may recover or precede a panic" in findings["PNC-002"].interpretation
    assert "lead, not a verdict" in findings["PNC-002"].interpretation


def test_pnc003_lockup_and_stalls():
    for message in (
        "watchdog: BUG: soft lockup - CPU#3 stuck for 22s!",
        "NMI watchdog: hard LOCKUP on cpu 2",
        "rcu: INFO: rcu_preempt detected stalls on CPUs/tasks",
        "INFO: task demo-app:4321 blocked for more than 120 seconds",
    ):
        assert "PNC-003" in ids(panic.evaluate(make_bundle([entry(message, index=0)])))


def test_pnc004_sysrq_action():
    findings = panic.evaluate(make_bundle([entry("sysrq: SysRq : Show State", index=0)]))
    assert "PNC-004" in ids(findings)
    assert next(f for f in findings if f.rule_id == "PNC-004").severity is Severity.NOTICE


def test_pnc004_emergency_remount_excluded():
    entries = [entry("sysrq: SysRq : Emergency Remount R/O", index=0)]
    assert "PNC-004" not in ids(panic.evaluate(make_bundle(entries)))


def test_userspace_panic_text_ignored():
    entries = [
        entry(
            "Kernel panic - not syncing: Fatal exception",
            index=0,
            source=SOURCE_JOURNAL_SYSTEM,
            transport="stdout",
            extra={"_COMM": "demo-app"},
        )
    ]
    assert ids(panic.evaluate(make_bundle(entries))) == set()


def test_spoofed_kernel_identifier_ignored():
    entries = [
        entry(
            "Oops: 0000 [#1] SMP",
            index=0,
            source=SOURCE_JOURNAL_SYSTEM,
            transport="syslog",
            extra={"SYSLOG_IDENTIFIER": "kernel"},
        )
    ]
    assert "PNC-002" not in ids(panic.evaluate(make_bundle(entries)))


def test_dmesg_accepted_for_current_boot():
    from rule_fixtures import make_boot

    entries = [
        entry("Kernel panic - not syncing: Fatal exception", index=0, source="dmesg", prefix="DMS-")
    ]
    bundle = make_bundle(entries, boot=make_boot(index=0, is_current=True))
    assert "PNC-001" in ids(panic.evaluate(bundle))


def test_interpretation_states_total_count():
    entries = [entry(f"Oops: 0000 [#{i}] SMP", index=i) for i in range(5)]
    findings = panic.evaluate(make_bundle(entries))
    finding = next(f for f in findings if f.rule_id == "PNC-002")
    assert len(finding.evidence) == 3
    assert "5" in finding.interpretation
