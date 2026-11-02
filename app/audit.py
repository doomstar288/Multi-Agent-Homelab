"""Tamper-evident audit log.

Each entry stores the hash of the previous entry, so changing or removing any
row breaks the chain from that point on. verify() walks the chain and reports
the first broken entry.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any

GENESIS = "0" * 64
_lock = threading.Lock()


def _digest(prev_hash: str, ts: str, actor: str, action: str, detail: str) -> str:
    payload = json.dumps([prev_hash, ts, actor, action, detail], separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def record(conn: sqlite3.Connection, actor: str, action: str, detail: dict[str, Any] | None = None) -> str:
    detail_json = json.dumps(detail or {}, sort_keys=True, separators=(",", ":"))
    ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    with _lock:
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute("SELECT hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
            prev = row["hash"] if row else GENESIS
            h = _digest(prev, ts, actor, action, detail_json)
            conn.execute(
                "INSERT INTO audit_log (ts, actor, action, detail, prev_hash, hash) VALUES (?,?,?,?,?,?)",
                (ts, actor, action, detail_json, prev, h),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    return h


def recent(conn: sqlite3.Connection, limit: int = 50) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, ts, actor, action, detail FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [{**dict(r), "detail": json.loads(r["detail"])} for r in rows]


def verify(conn: sqlite3.Connection) -> dict[str, Any]:
    prev = GENESIS
    count = 0
    for r in conn.execute("SELECT * FROM audit_log ORDER BY id"):
        expected = _digest(prev, r["ts"], r["actor"], r["action"], r["detail"])
        if r["prev_hash"] != prev or r["hash"] != expected:
            return {"ok": False, "entries": count, "broken_at": r["id"]}
        prev = r["hash"]
        count += 1
    return {"ok": True, "entries": count, "broken_at": None}
