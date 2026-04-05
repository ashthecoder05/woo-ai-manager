"""
Merchant database — SQLite via Python's built-in sqlite3.
Stores merchant sign-up details: email, gateway, platform, assistant channel.
No extra dependencies required.
"""

from __future__ import annotations
import sqlite3
import os
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "merchants.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS merchants (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                email      TEXT    NOT NULL UNIQUE,
                name       TEXT,
                gateway    TEXT,     -- blockonomics|coinbase|bitpay|stripe|nowpayments|coingate
                platforms  TEXT,     -- comma-separated: plugin,api,custom
                assistant  TEXT,     -- dash|telegram
                created_at TEXT    NOT NULL,
                updated_at TEXT    NOT NULL
            )
        """)
        conn.commit()


def upsert_merchant(
    email: str,
    name: str = "",
    gateways: list[str] | None = None,
    platforms: list[str] | None = None,
    assistant: str = "",
) -> dict:
    """Insert or update a merchant record. Returns the saved row as dict."""
    init_db()
    now = datetime.now(tz=timezone.utc).isoformat()
    gateways_str  = ",".join(gateways)  if gateways  else ""
    platforms_str = ",".join(platforms) if platforms else ""

    with _connect() as conn:
        existing = conn.execute(
            "SELECT id FROM merchants WHERE email = ?", (email,)
        ).fetchone()

        if existing:
            conn.execute("""
                UPDATE merchants SET
                    name       = COALESCE(NULLIF(?, ''), name),
                    gateway    = COALESCE(NULLIF(?, ''), gateway),
                    platforms  = COALESCE(NULLIF(?, ''), platforms),
                    assistant  = COALESCE(NULLIF(?, ''), assistant),
                    updated_at = ?
                WHERE email = ?
            """, (name, gateways_str, platforms_str, assistant, now, email))
        else:
            conn.execute("""
                INSERT INTO merchants (email, name, gateway, platforms, assistant, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (email, name, gateways_str, platforms_str, assistant, now, now))
        conn.commit()

    return get_merchant(email)


def get_merchant(email: str) -> dict | None:
    """Return a merchant record by email, or None if not found."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM merchants WHERE email = ?", (email,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["gateways"]  = d["gateway"].split(",")   if d["gateway"]   else []
    d["platforms"] = d["platforms"].split(",") if d["platforms"] else []
    return d


def get_all_merchants() -> list[dict]:
    """Return all merchant records."""
    init_db()
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM merchants ORDER BY created_at DESC").fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["gateways"]  = d["gateway"].split(",")   if d["gateway"]   else []
        d["platforms"] = d["platforms"].split(",") if d["platforms"] else []
        result.append(d)
    return result
