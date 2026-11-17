"""T-012: GPU-001..004 — timeout/reset separation, VM fault, Xid codes."""

from rule_fixtures import entry, make_bundle
from syspanic.diagnostics.rules import gpu
from syspanic.domain.enums import Severity


def by_rule(findings):
    return {f.rule_id: f for f in findings}


def test_gpu001_ring_timeout():
    entries = [entry("amdgpu 0000:0a:00.0: amdgpu: ring gfx_0.0.0 timeout", 0)]
    findings = by_rule(gpu.evaluate(make_bundle(entries)))
    assert findings["GPU-001"].severity is Severity.WARNING
    assert "GPU-002" not in findings


def test_gpu001_job_timedout_variant():
    entries = [entry("drm:amdgpu_job_timedout [amdgpu] *ERROR* ring gfx timeout", 0)]
    assert "GPU-001" in by_rule(gpu.evaluate(make_bundle(entries)))


def test_gpu002_reset_begin_and_end():
    entries = [
        entry("amdgpu 0000:0a:00.0: amdgpu: GPU reset begin!", 0),
        entry("amdgpu 0000:0a:00.0: amdgpu: GPU reset end!", 1),
    ]
    findings = by_rule(gpu.evaluate(make_bundle(entries)))
    assert findings["GPU-002"].severity is Severity.WARNING
    assert "GPU-001" not in findings


def test_gpu002_reset_only_no_timeout():
    entries = [entry("amdgpu 0000:0a:00.0: amdgpu: GPU reset(2) succeeded", 0)]
    findings = by_rule(gpu.evaluate(make_bundle(entries)))
    assert "GPU-002" in findings
    assert "GPU-001" not in findings


def test_gpu001_and_gpu002_both_when_both_present():
    entries = [
        entry("amdgpu 0000:0a:00.0: amdgpu: ring gfx timeout", 0),
        entry("amdgpu 0000:0a:00.0: amdgpu: GPU reset begin!", 1),
    ]
    findings = by_rule(gpu.evaluate(make_bundle(entries)))
    assert "GPU-001" in findings
    assert "GPU-002" in findings


def test_gpu003_vm_fault_variants():
    for message in (
        "amdgpu 0000:0a:00.0: amdgpu: VM fault (0x0000000000000000) detected",
        "amdgpu: GPU fault detected on ring gfx",
        "amdgpu: IH ring buffer overflow",
        "amdgpu: retry page fault handling",
    ):
        assert "GPU-003" in by_rule(gpu.evaluate(make_bundle([entry(message, 0)])))


def test_gpu004_xid_warning_and_79_critical():
    entries = [entry("NVRM: Xid (PCI:0000:01:00): 31, pid=4321, channel 0x0000000a", 0)]
    findings = by_rule(gpu.evaluate(make_bundle(entries)))
    assert findings["GPU-004"].severity is Severity.WARNING
    assert "31" in findings["GPU-004"].interpretation

    entries = [entry("NVRM: Xid (PCI:0000:01:00): 79, GPU has fallen off the bus", 0)]
    findings = by_rule(gpu.evaluate(make_bundle(entries)))
    assert findings["GPU-004"].severity is Severity.CRITICAL


def test_gpu_userspace_lookalike_ignored():
    from syspanic.constants import SOURCE_JOURNAL_SYSTEM

    entries = [
        entry(
            "amdgpu: ring gfx timeout",
            0,
            source=SOURCE_JOURNAL_SYSTEM,
            transport="stdout",
            extra={"SYSLOG_IDENTIFIER": "kernel", "_COMM": "demo-app"},
        )
    ]
    assert gpu.evaluate(make_bundle(entries)) == ()


def test_gpu_reset_word_without_amdgpu_ignored():
    entries = [entry("nvme nvme0: resetting controller", 0)]
    assert "GPU-002" not in by_rule(gpu.evaluate(make_bundle(entries)))
