from __future__ import annotations
"""
Blockonomics webhook receiver.

Blockonomics fires a GET request to this endpoint whenever a payment event occurs:
  GET /webhook/blockonomics?secret=<secret>&addr=<addr>&value=<satoshis>&txid=<txid>&status=<status>

Status codes:
  0 = unconfirmed (in mempool)
  1 = partially confirmed (< 2 blocks)
  2 = confirmed (2+ blocks) — safe to fulfill
"""

import base64
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request

from services.db import (
    insert_payment_event, get_recent_payments,
    create_order, update_order_status, get_wc_webhook_secret,
)

logger = logging.getLogger("webhook")

router = APIRouter(prefix="/webhook", tags=["webhook"])

# In production load this from your .env
WEBHOOK_SECRET = os.getenv("BLOCKONOMICS_WEBHOOK_SECRET", "CHANGE_ME_IN_ENV")

STATUS_LABELS = {0: "unconfirmed", 1: "partially_confirmed", 2: "confirmed"}


@router.get("/blockonomics")
def receive_payment_event(
    secret: str = Query(..., description="Shared secret to authenticate the request"),
    addr: str = Query(..., description="Bitcoin address that received the payment"),
    value: int = Query(..., description="Amount in satoshis"),
    txid: str = Query(..., description="Transaction ID"),
    status: int = Query(..., description="0=unconfirmed, 1=partial, 2=confirmed"),
):
    # Authenticate — timing-safe comparison to prevent secret brute-forcing
    if not hmac.compare_digest(secret, WEBHOOK_SECRET):
        logger.warning("Webhook received with invalid secret")
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    status_label = STATUS_LABELS.get(status, "unknown")
    btc = value / 1e8

    # Persist to DB — returns False if duplicate (txid+status)
    is_new = insert_payment_event(
        addr=addr, txid=txid, value_satoshis=value,
        value_btc=round(btc, 8), status=status, status_label=status_label,
    )

    if not is_new:
        logger.info("Duplicate webhook ignored | txid=%.16s... status=%d", txid, status)
        return {"ok": True, "status": status_label, "duplicate": True}

    logger.info(
        "Payment event | addr=%s txid=%.16s... value=%.8f BTC status=%s",
        addr,
        txid,
        btc,
        status_label,
    )

    if status >= 2:
        _on_confirmed({"addr": addr, "value_btc": round(btc, 8), "txid": txid})

    return {"ok": True, "status": status_label}


@router.get("/blockonomics/events")
def list_events(
    secret: str = Query(..., description="Webhook secret for authentication"),
    limit: int = Query(50, ge=1, le=100),
):
    """Return the most recent webhook events (newest first). Requires auth."""
    if not hmac.compare_digest(secret, WEBHOOK_SECRET):
        raise HTTPException(status_code=403, detail="Invalid secret")
    events = get_recent_payments(limit)
    return {"events": events, "total": len(events)}


def _on_confirmed(event: dict) -> None:
    logger.info(
        "CONFIRMED PAYMENT | addr=%s value=%.8f BTC txid=%.16s...",
        event["addr"], event["value_btc"], event["txid"],
    )


# ── WooCommerce webhook ────────────────────────────────────────────────────────
#
# Setup in WooCommerce:
#   WooCommerce → Settings → Advanced → Webhooks → Add webhook
#   Topic:        Order updated  (covers created, paid, completed, refunded)
#   Delivery URL: https://yourapp.com/webhook/woocommerce?merchant=email@store.com
#   Secret:       (get from GET /api/woocommerce/setup)
#
# WooCommerce signs the body with HMAC-SHA256 and base64-encodes it.
# Header: X-WC-Webhook-Signature

WC_STATUS_MAP = {
    "pending":    "pending",
    "processing": "confirmed",   # payment received, fulfilling
    "completed":  "confirmed",
    "on-hold":    "pending",
    "cancelled":  "cancelled",
    "refunded":   "cancelled",
    "failed":     "cancelled",
}


