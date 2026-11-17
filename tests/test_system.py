"""T-007: system profile collectors — synthetic fixtures, injected readers/runner."""

import threading
from datetime import UTC, datetime

from syspanic.collectors import system
from syspanic.collectors.base import CollectionContext
from syspanic.collectors.runner import CommandResult
from syspanic.constants import (
    SOURCE_SYSTEM_CPU,
    SOURCE_SYSTEM_FIRMWARE,
    SOURCE_SYSTEM_GPU,
    SOURCE_SYSTEM_MEMORY,
    SOURCE_SYSTEM_OS,
)
from syspanic.domain.enums import SourceState
from syspanic.domain.models import GpuInfo, SystemProfile

OS_RELEASE = 'NAME="Fedora Linux"\nVERSION_ID="44"\n# comment\nPRETTY_NAME="Fedora Linux 44"\n'
OSRELEASE = "6.17.8-300.fc44.x86_64\n"
CPUINFO = (
    "processor\t: 0\n"
    "model name\t: AMD Ryzen 9 7950X 16-Core Processor\n"
    "microcode\t: 0xa601203\n"
    "processor\t: 1\n"
    "model name\t: AMD Ryzen 9 7950X 16-Core Processor\n"
    "microcode\t: 0xa601203\n"
)
MEMINFO = "MemTotal:       32768000 kB\nMemFree:        1024000 kB\n"
LSPCI = (
    "0000:0a:00.0 VGA compatible controller [0300]: Advanced Micro Devices, Inc. [AMD/ATI] "
    "Navi 21 [1002:73bf] (rev c1)\n"
    "\tSubsystem: Device [1da2:e435]\n"
    "\tKernel driver in use: amdgpu\n"
    "\tKernel modules: amdgpu\n"
    "0000:01:00.0 VGA compatible controller [0300]: NVIDIA Corporation GA104 "
    "[GeForce RTX 3070] [10de:2484] (rev a1)\n"
    "\tKernel driver in use: nouveau\n"
    "0000:00:1f.3 Audio device [0403]: Intel Corporation Alder Lake PCH-P HD Audio "
    "[8086:51c8] (rev 01)\n"
    "\tKernel driver in use: snd_hda_intel\n"
)
DMI = {
    system.DMI_PATHS["bios_vendor"]: "American Megatrends International, LLC.\n",
    system.DMI_PATHS["bios_version"]: "F.32\n",
    system.DMI_PATHS["bios_date"]: "07/15/2025\n",
    system.DMI_PATHS["board_vendor"]: "ASUSTeK COMPUTER INC.\n",
    system.DMI_PATHS["board_name"]: "ROG STRIX X670E-E GAMING WIFI\n",
}


def ok(stdout: str) -> CommandResult:
    return CommandResult(
        stdout=stdout.encode(),
        state=SourceState.AVAILABLE if stdout else SourceState.EMPTY,
        exit_code=0,
        elapsed_ms=1.0,
        tail_reliable=True,
    )


class FakeRunner:
    def __init__(self, mapping):
        self.mapping = {tuple(k): v for k, v in mapping.items()}
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append((tuple(argv), kwargs))
        return self.mapping.get(tuple(argv), ok(""))


class FakeReader:
    def __init__(self, mapping):
        self.mapping = dict(mapping)
        self.reads = []

    def __call__(self, path):
        self.reads.append(path)
        return self.mapping.get(path)


def full_reader():
    return FakeReader(
        {
            system.OS_RELEASE_PATH: OS_RELEASE,
            system.OSRELEASE_PATH: OSRELEASE,
            system.CPUINFO_PATH: CPUINFO,
            system.MEMINFO_PATH: MEMINFO,
            **DMI,
        }
    )


def collect(reader=None, runner=None, cancel=None):
    reader = reader if reader is not None else full_reader()
    runner = runner if runner is not None else FakeRunner({system.LSPCI_ARGV: ok(LSPCI)})
    ctx = CollectionContext(cancel=cancel, runner=runner)
    return system.collect_system(ctx, read_text=reader), reader, runner


def coverage_by_source(result):
    return {c.source: c for c in result.coverage}


def test_parse_os_release_strips_quotes_and_comments():
    parsed = system.parse_os_release(OS_RELEASE)
    assert parsed["NAME"] == "Fedora Linux"
    assert parsed["VERSION_ID"] == "44"
    assert "PRETTY_NAME" in parsed
    assert "# comment" not in parsed


def test_parse_cpuinfo_model_cores_microcode():
    model, cores, microcode = system.parse_cpuinfo(CPUINFO)
    assert model == "AMD Ryzen 9 7950X 16-Core Processor"
    assert cores == 2
    assert microcode == "0xa601203"


def test_parse_cpuinfo_missing_fields():
    model, cores, microcode = system.parse_cpuinfo("processor\t: 0\n")
    assert model is None
    assert cores == 1
    assert microcode is None


def test_parse_meminfo_total_kib():
    assert system.parse_meminfo(MEMINFO) == 32768000


def test_parse_meminfo_missing():
    assert system.parse_meminfo("MemFree: 10 kB\n") is None


def test_parse_lspci_filters_display_controllers_and_drivers():
    gpus = system.parse_lspci(LSPCI)
    assert gpus == (
        GpuInfo("0000:0a:00.0", "Advanced Micro Devices, Inc.", "Navi 21", "amdgpu"),
        GpuInfo("0000:01:00.0", "NVIDIA Corporation GA104", "GeForce RTX 3070", "nouveau"),
    )


def test_parse_lspci_no_driver():
    text = "0000:0a:00.0 VGA compatible controller [0300]: Vendor Device [1002:73bf]\n"
    gpus = system.parse_lspci(text)
    assert len(gpus) == 1
    assert gpus[0].driver is None


