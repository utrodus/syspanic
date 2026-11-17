"""Boot and artifact metadata evidence (BTM-*/AFM-*) — never file contents."""

from syspanic.constants import (
    SOURCE_CRASH_PSTORE,
    SOURCE_CRASH_VMCORE,
    SOURCE_CRASH_VMCORE_DMESG,
    SOURCE_JOURNAL_BOOTS,
)
from syspanic.domain.models import BootInfo, CrashArtifacts, EvidenceItem

_KIND_SOURCE = {
    "vmcore": SOURCE_CRASH_VMCORE,
    "vmcore-dmesg": SOURCE_CRASH_VMCORE_DMESG,
    "pstore": SOURCE_CRASH_PSTORE,
}


def boots_to_evidence(boots: tuple[BootInfo, ...]) -> tuple[EvidenceItem, ...]:
    items = []
    for index, boot in enumerate(boots):
        window = ""
        if boot.first_entry is not None and boot.last_entry is not None:
            window = f" window {boot.first_entry.isoformat()}..{boot.last_entry.isoformat()}"
        items.append(
            EvidenceItem(
                evidence_id=f"BTM-{index:06d}",
                source=SOURCE_JOURNAL_BOOTS,
                boot_id=boot.boot_id,
                message=f"boot index {boot.index} id {boot.boot_id}{window}",
                timestamp=boot.first_entry,
            )
        )
    return tuple(items)


def artifacts_to_evidence(
    artifacts: CrashArtifacts, boot_id: str
) -> tuple[EvidenceItem, ...]:
    records = artifacts.vmcore_files + artifacts.vmcore_dmesg + artifacts.pstore_records
    items = []
    for index, record in enumerate(records):
        items.append(
            EvidenceItem(
                evidence_id=f"AFM-{index:06d}",
                source=_KIND_SOURCE.get(record.kind, SOURCE_CRASH_VMCORE),
                boot_id=boot_id,
                message=(
                    f"{record.kind} {record.path} size={record.size_bytes} "
                    f"association={record.association.value}"
                ),
                timestamp=record.mtime,
            )
        )
    return tuple(items)