@router.post("/woocommerce")
async def receive_woocommerce_order(
    request: Request,
    merchant: str = Query(..., description="Merchant email address"),
):
    """Receive WooCommerce order webhook and store the order in Blocko Agent DB."""
    raw_body = await request.body()

    # ── Verify HMAC signature ──────────────────────────────────────────────────
    sig_header = request.headers.get("X-WC-Webhook-Signature", "")
    if not sig_header:
        logger.warning("WooCommerce webhook missing signature | merchant=%s", merchant)
        raise HTTPException(status_code=401, detail="Missing signature")

    secret = get_wc_webhook_secret(merchant.strip().lower())
    expected_sig = base64.b64encode(
        hmac.new(secret.encode(), raw_body, hashlib.sha256).digest()
    ).decode()

    if not hmac.compare_digest(sig_header, expected_sig):
        logger.warning("WooCommerce webhook invalid signature | merchant=%s", merchant)
        raise HTTPException(status_code=403, detail="Invalid signature")

    # ── Parse order ────────────────────────────────────────────────────────────
    try:
        order_data = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    wc_order_id = str(order_data.get("id", ""))
    wc_status   = order_data.get("status", "pending")
    our_status  = WC_STATUS_MAP.get(wc_status, "pending")

    # Extract totals
    total_usd    = float(order_data.get("total", 0))
    currency     = order_data.get("currency", "USD")
    payment_method = order_data.get("payment_method_title", "")

    # Extract first line item as product name
    line_items   = order_data.get("line_items", [])
    product_name = line_items[0].get("name", "") if line_items else ""
    if len(line_items) > 1:
        product_name += f" (+{len(line_items)-1} more)"

    # Cost of goods: sum of (cost_per_item * qty) if meta exists, else 0
    product_cost = 0.0
    for item in line_items:
        for meta in item.get("meta_data", []):
            if meta.get("key") in ("_cost", "cost", "_product_cost"):
                try:
                    product_cost += float(meta["value"]) * int(item.get("quantity", 1))
                except (ValueError, TypeError):
                    pass

    # BTC amount from order meta (if merchant uses a BTC gateway plugin)
    btc_amount = 0.0
    btc_price  = 0.0
    for meta in order_data.get("meta_data", []):
        key = meta.get("key", "")
        if key in ("_btc_amount", "btc_amount", "_blockonomics_btc_amount"):
            try:
                btc_amount = float(meta["value"])
            except (ValueError, TypeError):
                pass
        if key in ("_btc_price", "btc_price_at_sale", "_blockonomics_btc_price"):
            try:
                btc_price = float(meta["value"])
            except (ValueError, TypeError):
                pass

    # Fall back to live BTC price if not in order meta
    if btc_amount == 0 and total_usd > 0:
        try:
            from services.blockonomics import get_price
            btc_price = get_price()["usd"]
            btc_amount = round(total_usd / btc_price, 8)
        except Exception:
            pass

    order_id = f"wc-{wc_order_id}"

    # ── Create or update order in DB ───────────────────────────────────────────
    from services.db import get_order
    existing = get_order(order_id)
    if existing:
        update_order_status(order_id, our_status)
        logger.info("WooCommerce order updated | merchant=%s order=%s status=%s",
                    merchant, order_id, our_status)
    else:
        create_order(
            order_id=order_id,
            merchant=merchant.strip().lower(),
            product_name=product_name,
            sale_price_usd=total_usd,
            product_cost=product_cost,
            btc_amount=btc_amount,
            btc_price_at_sale=btc_price,
            status=our_status,
        )
        logger.info("WooCommerce order created | merchant=%s order=%s product=%s total=$%.2f status=%s",
                    merchant, order_id, product_name, total_usd, our_status)

    return {"ok": True, "order_id": order_id, "status": our_status}
