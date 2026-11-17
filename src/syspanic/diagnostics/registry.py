"""Rule catalog: 29 IDs in 10 families; 27 core evaluators, ART-002/003 deferred."""

from dataclasses import dataclass

from syspanic.diagnostics.rules import (
    artifacts,
    cpu_mce,
    gpu,
    kernel_health,
    memory,
    panic,
    pcie,
    shutdown,
    storage,
    thermal,
)

DEFERRED_RULE_IDS = frozenset({"ART-002", "ART-003"})

_FAMILY = {
    "SHD": "shutdown_boot",
    "BOT": "shutdown_boot",
    "PNC": "panic",
    "MCE": "cpu_mce",
    "GPU": "gpu",
    "MEM": "memory",
    "PCI": "pcie",
    "STO": "storage",
    "THM": "thermal",
    "ART": "artifacts",
    "KRN": "kernel_health",
}
_MODULE = {
    "shutdown_boot": "shutdown",
    "panic": "panic",
    "cpu_mce": "cpu_mce",
    "gpu": "gpu",
    "memory": "memory",
    "pcie": "pcie",
    "storage": "storage",
    "thermal": "thermal",
    "artifacts": "artifacts",
    "kernel_health": "kernel_health",
}
_IDS = (
    "SHD-001", "SHD-002", "SHD-003", "SHD-004",
    "BOT-001",
    "PNC-001", "PNC-002", "PNC-003", "PNC-004",
    "MCE-001", "MCE-002",
    "GPU-001", "GPU-002", "GPU-003", "GPU-004",
    "MEM-001", "MEM-002",
    "PCI-001", "PCI-002", "PCI-003",
    "STO-001", "STO-002", "STO-003",
    "THM-001", "THM-002",
    "ART-001", "ART-002", "ART-003",
    "KRN-001",
)


@dataclass(frozen=True)
class RuleSpec:
    rule_id: str
    family: str
    module: str
    deferred: bool = False


CATALOG = tuple(
    RuleSpec(
        rule_id=rule_id,
        family=_FAMILY[rule_id.split("-")[0]],
        module="" if rule_id in DEFERRED_RULE_IDS else _MODULE[_FAMILY[rule_id.split("-")[0]]],
        deferred=rule_id in DEFERRED_RULE_IDS,
    )
    for rule_id in _IDS
)

CORE_RULE_IDS = frozenset(spec.rule_id for spec in CATALOG if not spec.deferred)

RULE_MODULES = {
    "shutdown": shutdown,
    "panic": panic,
    "cpu_mce": cpu_mce,
    "gpu": gpu,
    "memory": memory,
    "pcie": pcie,
    "storage": storage,
    "thermal": thermal,
    "artifacts": artifacts,
    "kernel_health": kernel_health,
}
