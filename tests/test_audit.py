import sqlite3

import pytest

from app import audit, db

from .conftest import AUTH


@pytest.fixture
def conn(tmp_path):
    return db.connect(tmp_path / "a.db")


def test_chain_verifies(conn):
    for i in range(5):
        audit.record(conn, "matt", "test", {"i": i})
    assert audit.verify(conn) == {"ok": True, "entries": 5, "broken_at": None}


def test_log_is_append_only(conn):
    audit.record(conn, "matt", "test")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE audit_log SET actor='mallory'")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM audit_log")


def test_tampering_is_detected(conn):
    for i in range(3):
        audit.record(conn, "matt", "test", {"i": i})
    # Bypass the triggers to simulate someone editing the file directly.
    conn.execute("DROP TRIGGER audit_log_no_update")
    conn.execute("UPDATE audit_log SET detail='{\"i\":99}' WHERE id=2")
    assert audit.verify(conn) == {"ok": False, "entries": 1, "broken_at": 2}


def test_startup_is_audited(client):
    entries = client.get("/api/audit", headers=AUTH).json()
    assert entries[0]["action"] == "startup"
    assert client.get("/api/audit/verify", headers=AUTH).json()["ok"] is True


def test_provider_status_never_leaks_keys(client):
    r = client.get("/api/providers", headers=AUTH)
    status = {p["name"]: p["configured"] for p in r.json()}
    assert status == {"claude": True, "gemini": False, "grok": False}
    assert "sk-test" not in r.text
    assert "sk-test" not in client.get("/api/audit", headers=AUTH).text
