"""T-008: crash artifact collector — bounded scans, association, synthetic tmp fixtures."""

import os
from datetime import UTC, datetime, timedelta

from syspanic.collectors import artifacts
from syspanic.collectors.base import CollectionContext
from syspanic.constants import (
    SOURCE_CRASH_KEXEC,
    SOURCE_CRASH_PSTORE,
    SOURCE_CRASH_VMCORE,
    SOURCE_CRASH_VMCORE_DMESG,
)
from syspanic.domain.enums import ArtifactAssociation, SourceState
from syspanic.domain.models import BootInfo, CrashArtifacts

BOOT_ID = "0f1e2d3c4b5a69788796a5b4c3d2e1f0"
KERNEL = "6.17.8-300.fc44.x86_64"
WINDOW_START = datetime(2026, 11, 10, 8, 0, tzinfo=UTC)
WINDOW_END = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)
INCIDENT_NAME = "127.0.0.1-2026-11-10-08:30:00"
VMD_TEXT = (
    f"BOOT_ID={BOOT_ID}\n"
    f"Linux version {KERNEL} (mockbuild@fedora) #1 SMP PREEMPT_DYNAMIC\n"
    "2026-11-10T08:29:58+00:00 amdgpu: ring gfx timeout\n"
    "2026-11-10T08:29:59+00:00 Kernel panic - not syncing: Fatal exception\n"
)


def make_boot(**overrides):
    fields = {
        "index": -1,
        "boot_id": BOOT_ID,
        "is_current": False,
        "first_entry": WINDOW_START,
        "last_entry": WINDOW_END,
        "kernel_release": KERNEL,
    }
    fields.update(overrides)
    return BootInfo(**fields)


class FakeReader:
    def __init__(self, mapping=None):
        self.mapping = dict(mapping or {})
        self.reads = []

    def __call__(self, path):
        self.reads.append(path)
        return self.mapping.get(path)


def kexec_reader(loaded="1", size="268435456"):
    mapping = {}
    if loaded is not None:
        mapping[artifacts.KEXEC_LOADED_PATH] = loaded
    if size is not None:
        mapping[artifacts.KEXEC_SIZE_PATH] = size
    return FakeReader(mapping)


def build_tree(tmp_path, *, dmesg_text=VMD_TEXT, incident_name=INCIDENT_NAME):
    root = tmp_path / "var_crash"
    root.mkdir(exist_ok=True)
    (root / "vmcore").write_bytes(b"\x00" * 4096)
    incident = root / incident_name
    incident.mkdir(exist_ok=True)
    (incident / "vmcore").write_bytes(b"\x00" * 8192)
    (incident / "vmcore-dmesg.txt").write_text(dmesg_text)
    pstore = tmp_path / "pstore"
    pstore.mkdir(exist_ok=True)
    (pstore / "dmesg-ramoops-0").write_text("2026-11-10T08:29:59+00:00 Oops: 0000 [#1] SMP\n")
    return root, pstore


def collect(
    tmp_path, *, boot=None, reader=None, crash_root=None, pstore_roots=None, monkeypatch=None
):
    root, pstore = build_tree(tmp_path)
    return collect_roots(
        crash_root or root,
        pstore_roots or (pstore,),
        boot=boot,
        reader=reader,
        monkeypatch=monkeypatch,
    )


def collect_roots(crash_root, pstore_roots, *, boot=None, reader=None, monkeypatch=None):
    ctx = CollectionContext(boot=boot if boot is not None else make_boot())
    result = artifacts.collect_artifacts(
        ctx,
        crash_root=str(crash_root),
        pstore_roots=tuple(str(p) for p in pstore_roots),
        read_text=reader if reader is not None else kexec_reader(),
    )
    return result


def coverage_by_source(result):
    return {c.source: c for c in result.coverage}


