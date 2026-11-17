"""T-015: token redaction — seeds, stable numbering, retention, idempotence."""

from syspanic.report.sanitize import sanitize

BOOT_ID = "a1b2c3d4e5f60718293a4b5c6d7e8f90"


def test_hostname_seeds_numbered_stably():
    text = "host alpha failed; alpha again; beta unrelated; alpha third"
    out, counts = sanitize(text, hostnames=("alpha", "beta"))
    assert out == "host HOST_1 failed; HOST_1 again; HOST_2 unrelated; HOST_1 third"
    assert counts["HOST"] == 2


def test_ip_like_hostname_seed_wins_over_ip_token():
    out, counts = sanitize("node 10.0.0.5 booted", hostnames=("10.0.0.5",))
    assert "HOST_1" in out
    assert "IP_" not in out
    assert counts.get("IP", 0) == 0


def test_username_boundary_keeps_process_names():
    out, _ = sanitize("demo-app[4321]: session for demo ended", usernames=("demo",))
    assert "demo-app[4321]" in out
    assert "USER_1" in out
    assert "for demo" not in out


def test_home_path_redacted_and_correlates_with_username():
    out, counts = sanitize("cwd /home/demo and user demo logged in", usernames=("demo",))
    assert "/home/USER_1" in out
    assert "user USER_1" in out
    assert "/home/demo" not in out
    assert counts["USER"] == 1


def test_home_path_discovery_seeds_username():
    out, _ = sanitize("path /home/alice then alice again")
    assert "/home/USER_1" in out
    assert "then USER_1 again" in out


def test_ipv4_redacted():
    out, counts = sanitize("peer 192.0.2.10 and 198.51.100.7 and 192.0.2.10")
    assert "IP_1" in out and "IP_2" in out
    assert "192.0.2.10" not in out
    assert counts["IP"] == 2


def test_ipv6_full_and_compressed():
    out, _ = sanitize("addr 2001:0db8:0000:0000:0000:0000:0000:0001 or 2001:db8::1")
    assert "2001:" not in out
    assert out.count("IP_") == 2


def test_mac_redacted_pci_and_versions_retained():
    text = (
        "mac 02:00:00:00:00:01 pci 0000:0a:00.0 kernel 6.17.8-300.fc44.x86_64 "
        "at 08:27:41 count 5"
    )
    out, _ = sanitize(text)
    assert "02:00:00:00:00:01" not in out
    assert "MAC_1" in out
    assert "0000:0a:00.0" in out
    assert "6.17.8-300.fc44.x86_64" in out
    assert "08:27:41" in out
    assert "count 5" in out


def test_email_redacted():
    out, counts = sanitize("contact demo@example.com please")
    assert "demo@example.com" not in out
    assert "EMAIL_1" in out
    assert counts["EMAIL"] == 1


def test_dashed_uuid_redacted_boot_id_retained():
    text = f"uuid 123e4567-e89b-12d3-a456-426614174000 boot {BOOT_ID}"
    out, counts = sanitize(text)
    assert "123e4567-e89b-12d3-a456-426614174000" not in out
    assert "UUID_1" in out
    assert BOOT_ID in out
    assert counts["UUID"] == 1


def test_serial_token_and_assignment():
    out, _ = sanitize("device serial DEMO-SERIAL-0001 and Serial Number: ABC123XYZ")
    assert "DEMO-SERIAL-0001" not in out
    assert "ABC123XYZ" not in out
    assert out.count("SERIAL_") == 2


def test_credential_assignments_keep_key():
    text = "config password=DemoPass123 api_key=sk-demo-123 token=tok-demo-456 secret=s3cr3t"
    out, counts = sanitize(text)
    for leak in ("DemoPass123", "sk-demo-123", "tok-demo-456", "s3cr3t"):
        assert leak not in out
    assert "password=CRED_" in out
    assert "api_key=CRED_" in out
    assert "token=CRED_" in out
    assert "secret=CRED_" in out
    assert counts["CRED"] == 4


def test_passwd_variant():
    out, _ = sanitize("passwd=OldStyle1")
    assert "OldStyle1" not in out
    assert "passwd=CRED_1" in out


def test_bearer_token():
    out, _ = sanitize("Authorization: Bearer eyJdemoTokenValue")
    assert "eyJdemoTokenValue" not in out
    assert "Bearer CRED_1" in out


def test_db_connection_strings():
    for url in (
        "postgres://demo:dbsecret@db.internal:5432/app",
        "mysql://u:p@host/db",
        "redis://:pw@cache:6379",
        "mongodb://u:p@mongo:27017",
    ):
        out, _ = sanitize(f"db {url} end")
        assert url not in out
        assert "CRED_1" in out
        assert "dbsecret" not in out


def test_https_userinfo_url():
    out, _ = sanitize("fetch https://user:pass@api.example.com/v1 done")
    assert "user:pass@" not in out
    assert "CRED_1" in out


def test_idempotent_on_already_redacted():
    text = (
        "host alpha user demo /home/demo 192.0.2.10 02:00:00:00:00:01 "
        "demo@example.com 123e4567-e89b-12d3-a456-426614174000 DEMO-SERIAL-0001 "
        "password=DemoPass123 Bearer eyJdemoTokenValue postgres://demo:dbsecret@db.internal:5432/app"
    )
    once, counts1 = sanitize(text, hostnames=("alpha",), usernames=("demo",))
    twice, counts2 = sanitize(once, hostnames=("alpha",), usernames=("demo",))
    assert once == twice
    assert counts2 == {} or all(v == 0 for v in counts2.values())
    assert counts1  # first pass did redact


def test_empty_text():
    out, counts = sanitize("")
    assert out == ""
    assert counts == {} or all(v == 0 for v in counts.values())


def test_unknown_secret_may_remain_best_effort():
    out, _ = sanitize("opaque value hunter2 stays")
    assert "hunter2" in out  # documented best-effort limitation


def test_redaction_inside_fenced_excerpt():
    text = "```text\npassword=DemoPass123 host alpha\n```"
    out, _ = sanitize(text, hostnames=("alpha",))
    assert "DemoPass123" not in out
    assert "alpha" not in out
    assert "```text" in out


def test_boot_id_survives_full_pipeline():
    text = (
        f"boot {BOOT_ID} incident /var/crash/127.0.0.1-2026-11-10-08:30:00 "
        f"matched by boot ID {BOOT_ID}"
    )
    out, _ = sanitize(text)
    assert out.count(BOOT_ID) == 2
    assert "127.0.0.1" not in out
