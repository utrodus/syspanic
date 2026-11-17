"""Token-based redaction over rendered text (docs/02 §11). Best-effort by design."""

import re

_TOKEN = re.compile(r"[A-Z]+_\d+")
_CRED_ASSIGN = re.compile(r"\b(password|passwd|token|api_key|secret)(\s*[=:]\s*)([^\s,;`|]+)")
_BEARER = re.compile(r"\b(Bearer\s+)([A-Za-z0-9._~+/=-]+)")
_DB_URL = re.compile(r"\b(?:postgres|postgresql|mysql|redis|mongodb)(?:\+[A-Za-z0-9]+)?://[^\s`|]+")
_USERINFO_URL = re.compile(r"\b[A-Za-z][A-Za-z0-9+.-]*://[^\s/@:`|]+:[^\s/@:`|]+@[^\s`|]+")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_HOME = re.compile(r"/home/([A-Za-z0-9._-]+)")
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_IPV6 = re.compile(r"\b[0-9A-Fa-f]{0,4}(?::[0-9A-Fa-f]{0,4}){2,7}\b")
_MAC = re.compile(r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b")
_UUID = re.compile(
    r"\b[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\b"
)
_SERIAL_ASSIGN = re.compile(r"\b(serial(?:[ _-]?number)?)(\s*[=:]\s*)([^\s,;`|]+)", re.IGNORECASE)
_SERIAL_TOKEN = re.compile(r"\b[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*-SERIAL-[A-Za-z0-9-]+\b")


def _boundary(seed: str) -> re.Pattern:
    return re.compile(rf"(?<![A-Za-z0-9_-]){re.escape(seed)}(?![A-Za-z0-9_-])")


def sanitize(text: str, *, hostnames=(), usernames=()) -> tuple[str, dict[str, int]]:
    counters: dict[str, int] = {}
    maps: dict[str, dict[str, str]] = {}

    def token(kind: str, value: str) -> str:
        mapping = maps.setdefault(kind, {})
        if value not in mapping:
            counters[kind] = counters.get(kind, 0) + 1
            mapping[value] = f"{kind}_{counters[kind]}"
        return mapping[value]

    def replace_value(match: re.Match, kind: str) -> str:
        key, sep, value = match.group(1), match.group(2), match.group(3)
        if _TOKEN.fullmatch(value):
            return match.group(0)
        return f"{key}{sep}{token(kind, value)}"

    text = _DB_URL.sub(lambda m: token("CRED", m.group(0)), text)
    text = _USERINFO_URL.sub(lambda m: token("CRED", m.group(0)), text)
    text = _CRED_ASSIGN.sub(lambda m: replace_value(m, "CRED"), text)
    text = _BEARER.sub(
        lambda m: (
            m.group(0)
            if _TOKEN.fullmatch(m.group(2))
            else m.group(1) + token("CRED", m.group(2))
        ),
        text,
    )
    text = _EMAIL.sub(lambda m: token("EMAIL", m.group(0)), text)

    user_seeds = list(dict.fromkeys(usernames))

    def home_sub(match: re.Match) -> str:
        name = match.group(1)
        if _TOKEN.fullmatch(name):
            return match.group(0)
        if name not in user_seeds:
            user_seeds.append(name)
        return f"/home/{token('USER', name)}"

    text = _HOME.sub(home_sub, text)

    for seed in sorted(set(hostnames), key=len, reverse=True):
        if seed:
            text = _boundary(seed).sub(lambda m, s=seed: token("HOST", s), text)
    for seed in user_seeds:
        if seed:
            text = _boundary(seed).sub(lambda m, s=seed: token("USER", s), text)

    text = _IPV4.sub(lambda m: token("IP", m.group(0)), text)

    def ipv6_sub(match: re.Match) -> str:
        value = match.group(0)
        if "::" in value or value.count(":") == 7:
            return token("IP", value)
        return value

    text = _IPV6.sub(ipv6_sub, text)
    text = _MAC.sub(lambda m: token("MAC", m.group(0)), text)
    text = _UUID.sub(lambda m: token("UUID", m.group(0)), text)
    text = _SERIAL_ASSIGN.sub(lambda m: replace_value(m, "SERIAL"), text)
    text = _SERIAL_TOKEN.sub(lambda m: token("SERIAL", m.group(0)), text)
    return text, {kind: count for kind, count in counters.items() if count}