def test_vmcore_metadata_only_and_never_opened(tmp_path, monkeypatch):
    reads = []
    real = artifacts._read_artifact_text

    def spy(path, **kwargs):
        reads.append(str(path))
        return real(path, **kwargs)

    monkeypatch.setattr(artifacts, "_read_artifact_text", spy)
    result = collect(tmp_path, monkeypatch=monkeypatch)
    payload = result.payload.artifacts
    assert isinstance(payload, CrashArtifacts)
    assert len(payload.vmcore_files) == 2
    sizes = sorted(a.size_bytes for a in payload.vmcore_files)
    assert sizes == [4096, 8192]
    assert all(a.kind == "vmcore" for a in payload.vmcore_files)
    assert all(a.readable is False for a in payload.vmcore_files)
    assert all(a.mtime is not None for a in payload.vmcore_files)
    assert not any(path.endswith("vmcore") for path in reads)


def test_symlinks_skipped(tmp_path):
    root, pstore = build_tree(tmp_path)
    (root / "vmcore-link").symlink_to(root / "vmcore")
    incident = root / INCIDENT_NAME
    (incident / "vmcore-dmesg-link.txt").symlink_to(incident / "vmcore-dmesg.txt")
    result = collect_roots(root, (pstore,))
    payload = result.payload.artifacts
    paths = [a.path for a in payload.vmcore_files + payload.vmcore_dmesg]
    assert not any("link" in os.path.basename(p) for p in paths)


def test_non_regular_files_skipped(tmp_path):
    root, pstore = build_tree(tmp_path)
    os.mkfifo(root / "vmcore-fifo")
    result = collect_roots(root, (pstore,))
    assert not any("fifo" in a.path for a in result.payload.artifacts.vmcore_files)


def test_no_deep_recursion(tmp_path):
    root, pstore = build_tree(tmp_path)
    nested = root / INCIDENT_NAME / "nested"
    nested.mkdir()
    (nested / "vmcore").write_bytes(b"\x00" * 16)
    result = collect_roots(root, (pstore,))
    assert not any("nested" in a.path for a in result.payload.artifacts.vmcore_files)


def test_incident_dir_limit(tmp_path):
    root = tmp_path / "crash"
    root.mkdir()
    for i in range(25):
        incident = root / f"127.0.0.1-2026-11-10-08:{i:02d}:00"
        incident.mkdir()
        (incident / "vmcore").write_bytes(b"\x00" * 8)
    result = collect_roots(root, ())
    payload = result.payload.artifacts
    dirs = {a.incident_dir for a in payload.vmcore_files}
    assert len(dirs) <= 20
    assert any("limit" in note.lower() for note in payload.notes)


def test_total_entry_limit(tmp_path):
    root = tmp_path / "crash"
    root.mkdir()
    for i in range(60):
        (root / f"vmcore-{i}").write_bytes(b"\x00" * 8)
    result = collect_roots(root, ())
    payload = result.payload.artifacts
    total = len(payload.vmcore_files) + len(payload.vmcore_dmesg) + len(payload.pstore_records)
    assert total <= 50
    assert any("limit" in note.lower() for note in payload.notes)


def test_vmcore_dmesg_text_becomes_evidence(tmp_path):
    result = collect(tmp_path)
    entries = result.payload.entries
    vmd = [e for e in entries if e.evidence_id.startswith("VMD-")]
    assert vmd
    assert all(e.source == SOURCE_CRASH_VMCORE_DMESG for e in vmd)
    assert all(e.boot_id == BOOT_ID for e in vmd)
    assert any("Kernel panic" in e.message for e in vmd)
    assert coverage_by_source(result)[SOURCE_CRASH_VMCORE_DMESG].state is SourceState.AVAILABLE


def test_vmcore_dmesg_byte_cap(tmp_path):
    big = "2026-11-10T08:29:59+00:00 line\n" * 12000  # ~348 KiB
    root, pstore = build_tree(tmp_path, dmesg_text=big)
    result = collect_roots(root, (pstore,))
    vmd = [e for e in result.payload.entries if e.evidence_id.startswith("VMD-")]
    total_chars = sum(len(e.message) for e in vmd)
    assert total_chars <= 256 * 1024
    assert any("cap" in note.lower() for note in result.payload.artifacts.notes)


