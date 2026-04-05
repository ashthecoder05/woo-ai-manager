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

import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger("webhook")

router = APIRouter(prefix="/webhook", tags=["webhook"])

# In production load this from your .env
WEBHOOK_SECRET = os.getenv("BLOCKONOMICS_WEBHOOK_SECRET", "CHANGE_ME_IN_ENV")

# In-memory event log (replace with a DB in production)
_event_log: list[dict] = []

# Idempotency: track (txid, status) pairs we have already processed.
# A set of strings "txid:status" is enough — same tx can legitimately
# arrive at status=0, then status=1, then status=2, and each is distinct.
_seen: set[str] = set()

STATUS_LABELS = {0: "unconfirmed", 1: "partially_confirmed", 2: "confirmed"}


@router.get("/blockonomics")
def receive_payment_event(
    secret: str = Query(..., description="Shared secret to authenticate the request"),
    addr: str = Query(..., description="Bitcoin address that received the payment"),
    value: int = Query(..., description="Amount in satoshis"),
    txid: str = Query(..., description="Transaction ID"),
    status: int = Query(..., description="0=unconfirmed, 1=partial, 2=confirmed"),
):
    # Authenticate
    if secret != WEBHOOK_SECRET:
        logger.warning("Webhook received with invalid secret")
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    # Idempotency — deduplicate retried callbacks for the same (txid, status)
    idempotency_key = f"{txid}:{status}"
    if idempotency_key in _seen:
        logger.info("Duplicate webhook ignored | txid=%.16s... status=%d", txid, status)
        return {"ok": True, "status": STATUS_LABELS.get(status, "unknown"), "duplicate": True}
    _seen.add(idempotency_key)

    status_label = STATUS_LABELS.get(status, "unknown")
    btc = value / 1e8

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "addr": addr,
        "value_satoshis": value,
        "value_btc": round(btc, 8),
        "txid": txid,
        "status": status,
        "status_label": status_label,
    }

    _event_log.append(event)
    logger.info(
        "Payment event | addr=%s txid=%.16s... value=%.8f BTC status=%s",
        addr,
        txid,
        btc,
        status_label,
    )

    if status >= 2:
        _on_confirmed(event)

    return {"ok": True, "status": status_label}


@router.get("/blockonomics/events")
def list_events(limit: int = Query(50, ge=1, le=500)):
    """Return the most recent webhook events (newest first). For debugging."""
    return {"events": _event_log[-limit:][::-1], "total": len(_event_log)}


def _on_confirmed(event: dict) -> None:
    """
    Called when a payment reaches 2+ confirmations.
    Replace this stub with your order fulfillment logic.
    """
    logger.info(
        "CONFIRMED PAYMENT | addr=%s value=%.8f BTC txid=%.16s...",
        event["addr"],
        event["value_btc"],
        event["txid"],
    )
    # TODO: look up the order by addr and mark it as paid
    # e.g.: order_service.fulfill(event["addr"], event["value_satoshis"])
