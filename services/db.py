"""
Merchant database — supports PostgreSQL (production) and SQLite (local dev).

Set DATABASE_URL env var to a PostgreSQL connection string to use PostgreSQL.
Leave unset to use SQLite at data/merchants.db.

PostgreSQL:  postgresql://user:pass@host:5432/dbname
SQLite:      (automatic, no config needed)
"""

from __future__ import annotations
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

from config import DATABASE_URL

# ── Backend detection ──────────────────────────────────────────────────────────
_USE_POSTGRES = bool(DATABASE_URL)
_DB_PATH = Path(__file__).parent.parent / "data" / "merchants.db"

# ── PostgreSQL connection pool ─────────────────────────────────────────────────
_pg_pool = None

def _get_pg_pool():
    global _pg_pool
    if _pg_pool is None:
        import psycopg2.pool
        _pg_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=DATABASE_URL,
        )
    return _pg_pool


# ── SQL dialect helpers ────────────────────────────────────────────────────────

def _ph() -> str:
    """Return the correct parameter placeholder for the active backend."""
    return "%s" if _USE_POSTGRES else "?"


def _period_filter(period: str) -> str:
    """Return a SQL AND-clause that filters created_at by period."""
    if _USE_POSTGRES:
        if period == "today":
            return "AND created_at::date = CURRENT_DATE"
        if period == "7d":
            return "AND created_at >= NOW() - INTERVAL '7 days'"
        if period == "30d":
            return "AND created_at >= NOW() - INTERVAL '30 days'"
    else:
        if period == "today":
            return "AND date(created_at) = date('now')"
        if period == "7d":
            return "AND created_at >= datetime('now', '-7 days')"
        if period == "30d":
            return "AND created_at >= datetime('now', '-30 days')"
    return ""


def _daily_30d_filter() -> str:
    """Return a WHERE clause for the last 30 days."""
    if _USE_POSTGRES:
        return "AND created_at >= NOW() - INTERVAL '30 days'"
    return "AND created_at >= datetime('now', '-30 days')"


def _serial_pk() -> str:
    return "BIGSERIAL PRIMARY KEY" if _USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"


def _row_to_dict(row) -> dict:
    """Convert a db row to a plain dict regardless of backend."""
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    return dict(row)  # sqlite3.Row


# ── Connection context manager ─────────────────────────────────────────────────

@contextmanager
def _connect() -> Generator:
    """Yield a database connection, returning it to the pool when done."""
    if _USE_POSTGRES:
        import psycopg2.extras
        pool = _get_pg_pool()
        conn = pool.getconn()
        try:
            # Use RealDictCursor so rows behave like dicts
            conn.cursor_factory = psycopg2.extras.RealDictCursor
            yield conn
        finally:
            pool.putconn(conn)
    else:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(_DB_PATH))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


def _execute(conn, sql: str, params: tuple = ()) -> object:
    """Execute a statement, returning the cursor."""
    if _USE_POSTGRES:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur
    else:
        return conn.execute(sql, params)


def _fetchone(conn, sql: str, params: tuple = ()) -> dict | None:
    cur = _execute(conn, sql, params)
    row = cur.fetchone()
    return _row_to_dict(row)


def _fetchall(conn, sql: str, params: tuple = ()) -> list[dict]:
    cur = _execute(conn, sql, params)
    rows = cur.fetchall()
    return [_row_to_dict(r) for r in rows]


# ── Schema ─────────────────────────────────────────────────────────────────────

