"""T-009: demo fixtures and DemoCollector — synthetic, no host probing."""

import json
import os
import socket
import subprocess
from datetime import UTC

import pytest

from syspanic.collectors.demo import (
    DEMO_CURRENT_BOOT_ID,
    DEMO_PREVIOUS_BOOT_ID,
    DemoCollector,
)
from syspanic.collectors.metadata import artifacts_to_evidence, boots_to_evidence
from syspanic.constants import (
    SOURCE_CRASH_KEXEC,
    SOURCE_CRASH_PSTORE,
    SOURCE_CRASH_VMCORE,
    SOURCE_CRASH_VMCORE_DMESG,
    SOURCE_DMESG,
    SOURCE_JOURNAL_BOOTS,
    SOURCE_JOURNAL_KERNEL,
    SOURCE_JOURNAL_SYSTEM,
    SOURCE_SYSTEM_CPU,
    SOURCE_SYSTEM_FIRMWARE,
    SOURCE_SYSTEM_GPU,
    SOURCE_SYSTEM_MEMORY,
    SOURCE_SYSTEM_OS,
)
from syspanic.domain.enums import ArtifactAssociation, SourceState
from syspanic.domain.models import CrashArtifacts

ALL_SOURCES = {
    SOURCE_JOURNAL_BOOTS,
    SOURCE_JOURNAL_KERNEL,
    SOURCE_JOURNAL_SYSTEM,
    SOURCE_DMESG,
    SOURCE_SYSTEM_OS,
    SOURCE_SYSTEM_CPU,
    SOURCE_SYSTEM_MEMORY,
    SOURCE_SYSTEM_GPU,
    SOURCE_SYSTEM_FIRMWARE,
    SOURCE_CRASH_VMCORE,
    SOURCE_CRASH_VMCORE_DMESG,
    SOURCE_CRASH_PSTORE,
    SOURCE_CRASH_KEXEC,
}


@pytest.fixture(scope="module")
def demo():
    return DemoCollector()


def test_boots_list(demo):
    boots = demo.boots()
    assert len(boots) == 2
    assert boots[0].boot_id == DEMO_PREVIOUS_BOOT_ID
    assert boots[0].index == -1
    assert boots[0].is_current is False
    assert boots[1].boot_id == DEMO_CURRENT_BOOT_ID
    assert boots[1].index == 0
    assert boots[1].is_current is True


def test_collect_current_bundle(demo):
    bundle = demo.collect(DEMO_CURRENT_BOOT_ID)
    assert bundle.demo is True
    assert bundle.boot.boot_id == DEMO_CURRENT_BOOT_ID
    assert bundle.boot.is_current is True
    assert bundle.hostname_hint == "demo-host"
    assert bundle.boot.kernel_release == "6.17.8-300.fc44.x86_64"
    assert bundle.boot.first_entry is not None
    assert bundle.boot.last_entry is not None


def test_collect_previous_bundle(demo):
    bundle = demo.collect(DEMO_PREVIOUS_BOOT_ID)
    assert bundle.demo is True
    assert bundle.boot.boot_id == DEMO_PREVIOUS_BOOT_ID
    assert bundle.boot.is_current is False


def test_unknown_boot_rejected(demo):
    with pytest.raises(ValueError):
        demo.collect("ffffffffffffffffffffffffffffffff")


