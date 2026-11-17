"""System profile collectors — fixed allowlisted paths only (docs/02 §10).

Inventory is collected now, never a crash-time measurement.
"""

import os
import re
from datetime import UTC, datetime

from syspanic.collectors.base import CollectionContext, CollectorResult
from syspanic.constants import (
    FIXED_READ_MAX_BYTES,
    LSPCI_MAX_BYTES,
    LSPCI_TIMEOUT_S,
    SOURCE_SYSTEM_CPU,
    SOURCE_SYSTEM_FIRMWARE,
    SOURCE_SYSTEM_GPU,
    SOURCE_SYSTEM_MEMORY,
    SOURCE_SYSTEM_OS,
)
from syspanic.domain.enums import SourceState
from syspanic.domain.models import GpuInfo, SourceCoverage, SystemProfile

OS_RELEASE_PATH = "/etc/os-release"
OSRELEASE_PATH = "/proc/sys/kernel/osrelease"
CPUINFO_PATH = "/proc/cpuinfo"
MEMINFO_PATH = "/proc/meminfo"
DMI_PATHS = {
    "bios_vendor": "/sys/class/dmi/id/bios_vendor",
    "bios_version": "/sys/class/dmi/id/bios_version",
    "bios_date": "/sys/class/dmi/id/bios_date",
    "board_vendor": "/sys/class/dmi/id/board_vendor",
    "board_name": "/sys/class/dmi/id/board_name",
}
LSPCI_ARGV = ("lspci", "-Dnnk")

_GPU_LINE = re.compile(
    r"^(\S+)\s+(?:VGA compatible controller|3D controller|Display controller)"
    r"\s+\[[0-9a-fA-F]+\]:\s+(.*)$"
)
_IDS_SUFFIX = re.compile(
    r"\s*\[[0-9a-fA-F]{4}:[0-9a-fA-F]{4}\](?:\s*\(rev [0-9a-fA-F]+\))?\s*$"
)


def _read_fixed_path(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read(FIXED_READ_MAX_BYTES)
    except OSError:
        return None


def parse_os_release(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def parse_cpuinfo(text: str) -> tuple[str | None, int, str | None]:
    model = None
    microcode = None
    cores = 0
    for line in text.splitlines():
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if key == "processor":
            cores += 1
        elif key == "model name" and model is None:
            model = value
        elif key == "microcode" and microcode is None:
            microcode = value
    return model, cores, microcode


def parse_meminfo(text: str) -> int | None:
    for line in text.splitlines():
        if line.startswith("MemTotal:"):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                return int(parts[1])
    return None


def parse_lspci(text: str) -> tuple[GpuInfo, ...]:
    gpus: list[GpuInfo] = []
    current: list | None = None
    for line in text.splitlines():
        match = _GPU_LINE.match(line)
        if match:
            if current is not None:
                gpus.append(GpuInfo(*current))
            rest = _IDS_SUFFIX.sub("", match.group(2)).strip()
            vendor = rest.split("[", 1)[0].strip()
            model_raw = rest[len(vendor) :].strip()
            bracket = re.match(r"^\[([^\]]*)\]\s*(.*)$", model_raw)
            model = (bracket.group(2).strip() or bracket.group(1)) if bracket else model_raw
            current = [match.group(1), vendor, model or vendor, None]
        elif current is not None and line[:1].isspace():
            stripped = line.strip()
            if stripped.startswith("Kernel driver in use:"):
                current[3] = stripped.partition(":")[2].strip() or None
        elif line.strip() and current is not None:
            gpus.append(GpuInfo(*current))
            current = None
    if current is not None:
        gpus.append(GpuInfo(*current))
    return tuple(gpus)


def _dmi_value(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    return value or None


def collect_system(
    ctx: CollectionContext, *, read_text=_read_fixed_path
) -> CollectorResult:
    os_release_text = read_text(OS_RELEASE_PATH)
    osrelease = read_text(OSRELEASE_PATH)
    cpuinfo = read_text(CPUINFO_PATH)
    meminfo = read_text(MEMINFO_PATH)
    dmi = {key: _dmi_value(read_text(path)) for key, path in DMI_PATHS.items()}

    os_values = parse_os_release(os_release_text) if os_release_text else {}
    kernel = (osrelease or "").strip()
    model, cores, microcode = parse_cpuinfo(cpuinfo) if cpuinfo else (None, 0, None)
    mem_total = parse_meminfo(meminfo) if meminfo else None

    lspci = ctx.runner(
        LSPCI_ARGV,
        timeout_s=LSPCI_TIMEOUT_S,
        max_bytes=LSPCI_MAX_BYTES,
        cancel=ctx.cancel,
    )
    gpus: tuple[GpuInfo, ...] = ()
    if lspci.state in (SourceState.AVAILABLE, SourceState.EMPTY, SourceState.TRUNCATED):
        gpus = parse_lspci(lspci.stdout.decode("utf-8", errors="replace"))

    profile = SystemProfile(
        os_name=os_values.get("NAME", ""),
        os_version_id=os_values.get("VERSION_ID", ""),
        kernel=kernel,
        arch=os.uname().machine,
        cpu_model=model or "",
        cpu_cores=cores,
        mem_total_kib=mem_total or 0,
        collected_at=datetime.now(UTC),
        microcode=microcode,
        gpus=gpus,
        bios_vendor=dmi["bios_vendor"],
        bios_version=dmi["bios_version"],
        bios_date=dmi["bios_date"],
        board_vendor=dmi["board_vendor"],
        board_name=dmi["board_name"],
    )

    def fixed_coverage(source: str, present: bool) -> SourceCoverage:
        return SourceCoverage(
            source=source,
            state=SourceState.AVAILABLE if present else SourceState.NOT_FOUND,
            detail="" if present else "allowlisted file not readable",
        )

    coverage = (
        fixed_coverage(SOURCE_SYSTEM_OS, bool(os_release_text or osrelease)),
        fixed_coverage(SOURCE_SYSTEM_CPU, bool(cpuinfo)),
        fixed_coverage(SOURCE_SYSTEM_MEMORY, bool(meminfo)),
        SourceCoverage(
            source=SOURCE_SYSTEM_GPU,
            state=lspci.state,
            detail=lspci.stderr_detail,
            tail_reliable=lspci.tail_reliable,
            elapsed_ms=lspci.elapsed_ms,
        ),
        fixed_coverage(SOURCE_SYSTEM_FIRMWARE, any(v is not None for v in dmi.values())),
    )
    return CollectorResult(payload=profile, coverage=coverage)
