"""DemoCollector — packaged synthetic fixtures via importlib.resources, zero host probing.

Reuses the real boot/journal collectors with a fixture-backed runner so demo and
production normalization are identical (docs/02 §12, docs/04 §12).
"""

import importlib.resources
import json
from datetime import UTC, datetime

from syspanic.collectors.artifacts import _text_evidence, associate
from syspanic.collectors.base import CollectionContext
from syspanic.collectors.boots import LIST_BOOTS_JSON_ARGV, collect_boots
from syspanic.collectors.journal import (
    DMESG_ISO_ARGV,
    DMESG_PLAIN_ARGV,
    collect_journal,
    kernel_argv,
    system_argv,
)
from syspanic.collectors.metadata import artifacts_to_evidence, boots_to_evidence
from syspanic.collectors.runner import CommandResult
from syspanic.constants import (
    SOURCE_CRASH_KEXEC,
    SOURCE_CRASH_PSTORE,
    SOURCE_CRASH_VMCORE,
    SOURCE_CRASH_VMCORE_DMESG,
    SOURCE_SYSTEM_CPU,
    SOURCE_SYSTEM_FIRMWARE,
    SOURCE_SYSTEM_GPU,
    SOURCE_SYSTEM_MEMORY,
    SOURCE_SYSTEM_OS,
)
from syspanic.domain.enums import SourceState
from syspanic.domain.models import (
    ArtifactInfo,
    BootInfo,
    CollectionBundle,
    CrashArtifacts,
    EvidenceItem,
    GpuInfo,
    SourceCoverage,
    SystemProfile,
)

DEMO_CURRENT_BOOT_ID = "a1b2c3d4e5f60718293a4b5c6d7e8f90"
DEMO_PREVIOUS_BOOT_ID = "0f1e2d3c4b5a69788796a5b4c3d2e1f0"
DEMO_HOSTNAME = "demo-host"
_INCIDENT_DIR = "/var/crash/127.0.0.1-2026-11-10-08:30:00"


def _fixture(name: str) -> str:
    return (
        importlib.resources.files("syspanic.demo_data").joinpath(name).read_text(encoding="utf-8")
    )


def _ok(text: str) -> CommandResult:
    return CommandResult(
        stdout=text.encode(),
        state=SourceState.AVAILABLE if text else SourceState.EMPTY,
        exit_code=0,
        elapsed_ms=0.0,
        tail_reliable=True,
    )


