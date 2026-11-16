"""Domain enums — docs/02 §5, docs/04 §4/§8/§9. Qt-free."""

from enum import StrEnum


class Severity(StrEnum):
    CRITICAL = "critical"
    WARNING = "warning"
    NOTICE = "notice"
    INFO = "info"


class EvidenceStrength(StrEnum):
    CIRCUMSTANTIAL = "circumstantial"
    DIRECT = "direct"
    CORROBORATED = "corroborated"


class SourceState(StrEnum):
    AVAILABLE = "available"
    EMPTY = "empty"
    TRUNCATED = "truncated"
    PERMISSION_DENIED = "permission_denied"
    NOT_FOUND = "not_found"
    UNSUPPORTED = "unsupported"
    TIMEOUT = "timeout"
    ERROR = "error"


class TimelineKind(StrEnum):
    BOOT_START = "boot_start"
    BOOT_END = "boot_end"
    RULE_MATCH = "rule_match"
    SHUTDOWN_MARKER = "shutdown_marker"
    TRANSITION = "transition"


class ArtifactAssociation(StrEnum):
    MATCHED = "matched"
    POSSIBLY_RELATED = "possibly_related"
    UNKNOWN = "unknown"