def test_no_host_probing(demo, monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("demo mode must not probe the host")

    monkeypatch.setattr(subprocess, "Popen", boom)
    monkeypatch.setattr(os, "scandir", boom)
    monkeypatch.setattr(socket, "gethostname", boom)
    demo.collect(DEMO_CURRENT_BOOT_ID)
    demo.collect(DEMO_PREVIOUS_BOOT_ID)


def test_coverage_thirteen_sources_once(demo):
    for boot_id in (DEMO_CURRENT_BOOT_ID, DEMO_PREVIOUS_BOOT_ID):
        bundle = demo.collect(boot_id)
        sources = [c.source for c in bundle.coverage]
        assert len(sources) == 13
        assert set(sources) == ALL_SOURCES


def test_journal_slices_complete_and_tail_reliable(demo):
    for boot_id in (DEMO_CURRENT_BOOT_ID, DEMO_PREVIOUS_BOOT_ID):
        bundle = demo.collect(boot_id)
        cov = {c.source: c for c in bundle.coverage}
        for source in (SOURCE_JOURNAL_KERNEL, SOURCE_JOURNAL_SYSTEM):
            assert cov[source].state is SourceState.AVAILABLE
            assert cov[source].tail_reliable is True
            assert cov[source].entry_count >= 20


def test_dmesg_boot_isolation(demo):
    current = {c.source: c for c in demo.collect(DEMO_CURRENT_BOOT_ID).coverage}
    previous = {c.source: c for c in demo.collect(DEMO_PREVIOUS_BOOT_ID).coverage}
    assert current[SOURCE_DMESG].state is SourceState.EMPTY
    assert previous[SOURCE_DMESG].state is SourceState.UNSUPPORTED
    assert previous[SOURCE_DMESG].tail_reliable is False


def test_evidence_prefixes(demo):
    current = demo.collect(DEMO_CURRENT_BOOT_ID)
    previous = demo.collect(DEMO_PREVIOUS_BOOT_ID)
    cur_prefixes = {e.evidence_id[:4] for e in current.entries}
    prev_prefixes = {e.evidence_id[:4] for e in previous.entries}
    assert "JRN-" in cur_prefixes
    assert "BTM-" in cur_prefixes
    assert "AFM-" not in cur_prefixes
    assert "VMD-" not in cur_prefixes
    assert {"JRN-", "BTM-", "AFM-", "VMD-", "PST-"} <= prev_prefixes
    ids = [e.evidence_id for e in previous.entries]
    assert len(ids) == len(set(ids))


def test_previous_artifacts_and_association(demo):
    bundle = demo.collect(DEMO_PREVIOUS_BOOT_ID)
    artifacts = bundle.artifacts
    assert len(artifacts.vmcore_files) == 1
    assert len(artifacts.vmcore_dmesg) == 1
    assert len(artifacts.pstore_records) == 1
    assert artifacts.vmcore_dmesg[0].association is ArtifactAssociation.MATCHED
    assert artifacts.pstore_records[0].association is ArtifactAssociation.MATCHED
    assert artifacts.vmcore_files[0].association is ArtifactAssociation.POSSIBLY_RELATED
    assert artifacts.vmcore_files[0].readable is False
    assert artifacts.crash_kernel_loaded is True


def test_current_has_no_artifacts(demo):
    bundle = demo.collect(DEMO_CURRENT_BOOT_ID)
    assert bundle.artifacts.vmcore_files == ()
    assert bundle.artifacts.vmcore_dmesg == ()
    assert bundle.artifacts.pstore_records == ()


def test_system_profile_from_fixture(demo):
    profile = demo.collect(DEMO_CURRENT_BOOT_ID).system
    assert profile.os_name == "Fedora Linux"
    assert profile.kernel == "6.17.8-300.fc44.x86_64"
    assert profile.cpu_cores == 16
    assert profile.mem_total_kib == 32768000
    assert len(profile.gpus) == 1
    assert profile.gpus[0].driver == "amdgpu"
    assert profile.collected_at.tzinfo is UTC


def test_fake_identifiers_present_for_sanitizer(demo):
    bundle = demo.collect(DEMO_PREVIOUS_BOOT_ID)
    text = "\n".join(e.message for e in bundle.entries)
    for token in (
        "192.0.2.10",
        "02:00:00:00:00:01",
        "demo@example.com",
        "/home/demo",
        "password=",
        "postgres://",
        "DEMO-SERIAL-0001",
        "123e4567-e89b-12d3-a456-426614174000",
    ):
        assert token in text


def test_expected_findings_fixture(demo):
    expected = demo.expected_findings
    assert expected[DEMO_CURRENT_BOOT_ID]["core"] == [
        "SHD-003",
        "GPU-001",
        "GPU-002",
        "MEM-001",
        "PCI-001",
        "THM-001",
        "KRN-001",
    ]
    assert expected[DEMO_CURRENT_BOOT_ID]["deferred"] == []
    assert expected[DEMO_PREVIOUS_BOOT_ID]["core"] == [
        "SHD-002",
        "BOT-001",
        "PNC-001",
        "PNC-002",
        "GPU-003",
        "ART-001",
    ]
    assert expected[DEMO_PREVIOUS_BOOT_ID]["deferred"] == ["ART-002", "ART-003"]


def test_deterministic_bundle(demo):
    first = demo.collect(DEMO_PREVIOUS_BOOT_ID)
    second = demo.collect(DEMO_PREVIOUS_BOOT_ID)
    assert first == second


def test_metadata_evidence_helpers(demo):
    boots = demo.boots()
    btm = boots_to_evidence(boots)
    assert len(btm) == 2
    assert all(e.evidence_id.startswith("BTM-") for e in btm)
    assert all(e.source == SOURCE_JOURNAL_BOOTS for e in btm)
    assert btm[0].timestamp == boots[0].first_entry

    bundle = demo.collect(DEMO_PREVIOUS_BOOT_ID)
    afm = artifacts_to_evidence(bundle.artifacts, DEMO_PREVIOUS_BOOT_ID)
    assert len(afm) == 3
    assert all(e.evidence_id.startswith("AFM-") for e in afm)
    assert all("association=" in e.message for e in afm)
    assert all(e.boot_id == DEMO_PREVIOUS_BOOT_ID for e in afm)

    empty = artifacts_to_evidence(CrashArtifacts(), DEMO_CURRENT_BOOT_ID)
    assert empty == ()


def test_fixture_files_are_packaged(demo):
    import importlib.resources

    names = {
        "boots.json",
        "journal_current.jsonl",
        "journal_previous.jsonl",
        "system.json",
        "vmcore-dmesg.txt",
        "pstore_oops.txt",
        "expected_findings.json",
    }
    packaged = {p.name for p in importlib.resources.files("syspanic.demo_data").iterdir()}
    assert names <= packaged
    json.loads(importlib.resources.files("syspanic.demo_data").joinpath("boots.json").read_text())