def init_db() -> None:
    """Create tables if they don't exist."""
    pk = _serial_pk()
    with _connect() as conn:
        _execute(conn, f"""
            CREATE TABLE IF NOT EXISTS merchants (
                id               {pk},
                email            TEXT    NOT NULL UNIQUE,
                name             TEXT,
                gateway          TEXT,
                platforms        TEXT,
                assistant        TEXT,
                is_verified      INTEGER NOT NULL DEFAULT 0,
                wc_webhook_secret TEXT,
                daily_chat_count INTEGER NOT NULL DEFAULT 0,
                chat_count_date  TEXT,
                created_at       TEXT    NOT NULL,
                updated_at       TEXT    NOT NULL
            )
        """)
        # Safe migrations — add new columns to existing deployments
        for col, definition in [
            ("is_verified",       "INTEGER NOT NULL DEFAULT 0"),
            ("wc_webhook_secret", "TEXT"),
            ("daily_chat_count",  "INTEGER NOT NULL DEFAULT 0"),
            ("chat_count_date",   "TEXT"),
            ("plugin_credits",    "INTEGER NOT NULL DEFAULT 50"),
        ]:
            try:
                _execute(conn, f"ALTER TABLE merchants ADD COLUMN {col} {definition}")
                conn.commit()
            except Exception:
                pass  # column already exists
        _execute(conn, f"""
            CREATE TABLE IF NOT EXISTS payment_events (
                id              {pk},
                addr            TEXT    NOT NULL,
                txid            TEXT    NOT NULL,
                value_satoshis  BIGINT  NOT NULL,
                value_btc       DOUBLE PRECISION NOT NULL,
                status          INTEGER NOT NULL,
                status_label    TEXT    NOT NULL,
                created_at      TEXT    NOT NULL,
                UNIQUE(txid, status)
            )
        """)
        _execute(conn, f"""
            CREATE TABLE IF NOT EXISTS chat_stats (
                id         {pk},
                merchant   TEXT,
                gateway    TEXT,
                tools_used INTEGER NOT NULL DEFAULT 0,
                created_at TEXT    NOT NULL
            )
        """)
        _execute(conn, f"""
            CREATE TABLE IF NOT EXISTS orders (
                id                {pk},
                order_id          TEXT    NOT NULL UNIQUE,
                merchant          TEXT,
                product_name      TEXT,
                product_cost      DOUBLE PRECISION NOT NULL DEFAULT 0,
                sale_price_usd    DOUBLE PRECISION NOT NULL DEFAULT 0,
                btc_amount        DOUBLE PRECISION NOT NULL DEFAULT 0,
                btc_price_at_sale DOUBLE PRECISION NOT NULL DEFAULT 0,
                fee_satoshis      BIGINT  NOT NULL DEFAULT 0,
                fee_usd           DOUBLE PRECISION NOT NULL DEFAULT 0,
                addr              TEXT,
                txid              TEXT,
                status            TEXT    NOT NULL DEFAULT 'pending',
                created_at        TEXT    NOT NULL,
                confirmed_at      TEXT
            )
        """)
        conn.commit()


# ── Merchants ──────────────────────────────────────────────────────────────────

def mark_merchant_verified(email: str) -> None:
    """Mark merchant email as verified (after Google OAuth)."""
    init_db()
    ph = _ph()
    now = datetime.now(tz=timezone.utc).isoformat()
    with _connect() as conn:
        _execute(conn,
            f"UPDATE merchants SET is_verified = 1, updated_at = {ph} WHERE email = {ph}",
            (now, email.lower()))
        conn.commit()


def check_and_increment_chat(email: str, daily_limit: int) -> tuple[bool, int]:
    """
    Atomically check daily chat limit and increment counter.
    Returns (allowed: bool, count_so_far: int).
    """
    init_db()
    ph = _ph()
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    with _connect() as conn:
        row = _fetchone(conn,
            f"SELECT daily_chat_count, chat_count_date FROM merchants WHERE email = {ph}",
            (email.lower(),))
        if not row:
            return False, 0
        count = row["daily_chat_count"] or 0
        last_date = row["chat_count_date"] or ""
        # Reset counter if it's a new day
        if last_date != today:
            count = 0
        if count >= daily_limit:
            return False, count
        _execute(conn,
            f"UPDATE merchants SET daily_chat_count = {ph}, chat_count_date = {ph} WHERE email = {ph}",
            (count + 1, today, email.lower()))
        conn.commit()
        return True, count + 1


def get_plugin_credits(email: str) -> int:
    """Return remaining plugin credits for a merchant."""
    init_db()
    ph = _ph()
    with _connect() as conn:
        row = _fetchone(conn,
            f"SELECT plugin_credits FROM merchants WHERE email = {ph}",
            (email.lower(),))
    return int(row["plugin_credits"]) if row else 0


def check_and_decrement_plugin_credits(email: str) -> tuple[bool, int]:
    """
    Atomically check and decrement plugin credits.
    Returns (allowed: bool, credits_remaining: int).
    """
    init_db()
    ph = _ph()
    with _connect() as conn:
        row = _fetchone(conn,
            f"SELECT plugin_credits FROM merchants WHERE email = {ph}",
            (email.lower(),))
        if not row:
            return False, 0
        credits = int(row["plugin_credits"] or 0)
        if credits <= 0:
            return False, 0
        now = datetime.now(tz=timezone.utc).isoformat()
        _execute(conn,
            f"UPDATE merchants SET plugin_credits = plugin_credits - 1, updated_at = {ph} WHERE email = {ph}",
            (now, email.lower()))
        conn.commit()
        return True, credits - 1