class DemoCollector:
    def __init__(self) -> None:
        self._boots_text = _fixture("boots.json")
        self._journals = {
            DEMO_CURRENT_BOOT_ID: _fixture("journal_current.jsonl"),
            DEMO_PREVIOUS_BOOT_ID: _fixture("journal_previous.jsonl"),
        }
        self._system = json.loads(_fixture("system.json"))
        self._vmd_text = _fixture("vmcore-dmesg.txt")
        self._pst_text = _fixture("pstore_oops.txt")
        self.expected_findings = json.loads(_fixture("expected_findings.json"))

    def _runner(self, boot_id: str | None):
        journal_text = self._journals.get(boot_id or "", "")
        mapping = {
            tuple(LIST_BOOTS_JSON_ARGV): _ok(self._boots_text),
            tuple(kernel_argv(boot_id or DEMO_CURRENT_BOOT_ID)): _ok(journal_text),
            tuple(system_argv(boot_id or DEMO_CURRENT_BOOT_ID)): _ok(journal_text),
            tuple(DMESG_ISO_ARGV): _ok(""),
            tuple(DMESG_PLAIN_ARGV): _ok(""),
        }

        def run(argv, **kwargs):
            return mapping.get(tuple(argv), _ok(""))

        return run

    def boots(self) -> tuple[BootInfo, ...]:
        result = collect_boots(
            CollectionContext(runner=self._runner(DEMO_CURRENT_BOOT_ID)),
            read_boot_id=lambda: DEMO_CURRENT_BOOT_ID,
        )
        return result.payload

    def _profile(self) -> SystemProfile:
        data = dict(self._system)
        data["gpus"] = tuple(GpuInfo(**gpu) for gpu in data["gpus"])
        data["collected_at"] = datetime.fromisoformat(data["collected_at"])
        return SystemProfile(**data)

    def _previous_artifacts(
        self, boot: BootInfo
    ) -> tuple[CrashArtifacts, tuple[EvidenceItem, ...], tuple[SourceCoverage, ...]]:
        mtime_vmcore = datetime(2026, 11, 10, 8, 30, 5, tzinfo=UTC)
        mtime_dmesg = datetime(2026, 11, 10, 8, 30, 6, tzinfo=UTC)
        mtime_pstore = datetime(2026, 11, 10, 8, 30, 7, tzinfo=UTC)
        assoc_vmcore, reason_vmcore = associate(
            boot, mtime=mtime_vmcore, incident_dir=_INCIDENT_DIR
        )
        assoc_dmesg, reason_dmesg = associate(
            boot, text=self._vmd_text, mtime=mtime_dmesg, incident_dir=_INCIDENT_DIR
        )
        assoc_pstore, reason_pstore = associate(boot, text=self._pst_text, mtime=mtime_pstore)
        vmcore = ArtifactInfo(
            path=f"{_INCIDENT_DIR}/vmcore",
            kind="vmcore",
            size_bytes=268435456,
            readable=False,
            association=assoc_vmcore,
            association_reason=reason_vmcore,
            mtime=mtime_vmcore,
            incident_dir=_INCIDENT_DIR,
            note="binary dump; metadata only, never opened",
        )
        dmesg = ArtifactInfo(
            path=f"{_INCIDENT_DIR}/vmcore-dmesg.txt",
            kind="vmcore-dmesg",
            size_bytes=len(self._vmd_text.encode()),
            readable=True,
            association=assoc_dmesg,
            association_reason=reason_dmesg,
            mtime=mtime_dmesg,
            incident_dir=_INCIDENT_DIR,
        )
        pstore = ArtifactInfo(
            path="/sys/fs/pstore/dmesg-ramoops-0",
            kind="pstore",
            size_bytes=len(self._pst_text.encode()),
            readable=True,
            association=assoc_pstore,
            association_reason=reason_pstore,
            mtime=mtime_pstore,
        )
        artifacts = CrashArtifacts(
            vmcore_files=(vmcore,),
            vmcore_dmesg=(dmesg,),
            pstore_records=(pstore,),
            crash_kernel_loaded=True,
        )
        vmd_items, _, _ = _text_evidence(
            self._vmd_text,
            prefix="VMD-",
            source=SOURCE_CRASH_VMCORE_DMESG,
            boot_id=boot.boot_id,
            start_index=0,
        )
        pst_items, _, _ = _text_evidence(
            self._pst_text,
            prefix="PST-",
            source=SOURCE_CRASH_PSTORE,
            boot_id=boot.boot_id,
            start_index=0,
        )
        coverage = (
            SourceCoverage(SOURCE_CRASH_VMCORE, SourceState.AVAILABLE, "demo fixture", 1),
            SourceCoverage(SOURCE_CRASH_VMCORE_DMESG, SourceState.AVAILABLE, "demo fixture", 1),
            SourceCoverage(SOURCE_CRASH_PSTORE, SourceState.AVAILABLE, "demo fixture", 1),
            SourceCoverage(SOURCE_CRASH_KEXEC, SourceState.AVAILABLE, "demo fixture"),
        )
        return artifacts, vmd_items + pst_items, coverage

    def collect(self, boot_id: str) -> CollectionBundle:
        if boot_id not in self._journals:
            raise ValueError(f"unknown demo boot: {boot_id}")
        boots = self.boots()
        selected = next(boot for boot in boots if boot.boot_id == boot_id)
        runner = self._runner(boot_id)
        boots_result = collect_boots(
            CollectionContext(runner=runner), read_boot_id=lambda: DEMO_CURRENT_BOOT_ID
        )
        journal_result = collect_journal(CollectionContext(boot=selected, runner=runner))
        boot = journal_result.payload.boot

        if boot_id == DEMO_PREVIOUS_BOOT_ID:
            artifacts, artifact_entries, artifact_coverage = self._previous_artifacts(boot)
        else:
            artifacts = CrashArtifacts(crash_kernel_loaded=True)
            artifact_entries = ()
            artifact_coverage = (
                SourceCoverage(SOURCE_CRASH_VMCORE, SourceState.EMPTY, "demo fixture"),
                SourceCoverage(SOURCE_CRASH_VMCORE_DMESG, SourceState.EMPTY, "demo fixture"),
                SourceCoverage(SOURCE_CRASH_PSTORE, SourceState.EMPTY, "demo fixture"),
                SourceCoverage(SOURCE_CRASH_KEXEC, SourceState.AVAILABLE, "demo fixture"),
            )

        system_coverage = tuple(
            SourceCoverage(source=source, state=SourceState.AVAILABLE, detail="demo fixture")
            for source in (
                SOURCE_SYSTEM_OS,
                SOURCE_SYSTEM_CPU,
                SOURCE_SYSTEM_MEMORY,
                SOURCE_SYSTEM_GPU,
                SOURCE_SYSTEM_FIRMWARE,
            )
        )
        entries = (
            journal_result.payload.entries
            + artifact_entries
            + boots_to_evidence(boots)
            + artifacts_to_evidence(artifacts, boot_id)
        )
        coverage = (
            boots_result.coverage
            + journal_result.coverage
            + system_coverage
            + artifact_coverage
        )
        return CollectionBundle(
            boot=boot,
            boots=boots,
            entries=entries,
            coverage=coverage,
            system=self._profile(),
            artifacts=artifacts,
            issues=(),
            demo=True,
            hostname_hint=DEMO_HOSTNAME,
        )
