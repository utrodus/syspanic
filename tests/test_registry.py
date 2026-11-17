"""T-010: rule registry — 29 IDs, 10 families, 27 core, deferred tracked."""

from syspanic.diagnostics import registry
from syspanic.domain.models import RULE_IDS


def test_catalog_has_29_unique_ids():
    ids = [spec.rule_id for spec in registry.CATALOG]
    assert len(ids) == 29
    assert len(set(ids)) == 29
    assert set(ids) == set(RULE_IDS)


def test_catalog_has_ten_families():
    families = {spec.family for spec in registry.CATALOG}
    assert len(families) == 10


def test_core_is_27_and_deferred_tracked():
    core = {spec.rule_id for spec in registry.CATALOG if not spec.deferred}
    deferred = {spec.rule_id for spec in registry.CATALOG if spec.deferred}
    assert len(core) == 27
    assert deferred == {"ART-002", "ART-003"}
    assert frozenset(core) == registry.CORE_RULE_IDS
    assert frozenset(deferred) == registry.DEFERRED_RULE_IDS


def test_every_rule_has_family_and_module():
    for spec in registry.CATALOG:
        assert spec.family
        assert spec.module in registry.RULE_MODULES or spec.deferred


def test_deferred_rules_have_no_evaluator():
    for spec in registry.CATALOG:
        if spec.deferred:
            assert spec.module not in registry.RULE_MODULES