def get_wc_webhook_secret(email: str) -> str:
    """Get or create a WooCommerce webhook secret for this merchant."""
    import secrets as _secrets
    init_db()
    ph = _ph()
    with _connect() as conn:
        row = _fetchone(conn,
            f"SELECT wc_webhook_secret FROM merchants WHERE email = {ph}",
            (email.lower(),))
    if row and row.get("wc_webhook_secret"):
        return row["wc_webhook_secret"]
    # Generate and store a new secret
    secret = _secrets.token_hex(32)
    now = datetime.now(tz=timezone.utc).isoformat()
    with _connect() as conn:
        _execute(conn,
            f"UPDATE merchants SET wc_webhook_secret = {ph}, updated_at = {ph} WHERE email = {ph}",
            (secret, now, email.lower()))
        conn.commit()
    return secret


def upsert_merchant(
    email: str,
    name: str = "",
    gateways: list[str] | None = None,
    platforms: list[str] | None = None,
    assistant: str = "",
) -> dict:
    init_db()
    now = datetime.now(tz=timezone.utc).isoformat()
    gateways_str  = ",".join(gateways)  if gateways  else ""
    platforms_str = ",".join(platforms) if platforms else ""
    ph = _ph()

    with _connect() as conn:
        existing = _fetchone(conn, f"SELECT id FROM merchants WHERE email = {ph}", (email,))
        if existing:
            _execute(conn, f"""
                UPDATE merchants SET
                    name       = COALESCE(NULLIF({ph}, ''), name),
                    gateway    = COALESCE(NULLIF({ph}, ''), gateway),
                    platforms  = COALESCE(NULLIF({ph}, ''), platforms),
                    assistant  = COALESCE(NULLIF({ph}, ''), assistant),
                    updated_at = {ph}
                WHERE email = {ph}
            """, (name, gateways_str, platforms_str, assistant, now, email))
        else:
            _execute(conn, f"""
                INSERT INTO merchants (email, name, gateway, platforms, assistant, created_at, updated_at)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
            """, (email, name, gateways_str, platforms_str, assistant, now, now))
        conn.commit()

    return get_merchant(email)


def get_merchant(email: str) -> dict | None:
    init_db()
    ph = _ph()
    with _connect() as conn:
        row = _fetchone(conn, f"SELECT * FROM merchants WHERE email = {ph}", (email,))
    if not row:
        return None
    row["gateways"]  = row["gateway"].split(",")   if row.get("gateway")   else []
    row["platforms"] = row["platforms"].split(",") if row.get("platforms") else []
    return row


def get_all_merchants() -> list[dict]:
    init_db()
    with _connect() as conn:
        rows = _fetchall(conn, "SELECT * FROM merchants ORDER BY created_at DESC")
    result = []
    for row in rows:
        row["gateways"]  = row["gateway"].split(",")   if row.get("gateway")   else []
        row["platforms"] = row["platforms"].split(",") if row.get("platforms") else []
        result.append(row)
    return result


# ── Payment events ─────────────────────────────────────────────────────────────

def insert_payment_event(
    addr: str, txid: str, value_satoshis: int,
    value_btc: float, status: int, status_label: str,
) -> bool:
    init_db()
    now = datetime.now(tz=timezone.utc).isoformat()
    ph = _ph()
    try:
        with _connect() as conn:
            _execute(conn, f"""
                INSERT INTO payment_events (addr, txid, value_satoshis, value_btc, status, status_label, created_at)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
            """, (addr, txid, value_satoshis, value_btc, status, status_label, now))
            conn.commit()
        return True
    except Exception:
        return False  # duplicate (UNIQUE constraint)


def get_recent_payments(limit: int = 20) -> list[dict]:
    init_db()
    ph = _ph()
    with _connect() as conn:
        return _fetchall(conn,
            f"SELECT * FROM payment_events ORDER BY created_at DESC LIMIT {ph}", (limit,))


def get_payment_stats() -> dict:
    init_db()
    with _connect() as conn:
        total     = _fetchone(conn, "SELECT COUNT(*) AS n FROM payment_events")["n"]
        confirmed = _fetchone(conn, "SELECT COUNT(*) AS n FROM payment_events WHERE status >= 2")["n"]
        btc_row   = _fetchone(conn,
            "SELECT COALESCE(SUM(value_btc), 0) AS s FROM payment_events WHERE status >= 2")
        total_btc = btc_row["s"] if btc_row else 0
    return {
        "total_events": total,
        "confirmed_payments": confirmed,
        "total_btc_received": round(total_btc, 8),
    }