def test_vmcore_dmesg_line_cap(tmp_path):
    text = "".join(f"2026-11-10T08:29:59+00:00 line {i}\n" for i in range(3000))
    root, pstore = build_tree(tmp_path, dmesg_text=text)
    result = collect_roots(root, (pstore,))
    vmd = [e for e in result.payload.entries if e.evidence_id.startswith("VMD-")]
    assert len(vmd) <= 2000
    assert any("cap" in note.lower() for note in result.payload.artifacts.notes)


def test_pstore_record_caps(tmp_path):
    root = tmp_path / "crash"
    root.mkdir()
    pstore = tmp_path / "pstore"
    pstore.mkdir()
    for i in range(7):
        (pstore / f"dmesg-ramoops-{i}").write_text("x" * (100 * 1024))
    result = collect_roots(root, (pstore,))
    payload = result.payload.artifacts
    assert len(payload.pstore_records) == 5
    pst = [e for e in result.payload.entries if e.evidence_id.startswith("PST-")]
    assert all(len(e.message) <= 64 * 1024 for e in pst)
    assert any("limit" in note.lower() or "cap" in note.lower() for note in payload.notes)


def test_pstore_depth_one_only(tmp_path):
    root = tmp_path / "crash"
    root.mkdir()
    pstore = tmp_path / "pstore"
    pstore.mkdir()
    (pstore / "dmesg-ramoops-0").write_text("record\n")
    sub = pstore / "subdir"
    sub.mkdir()
    (sub / "dmesg-ramoops-1").write_text("deep\n")
    result = collect_roots(root, (pstore,))
    assert len(result.payload.artifacts.pstore_records) == 1


def test_pstore_both_roots_merged(tmp_path):
    root = tmp_path / "crash"
    root.mkdir()
    p1 = tmp_path / "p1"
    p2 = tmp_path / "p2"
    p1.mkdir()
    p2.mkdir()
    (p1 / "dmesg-ramoops-0").write_text("a\n")
    (p2 / "dmesg-ramoops-1").write_text("b\n")
    result = collect_roots(root, (p1, p2))
    assert len(result.payload.artifacts.pstore_records) == 2


def test_missing_roots_reported_not_raised(tmp_path):
    result = collect_roots(tmp_path / "absent", (tmp_path / "absent-pstore",))
    cov = coverage_by_source(result)
    assert cov[SOURCE_CRASH_VMCORE].state is SourceState.NOT_FOUND
    assert cov[SOURCE_CRASH_VMCORE_DMESG].state is SourceState.NOT_FOUND
    assert cov[SOURCE_CRASH_PSTORE].state is SourceState.NOT_FOUND
    payload = result.payload.artifacts
    assert payload.vmcore_files == ()
    assert payload.vmcore_dmesg == ()
    assert payload.pstore_records == ()


def test_permission_denied_root_reported(tmp_path, monkeypatch):
    root, pstore = build_tree(tmp_path)
    real_scandir = os.scandir

    def guarded(path):
        if str(path) == str(root):
            raise PermissionError("permission denied")
        return real_scandir(path)

    monkeypatch.setattr(artifacts.os, "scandir", guarded)
    result = collect_roots(root, (pstore,))
    cov = coverage_by_source(result)
    assert cov[SOURCE_CRASH_VMCORE].state is SourceState.PERMISSION_DENIED
    assert cov[SOURCE_CRASH_VMCORE].tail_reliable is False
    assert any(i.source == SOURCE_CRASH_VMCORE for i in result.issues)


def test_kexec_loaded_states(tmp_path):
    result = collect(tmp_path, reader=kexec_reader(loaded="1"))
    assert result.payload.artifacts.crash_kernel_loaded is True
    assert coverage_by_source(result)[SOURCE_CRASH_KEXEC].state is SourceState.AVAILABLE

    result = collect(tmp_path, reader=kexec_reader(loaded="0"))
    assert result.payload.artifacts.crash_kernel_loaded is False

    result = collect(tmp_path, reader=kexec_reader(loaded=None, size=None))
    assert result.payload.artifacts.crash_kernel_loaded is None
    assert coverage_by_source(result)[SOURCE_CRASH_KEXEC].state is SourceState.NOT_FOUND