def test_parse_lspci_empty():
    assert system.parse_lspci("") == ()
    assert system.parse_lspci("0000:00:1f.3 Audio device [0403]: Intel HD Audio\n") == ()


def test_collect_full_profile():
    result, _, _ = collect()
    profile = result.payload
    assert isinstance(profile, SystemProfile)
    assert profile.os_name == "Fedora Linux"
    assert profile.os_version_id == "44"
    assert profile.kernel == "6.17.8-300.fc44.x86_64"
    assert profile.arch
    assert profile.cpu_model == "AMD Ryzen 9 7950X 16-Core Processor"
    assert profile.cpu_cores == 2
    assert profile.microcode == "0xa601203"
    assert profile.mem_total_kib == 32768000
    assert len(profile.gpus) == 2
    assert profile.bios_vendor == "American Megatrends International, LLC."
    assert profile.bios_version == "F.32"
    assert profile.bios_date == "07/15/2025"
    assert profile.board_vendor == "ASUSTeK COMPUTER INC."
    assert profile.board_name == "ROG STRIX X670E-E GAMING WIFI"


def test_collect_coverage_five_sources_available():
    result, _, _ = collect()
    cov = coverage_by_source(result)
    assert set(cov) == {
        SOURCE_SYSTEM_OS,
        SOURCE_SYSTEM_CPU,
        SOURCE_SYSTEM_MEMORY,
        SOURCE_SYSTEM_GPU,
        SOURCE_SYSTEM_FIRMWARE,
    }
    assert all(c.state is SourceState.AVAILABLE for c in cov.values())
    assert all(c.tail_reliable for c in cov.values())


def test_collect_missing_paths_yield_coverage_not_exceptions():
    reader = FakeReader({})
    runner = FakeRunner(
        {system.LSPCI_ARGV: CommandResult(b"", SourceState.NOT_FOUND, None, 0.5)}
    )
    result, _, _ = collect(reader=reader, runner=runner)
    profile = result.payload
    assert profile.os_name == ""
    assert profile.kernel == ""
    assert profile.cpu_model == ""
    assert profile.cpu_cores == 0
    assert profile.mem_total_kib == 0
    assert profile.gpus == ()
    assert profile.bios_vendor is None
    cov = coverage_by_source(result)
    assert all(c.state is SourceState.NOT_FOUND for c in cov.values())


def test_collect_lspci_empty_output():
    runner = FakeRunner({system.LSPCI_ARGV: ok("")})
    result, _, _ = collect(runner=runner)
    assert result.payload.gpus == ()
    assert coverage_by_source(result)[SOURCE_SYSTEM_GPU].state is SourceState.EMPTY


def test_collect_lspci_permission_denied():
    runner = FakeRunner(
        {
            system.LSPCI_ARGV: CommandResult(
                b"", SourceState.PERMISSION_DENIED, 1, 1.0, stderr_detail="permission denied"
            )
        }
    )
    result, _, _ = collect(runner=runner)
    cov = coverage_by_source(result)[SOURCE_SYSTEM_GPU]
    assert cov.state is SourceState.PERMISSION_DENIED
    assert cov.tail_reliable is False
    assert result.payload.gpus == ()


def test_collect_firmware_partial():
    mapping = {
        system.OS_RELEASE_PATH: OS_RELEASE,
        system.OSRELEASE_PATH: OSRELEASE,
        system.CPUINFO_PATH: CPUINFO,
        system.MEMINFO_PATH: MEMINFO,
        system.DMI_PATHS["bios_vendor"]: "AMI\n",
        system.DMI_PATHS["board_name"]: "BOARD\n",
    }
    result, _, _ = collect(reader=FakeReader(mapping))
    profile = result.payload
    assert profile.bios_vendor == "AMI"
    assert profile.board_name == "BOARD"
    assert profile.bios_version is None
    assert profile.bios_date is None
    assert profile.board_vendor is None
    assert coverage_by_source(result)[SOURCE_SYSTEM_FIRMWARE].state is SourceState.AVAILABLE


def test_collect_osrelease_without_os_release():
    mapping = {system.OSRELEASE_PATH: OSRELEASE}
    result, _, _ = collect(reader=FakeReader(mapping))
    assert result.payload.kernel == "6.17.8-300.fc44.x86_64"
    assert result.payload.os_name == ""
    assert coverage_by_source(result)[SOURCE_SYSTEM_OS].state is SourceState.AVAILABLE


def test_collect_reads_only_allowlisted_paths():
    _, reader, _ = collect()
    allowed = {
        system.OS_RELEASE_PATH,
        system.OSRELEASE_PATH,
        system.CPUINFO_PATH,
        system.MEMINFO_PATH,
        *system.DMI_PATHS.values(),
    }
    assert set(reader.reads) <= allowed
    for path in reader.reads:
        lowered = path.lower()
        assert "serial" not in lowered
        assert "uuid" not in lowered
        assert "machine-id" not in lowered
        assert "cmdline" not in lowered


def test_collect_collected_at_is_utc_now():
    before = datetime.now(UTC)
    result, _, _ = collect()
    after = datetime.now(UTC)
    assert result.payload.collected_at.tzinfo is UTC
    assert before <= result.payload.collected_at <= after


def test_collect_forwards_cancel_to_runner():
    cancel = threading.Event()
    _, _, runner = collect(cancel=cancel)
    assert runner.calls
    argv, kwargs = runner.calls[0]
    assert argv == tuple(system.LSPCI_ARGV)
    assert kwargs["cancel"] is cancel
    assert kwargs["timeout_s"] > 0
    assert kwargs["max_bytes"] > 0
