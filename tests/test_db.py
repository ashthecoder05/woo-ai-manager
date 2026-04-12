"""
Tests for services/db.py — runs against SQLite (no DATABASE_URL needed).
Run with:  pytest tests/test_db.py -v
"""
import os
import pytest

# Force SQLite for tests regardless of env
os.environ.pop("DATABASE_URL", None)

from services.db import (
    init_db, upsert_merchant, get_merchant, get_all_merchants,
    create_order, get_order, update_order_status, get_recent_orders,
    get_merchant_analytics, insert_payment_event, get_payment_stats,
    record_chat, get_chat_stats, mark_merchant_verified,
    check_and_increment_chat,
)


@pytest.fixture(autouse=True)
def clean_db(tmp_path, monkeypatch):
    """Each test gets a fresh isolated SQLite DB."""
    db_file = tmp_path / "test.db"
    import services.db as db_module
    monkeypatch.setattr(db_module, "_DB_PATH", db_file)
    monkeypatch.setattr(db_module, "_USE_POSTGRES", False)
    init_db()
    yield


# ── Merchant tests ─────────────────────────────────────────────────────────────

def test_upsert_and_get_merchant():
    m = upsert_merchant("test@store.com", name="Test Store",
                        gateways=["blockonomics"], platforms=["plugin"])
    assert m["email"] == "test@store.com"
    assert m["name"] == "Test Store"
    assert "blockonomics" in m["gateways"]

    fetched = get_merchant("test@store.com")
    assert fetched is not None
    assert fetched["email"] == "test@store.com"


def test_get_merchant_not_found():
    assert get_merchant("nobody@nowhere.com") is None


def test_upsert_updates_existing():
    upsert_merchant("m@store.com", name="Old Name", gateways=["blockonomics"])
    upsert_merchant("m@store.com", name="New Name", gateways=["stripe"])
    m = get_merchant("m@store.com")
    assert m["name"] == "New Name"
    assert "stripe" in m["gateways"]


def test_mark_merchant_verified():
    upsert_merchant("v@store.com")
    mark_merchant_verified("v@store.com")
    m = get_merchant("v@store.com")
    assert m["is_verified"] == 1


def test_chat_limit_enforced():
    upsert_merchant("limit@store.com")
    for i in range(3):
        allowed, count = check_and_increment_chat("limit@store.com", daily_limit=3)
        assert allowed is True
        assert count == i + 1
    # 4th message should be blocked
    allowed, count = check_and_increment_chat("limit@store.com", daily_limit=3)
    assert allowed is False


# ── Order tests ────────────────────────────────────────────────────────────────

def test_create_and_get_order():
    o = create_order(
        order_id="ord-001",
        merchant="m@store.com",
        product_name="Bitcoin Mug",
        sale_price_usd=29.99,
        btc_amount=0.00045,
        btc_price_at_sale=66000,
        product_cost=8.00,
    )
    assert o is not None
    assert o["order_id"] == "ord-001"
    assert o["status"] == "pending"
    assert o["sale_price_usd"] == 29.99

    fetched = get_order("ord-001")
    assert fetched["product_name"] == "Bitcoin Mug"


def test_duplicate_order_returns_none():
    create_order("ord-dup", sale_price_usd=10, btc_amount=0.0001, btc_price_at_sale=50000)
    result = create_order("ord-dup", sale_price_usd=10, btc_amount=0.0001, btc_price_at_sale=50000)
    assert result is None


def test_update_order_status():
    create_order("ord-002", sale_price_usd=50, btc_amount=0.0007, btc_price_at_sale=70000)
    update_order_status("ord-002", "confirmed")
    o = get_order("ord-002")
    assert o["status"] == "confirmed"
    assert o["confirmed_at"] is not None


def test_get_recent_orders_filtered_by_merchant():
    upsert_merchant("alice@store.com")
    upsert_merchant("bob@store.com")
    create_order("a-001", merchant="alice@store.com", sale_price_usd=10,
                 btc_amount=0.0001, btc_price_at_sale=50000)
    create_order("b-001", merchant="bob@store.com", sale_price_usd=20,
                 btc_amount=0.0002, btc_price_at_sale=50000)

    alice_orders = get_recent_orders(merchant="alice@store.com")
    assert len(alice_orders) == 1
    assert alice_orders[0]["order_id"] == "a-001"


# ── Analytics tests ────────────────────────────────────────────────────────────

def test_analytics_empty():
    a = get_merchant_analytics(merchant="nobody@store.com")
    assert a["total_orders"] == 0
    assert a["revenue_usd"] == 0.0
    assert a["gross_profit_usd"] == 0.0


def test_analytics_confirmed_only():
    upsert_merchant("shop@store.com")
    create_order("x-001", merchant="shop@store.com", product_name="Hat",
                 sale_price_usd=50, product_cost=10, btc_amount=0.0007,
                 btc_price_at_sale=70000)
    create_order("x-002", merchant="shop@store.com", product_name="Hat",
                 sale_price_usd=50, product_cost=10, btc_amount=0.0007,
                 btc_price_at_sale=70000)
    # Only confirm one
    update_order_status("x-001", "confirmed")

    a = get_merchant_analytics(merchant="shop@store.com")
    assert a["confirmed_orders"] == 1
    assert a["pending_orders"] == 1
    assert a["revenue_usd"] == 50.0
    assert a["gross_profit_usd"] == 40.0  # 50 - 10 cost
    assert a["top_products"][0]["product"] == "Hat"


# ── Payment event tests ────────────────────────────────────────────────────────

def test_insert_payment_event():
    ok = insert_payment_event("addr1", "txid1", 100000, 0.001, 2, "confirmed")
    assert ok is True

def test_duplicate_payment_event_rejected():
    insert_payment_event("addr1", "txid1", 100000, 0.001, 2, "confirmed")
    ok = insert_payment_event("addr1", "txid1", 100000, 0.001, 2, "confirmed")
    assert ok is False

def test_payment_stats():
    insert_payment_event("a1", "tx1", 100000, 0.001, 2, "confirmed")
    insert_payment_event("a2", "tx2", 50000,  0.0005, 0, "unconfirmed")
    stats = get_payment_stats()
    assert stats["total_events"] == 2
    assert stats["confirmed_payments"] == 1
    assert stats["total_btc_received"] == 0.001


# ── Chat stats tests ───────────────────────────────────────────────────────────

def test_record_and_get_chat_stats():
    record_chat(merchant="m@store.com", gateway="blockonomics", tools_used=3)
    record_chat(merchant="m@store.com", gateway="blockonomics", tools_used=1)
    record_chat(merchant="other@store.com", gateway="stripe", tools_used=0)

    stats = get_chat_stats()
    assert stats["total_conversations"] == 3
    assert stats["total_tool_calls"] == 4
    assert stats["unique_merchants"] == 2