# ── Chat stats ─────────────────────────────────────────────────────────────────

def record_chat(merchant: str | None = None, gateway: str = "", tools_used: int = 0) -> None:
    init_db()
    now = datetime.now(tz=timezone.utc).isoformat()
    ph = _ph()
    with _connect() as conn:
        _execute(conn, f"""
            INSERT INTO chat_stats (merchant, gateway, tools_used, created_at)
            VALUES ({ph}, {ph}, {ph}, {ph})
        """, (merchant, gateway, tools_used, now))
        conn.commit()


def get_chat_stats() -> dict:
    init_db()
    with _connect() as conn:
        total       = _fetchone(conn, "SELECT COUNT(*) AS n FROM chat_stats")["n"]
        tools_row   = _fetchone(conn, "SELECT COALESCE(SUM(tools_used), 0) AS s FROM chat_stats")
        uniq_row    = _fetchone(conn,
            "SELECT COUNT(DISTINCT merchant) AS n FROM chat_stats WHERE merchant IS NOT NULL AND merchant != ''")
    return {
        "total_conversations": total,
        "total_tool_calls": tools_row["s"] if tools_row else 0,
        "unique_merchants": uniq_row["n"] if uniq_row else 0,
    }


# ── Orders & Revenue ───────────────────────────────────────────────────────────

def create_order(
    order_id: str,
    sale_price_usd: float,
    btc_amount: float,
    btc_price_at_sale: float,
    merchant: str = "",
    product_name: str = "",
    product_cost: float = 0,
    fee_satoshis: int = 0,
    fee_usd: float = 0,
    addr: str = "",
    txid: str = "",
    status: str = "pending",
) -> dict | None:
    init_db()
    now = datetime.now(tz=timezone.utc).isoformat()
    ph = _ph()
    try:
        with _connect() as conn:
            _execute(conn, f"""
                INSERT INTO orders (order_id, merchant, product_name, product_cost,
                    sale_price_usd, btc_amount, btc_price_at_sale,
                    fee_satoshis, fee_usd, addr, txid, status, created_at)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
            """, (order_id, merchant, product_name, product_cost,
                  sale_price_usd, btc_amount, btc_price_at_sale,
                  fee_satoshis, fee_usd, addr, txid, status, now))
            conn.commit()
        return get_order(order_id)
    except Exception:
        return None  # duplicate order_id


def update_order_status(order_id: str, status: str) -> bool:
    init_db()
    now = datetime.now(tz=timezone.utc).isoformat()
    ph = _ph()
    with _connect() as conn:
        if status == "confirmed":
            _execute(conn,
                f"UPDATE orders SET status = {ph}, confirmed_at = {ph} WHERE order_id = {ph}",
                (status, now, order_id))
        else:
            _execute(conn,
                f"UPDATE orders SET status = {ph} WHERE order_id = {ph}",
                (status, order_id))
        conn.commit()
        if _USE_POSTGRES:
            return True  # psycopg2 rowcount not always reliable after commit
        return conn.total_changes > 0


def get_order(order_id: str) -> dict | None:
    init_db()
    ph = _ph()
    with _connect() as conn:
        return _fetchone(conn, f"SELECT * FROM orders WHERE order_id = {ph}", (order_id,))


def get_recent_orders(merchant: str = "", limit: int = 50) -> list[dict]:
    init_db()
    ph = _ph()
    with _connect() as conn:
        if merchant:
            return _fetchall(conn,
                f"SELECT * FROM orders WHERE merchant = {ph} ORDER BY created_at DESC LIMIT {ph}",
                (merchant, limit))
        return _fetchall(conn,
            f"SELECT * FROM orders ORDER BY created_at DESC LIMIT {ph}", (limit,))


