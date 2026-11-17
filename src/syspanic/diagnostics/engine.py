"""Pure deterministic engine: evaluate rules, corroborate, sort, validate (docs/04)."""

from dataclasses import replace
from datetime import UTC, datetime

from syspanic import __version__
from syspanic.diagnostics import registry
from syspanic.diagnostics.timeline import build_timeline
from syspanic.domain.enums import EvidenceStrength, Severity
from syspanic.domain.models import IncidentReport, validate_report

_SEVERITY_ORDER = {
    Severity.CRITICAL: 0,
    Severity.WARNING: 1,
    Severity.NOTICE: 2,
    Severity.INFO: 3,
}


def _corroborate(findings: list) -> list:
    by_rule = {f.rule_id: f for f in findings}
    mce = by_rule.get("MCE-001")
    mem = by_rule.get("MEM-002")
    if mce is not None and mem is not None:
        mce_ids = {ref.evidence_id for ref in mce.evidence}
        mem_ids = {ref.evidence_id for ref in mem.evidence}
        if mce_ids.isdisjoint(mem_ids):
            by_rule["MCE-001"] = replace(mce, strength=EvidenceStrength.CORROBORATED)
            by_rule["MEM-002"] = replace(mem, strength=EvidenceStrength.CORROBORATED)
    return list(by_rule.values())


def analyze(bundle, *, now: datetime | None = None) -> IncidentReport:
    findings = []
    for module in registry.RULE_MODULES.values():
        findings.extend(module.evaluate(bundle))
    findings = _corroborate(findings)
    findings.sort(key=lambda f: (_SEVERITY_ORDER[f.severity], f.rule_id))
    report = IncidentReport(
        boot=bundle.boot,
        findings=tuple(findings),
        timeline=build_timeline(bundle, findings),
        coverage=bundle.coverage,
        evidence=bundle.entries,
        generated_at=now if now is not None else datetime.now(UTC),
        app_version=__version__,
        system=bundle.system,
        artifacts=bundle.artifacts,
        demo=bundle.demo,
    )
    validate_report(report, bundle)
    return report