def test_associate_matched_by_boot_id_in_text():
    assoc, reason = artifacts.associate(make_boot(), text=f"BOOT_ID={BOOT_ID}\n")
    assert assoc is ArtifactAssociation.MATCHED
    assert reason


def test_associate_matched_by_boot_id_in_incident_dir():
    assoc, _ = artifacts.associate(make_boot(), incident_dir=f"/var/crash/{BOOT_ID}")
    assert assoc is ArtifactAssociation.MATCHED


def test_associate_timestamp_and_release_never_matched():
    text = f"Linux version {KERNEL}\n"
    assoc, reason = artifacts.associate(
        make_boot(), text=text, incident_dir=f"/var/crash/{INCIDENT_NAME}"
    )
    assert assoc is ArtifactAssociation.POSSIBLY_RELATED
    assert assoc is not ArtifactAssociation.MATCHED
    assert reason


def test_associate_mtime_only_is_possibly_related():
    mtime = WINDOW_START + timedelta(minutes=30)
    assoc, reason = artifacts.associate(make_boot(), mtime=mtime)
    assert assoc is ArtifactAssociation.POSSIBLY_RELATED
    assert "mtime" in reason.lower()


def test_associate_unknown_without_correlation():
    assoc, _ = artifacts.associate(
        make_boot(), mtime=WINDOW_END + timedelta(days=2), text="nothing relevant\n"
    )
    assert assoc is ArtifactAssociation.UNKNOWN


def test_associate_without_boot_window():
    boot = make_boot(first_entry=None, last_entry=None)
    assoc, _ = artifacts.associate(boot, mtime=WINDOW_START)
    assert assoc is ArtifactAssociation.UNKNOWN
    assoc, _ = artifacts.associate(boot, text=f"BOOT_ID={BOOT_ID}")
    assert assoc is ArtifactAssociation.MATCHED


def test_collect_association_integration(tmp_path):
    root, pstore = build_tree(tmp_path)
    incident = root / INCIDENT_NAME
    stamp = (WINDOW_START + timedelta(minutes=30)).timestamp()
    os.utime(incident / "vmcore", (stamp, stamp))
    result = collect_roots(root, (pstore,))
    payload = result.payload.artifacts
    dmesg = payload.vmcore_dmesg[0]
    assert dmesg.association is ArtifactAssociation.MATCHED
    assert dmesg.association_reason
    vmcore_in_incident = [a for a in payload.vmcore_files if a.incident_dir][0]
    assert vmcore_in_incident.association is ArtifactAssociation.POSSIBLY_RELATED


def test_denied_dmesg_read_reported(tmp_path, monkeypatch):
    def denied(path, **kwargs):
        raise PermissionError("permission denied")

    monkeypatch.setattr(artifacts, "_read_artifact_text", denied)
    result = collect(tmp_path)
    payload = result.payload.artifacts
    assert len(payload.vmcore_dmesg) == 1
    assert payload.vmcore_dmesg[0].readable is False
    cov = coverage_by_source(result)[SOURCE_CRASH_VMCORE_DMESG]
    assert cov.state is SourceState.PERMISSION_DENIED
    assert cov.tail_reliable is False


def test_cancelled_collection_stops_early(tmp_path):
    import threading

    root, pstore = build_tree(tmp_path)
    cancel = threading.Event()
    cancel.set()
    ctx = CollectionContext(boot=make_boot(), cancel=cancel)
    result = artifacts.collect_artifacts(
        ctx, crash_root=str(root), pstore_roots=(str(pstore),), read_text=kexec_reader()
    )
    assert result.payload.artifacts.vmcore_files == ()
    assert any(i.source == SOURCE_CRASH_VMCORE for i in result.issues)