def get_merchant_analytics(merchant: str = "", period: str = "all") -> dict:
    """
    Full merchant analytics: revenue, profit, orders, averages, trends.
    period: 'today', '7d', '30d', 'all'
    """
    init_db()
    ph = _ph()
    date_filter = _period_filter(period)
    merchant_filter = f"AND merchant = {ph}" if merchant else ""
    params = (merchant,) if merchant else ()

    with _connect() as conn:
        def scalar(sql, extra_params=()):
            row = _fetchone(conn, sql, params + extra_params)
            return list(row.values())[0] if row else 0

        total_orders     = scalar(f"SELECT COUNT(*) FROM orders WHERE 1=1 {merchant_filter} {date_filter}")
        confirmed_orders = scalar(f"SELECT COUNT(*) FROM orders WHERE status='confirmed' {merchant_filter} {date_filter}")
        pending_orders   = scalar(f"SELECT COUNT(*) FROM orders WHERE status='pending' {merchant_filter} {date_filter}")
        revenue_usd      = scalar(f"SELECT COALESCE(SUM(sale_price_usd),0) FROM orders WHERE status='confirmed' {merchant_filter} {date_filter}")
        total_btc        = scalar(f"SELECT COALESCE(SUM(btc_amount),0)    FROM orders WHERE status='confirmed' {merchant_filter} {date_filter}")
        total_cost       = scalar(f"SELECT COALESCE(SUM(product_cost),0)  FROM orders WHERE status='confirmed' {merchant_filter} {date_filter}")
        total_fees_usd   = scalar(f"SELECT COALESCE(SUM(fee_usd),0)       FROM orders WHERE status='confirmed' {merchant_filter} {date_filter}")
        avg_order        = scalar(f"SELECT COALESCE(AVG(sale_price_usd),0) FROM orders WHERE status='confirmed' {merchant_filter} {date_filter}")
        largest_order    = scalar(f"SELECT COALESCE(MAX(sale_price_usd),0) FROM orders WHERE status='confirmed' {merchant_filter} {date_filter}")

        # Daily revenue for last 30 days
        daily_sql = f"""
            SELECT date(created_at) AS day,
                   COUNT(*) AS order_count,
                   COALESCE(SUM(sale_price_usd),0) AS revenue,
                   COALESCE(SUM(btc_amount),0) AS btc_total
            FROM orders
            WHERE status='confirmed' {merchant_filter} {_daily_30d_filter()}
            GROUP BY date(created_at)
            ORDER BY day
        """ if not _USE_POSTGRES else f"""
            SELECT created_at::date AS day,
                   COUNT(*) AS order_count,
                   COALESCE(SUM(sale_price_usd),0) AS revenue,
                   COALESCE(SUM(btc_amount),0) AS btc_total
            FROM orders
            WHERE status='confirmed' {merchant_filter} {_daily_30d_filter()}
            GROUP BY created_at::date
            ORDER BY day
        """
        daily_rows = _fetchall(conn, daily_sql, params)
        daily_revenue = [
            {
                "date": str(r["day"]),
                "orders": r["order_count"],
                "revenue_usd": round(float(r["revenue"]), 2),
                "btc": round(float(r["btc_total"]), 8),
            }
            for r in daily_rows
        ]

        # Top products
        top_sql = f"""
            SELECT product_name,
                   COUNT(*) AS sold,
                   COALESCE(SUM(sale_price_usd),0) AS revenue,
                   COALESCE(SUM(sale_price_usd - product_cost),0) AS profit
            FROM orders
            WHERE status='confirmed'
              AND product_name IS NOT NULL AND product_name != ''
              {merchant_filter}
            GROUP BY product_name
            ORDER BY revenue DESC
            LIMIT 10
        """
        top_rows = _fetchall(conn, top_sql, params)
        top_products = [
            {
                "product": r["product_name"],
                "units_sold": r["sold"],
                "revenue_usd": round(float(r["revenue"]), 2),
                "profit_usd": round(float(r["profit"]), 2),
            }
            for r in top_rows
        ]

    profit = float(revenue_usd) - float(total_cost) - float(total_fees_usd)
    margin = (profit / float(revenue_usd) * 100) if float(revenue_usd) > 0 else 0

    return {
        "period": period,
        "total_orders": total_orders,
        "confirmed_orders": confirmed_orders,
        "pending_orders": pending_orders,
        "revenue_usd": round(float(revenue_usd), 2),
        "total_btc_received": round(float(total_btc), 8),
        "total_cost_usd": round(float(total_cost), 2),
        "total_fees_usd": round(float(total_fees_usd), 2),
        "gross_profit_usd": round(profit, 2),
        "profit_margin_pct": round(margin, 1),
        "avg_order_usd": round(float(avg_order), 2),
        "largest_order_usd": round(float(largest_order), 2),
        "daily_revenue": daily_revenue,
        "top_products": top_products,
    }
