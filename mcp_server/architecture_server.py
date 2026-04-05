"""
Architecture MCP Server — Bitcoin Payment Gateway Technical Guide

Covers end-to-end technical architecture for onboarding Bitcoin payment gateways:
  - Web page integration (embed scripts, iframes, payment pages)
  - Plugin architecture (WooCommerce, PrestaShop, WHMCS hooks & filters)
  - Database schemas (orders, payments, webhook logs)
  - Frontend patterns (React, Vue, Vanilla JS — QR code, payment status, polling)
  - Backend patterns (FastAPI, Flask, Django, Laravel, Express — webhook handlers)
  - Security patterns (HMAC verification, CSRF, rate limiting, replay attack prevention)
  - Testing strategies (sandbox, unit, integration, end-to-end)
  - Deployment architecture (HTTPS, reverse proxy, SSL, environment config)

Python 3.8+ compatible — wired as tools in agent/tools.py
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# DATABASE SCHEMAS
# ---------------------------------------------------------------------------

DB_SCHEMAS: dict[str, dict] = {

    "mysql_woocommerce": {
        "label": "MySQL — WooCommerce Bitcoin Orders",
        "description": "Minimal schema additions on top of WooCommerce for Bitcoin payment tracking",
        "sql": """\
-- Bitcoin payment metadata stored in WooCommerce order meta table (no extra tables needed)
-- These meta_keys are set automatically by Blockonomics / Coinbase / BitPay plugins:

-- wp_postmeta keys added per order:
--   _payment_method          = 'blockonomics' | 'coinbase_commerce' | 'bitpay' etc.
--   _btc_address             = the Bitcoin address for this order
--   _btc_amount              = BTC amount expected
--   _btc_txid                = txid once payment is detected
--   _btc_status              = 0 (unconfirmed) | 1 (partial) | 2 (confirmed)

-- Custom table for webhook audit log (recommended for debugging):
CREATE TABLE IF NOT EXISTS wp_bitcoin_webhook_log (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    order_id      BIGINT UNSIGNED NOT NULL,
    gateway       VARCHAR(50)  NOT NULL,
    txid          VARCHAR(64)  DEFAULT NULL,
    btc_address   VARCHAR(62)  DEFAULT NULL,
    value_sats    BIGINT       DEFAULT 0,
    status        TINYINT      DEFAULT 0,
    raw_payload   TEXT         NOT NULL,
    received_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed     TINYINT(1)   DEFAULT 0,
    PRIMARY KEY (id),
    INDEX idx_order   (order_id),
    INDEX idx_address (btc_address),
    INDEX idx_txid    (txid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
""",
        "orm_models": """\
# Django ORM equivalent (if building custom):
from django.db import models

class BitcoinWebhookLog(models.Model):
    order_id    = models.PositiveBigIntegerField(db_index=True)
    gateway     = models.CharField(max_length=50)
    txid        = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    btc_address = models.CharField(max_length=62, null=True, blank=True, db_index=True)
    value_sats  = models.BigIntegerField(default=0)
    status      = models.SmallIntegerField(default=0)
    raw_payload = models.TextField()
    received_at = models.DateTimeField(auto_now_add=True)
    processed   = models.BooleanField(default=False)

    class Meta:
        db_table = 'bitcoin_webhook_log'
""",
        "tips": [
            "Never store raw private keys or xpub in the database — use environment variables",
            "Index btc_address and txid columns for fast webhook lookups",
            "Store raw_payload for every webhook so you can replay/debug failed deliveries",
            "Use a processed flag + idempotency check to prevent double-fulfillment on duplicate webhooks",
        ],
    },

    "postgresql_custom": {
        "label": "PostgreSQL — Custom Bitcoin Payment System",
        "description": "Full schema for a custom Bitcoin payment integration (not plugin-based)",
        "sql": """\
-- Orders table
CREATE TABLE IF NOT EXISTS orders (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_ref    VARCHAR(128) UNIQUE NOT NULL,   -- your internal order/cart ID
    merchant_email  VARCHAR(255) NOT NULL,
    amount_fiat     NUMERIC(12,2) NOT NULL,
    currency        CHAR(3) NOT NULL DEFAULT 'USD',
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- status: pending | awaiting_payment | underpaid | confirmed | fulfilled | expired | failed
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Bitcoin payment requests (one per order)
CREATE TABLE IF NOT EXISTS btc_payment_requests (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id            UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    gateway             VARCHAR(50) NOT NULL,   -- blockonomics | coinbase | bitpay | etc.
    btc_address         VARCHAR(62) UNIQUE NOT NULL,
    expected_btc        NUMERIC(16,8) NOT NULL,
    expected_sats       BIGINT NOT NULL,
    btc_price_at_create NUMERIC(12,2) NOT NULL,  -- BTC/USD rate when address was generated
    expires_at          TIMESTAMPTZ,              -- NULL = no expiry
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Incoming webhook events (raw + parsed)
CREATE TABLE IF NOT EXISTS webhook_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gateway         VARCHAR(50) NOT NULL,
    btc_address     VARCHAR(62),
    txid            VARCHAR(64),
    received_sats   BIGINT,
    status_code     SMALLINT,              -- gateway-specific (0/1/2 for Blockonomics etc.)
    status_label    VARCHAR(30),           -- 'confirmed' | 'pending' | 'paid' etc.
    raw_payload     JSONB NOT NULL,
    signature_ok    BOOLEAN DEFAULT FALSE, -- did HMAC verification pass?
    processed       BOOLEAN DEFAULT FALSE,
    idempotency_key VARCHAR(128) UNIQUE,   -- prevent double-processing
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_webhook_address ON webhook_events(btc_address);
CREATE INDEX idx_webhook_txid    ON webhook_events(txid);
CREATE INDEX idx_webhook_processed ON webhook_events(processed) WHERE processed = FALSE;

-- Fulfillment log
CREATE TABLE IF NOT EXISTS fulfillments (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id    UUID NOT NULL REFERENCES orders(id),
    triggered_by UUID REFERENCES webhook_events(id),
    fulfilled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes       TEXT
);
""",
        "sqlalchemy_models": """\
# SQLAlchemy 2.x models
import uuid
from datetime import datetime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Numeric, BigInteger, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMPTZ

class Base(DeclarativeBase):
    pass

class Order(Base):
    __tablename__ = "orders"
    id           : Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    external_ref : Mapped[str]       = mapped_column(unique=True)
    amount_fiat  : Mapped[float]     = mapped_column(Numeric(12, 2))
    currency     : Mapped[str]       = mapped_column(default="USD")
    status       : Mapped[str]       = mapped_column(default="pending")
    created_at   : Mapped[datetime]  = mapped_column(TIMESTAMPTZ, default=datetime.utcnow)

class BtcPaymentRequest(Base):
    __tablename__ = "btc_payment_requests"
    id           : Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    order_id     : Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"))
    gateway      : Mapped[str]
    btc_address  : Mapped[str]       = mapped_column(unique=True)
    expected_sats: Mapped[int]       = mapped_column(BigInteger)
    order        : Mapped["Order"]   = relationship()

class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    id             : Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    gateway        : Mapped[str]
    btc_address    : Mapped[str | None]
    txid           : Mapped[str | None]
    received_sats  : Mapped[int | None] = mapped_column(BigInteger)
    raw_payload    : Mapped[dict]        = mapped_column(JSONB)
    signature_ok   : Mapped[bool]        = mapped_column(Boolean, default=False)
    processed      : Mapped[bool]        = mapped_column(Boolean, default=False)
    idempotency_key: Mapped[str | None]  = mapped_column(unique=True)
    received_at    : Mapped[datetime]    = mapped_column(TIMESTAMPTZ, default=datetime.utcnow)
""",
        "tips": [
            "Use idempotency_key on webhook_events to deduplicate retries safely",
            "Store raw_payload as JSONB so you can query payment fields directly",
            "Use a background worker (Celery / ARQ / RQ) to process webhooks asynchronously",
            "Never fulfill inside the webhook handler synchronously — enqueue a job",
            "Add a partial payment flow: if received_sats < expected_sats → mark as 'underpaid' not 'fulfilled'",
        ],
    },

    "sqlite_minimal": {
        "label": "SQLite — Minimal Dev/Test Schema",
        "description": "Lightweight schema for local development and testing",
        "sql": """\
CREATE TABLE IF NOT EXISTS orders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ref          TEXT UNIQUE NOT NULL,
    amount_usd   REAL NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS btc_payments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id     INTEGER NOT NULL REFERENCES orders(id),
    gateway      TEXT NOT NULL,
    btc_address  TEXT UNIQUE NOT NULL,
    expected_sats INTEGER NOT NULL,
    txid         TEXT,
    status_code  INTEGER DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS webhook_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    btc_address  TEXT,
    txid         TEXT,
    value_sats   INTEGER,
    status_code  INTEGER,
    payload      TEXT NOT NULL,
    received_at  TEXT NOT NULL DEFAULT (datetime('now')),
    processed    INTEGER DEFAULT 0
);
""",
        "tips": [
            "SQLite is fine for development — switch to PostgreSQL for production",
            "SQLite has no JSONB; store raw webhook payload as TEXT",
            "Enable WAL mode for concurrent reads: PRAGMA journal_mode=WAL",
        ],
    },
}

# ---------------------------------------------------------------------------
# FRONTEND PATTERNS
# ---------------------------------------------------------------------------

FRONTEND_PATTERNS: dict[str, dict] = {

    "vanilla_js_payment_page": {
        "label": "Vanilla JS — Bitcoin Payment Page",
        "description": "Pure HTML/JS payment page with QR code, countdown timer, and auto-polling",
        "frameworks": ["Vanilla JS", "Any HTML page"],
        "snippet": """\
<!-- Include QR code library -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>

<div id="btc-payment-box" style="max-width:420px;margin:auto;font-family:monospace">
  <h2>Pay with Bitcoin</h2>
  <p>Send exactly: <strong id="btc-amount"></strong> BTC</p>
  <div id="qr-code" style="margin:16px 0"></div>
  <p style="word-break:break-all">Address: <code id="btc-address"></code></p>
  <button onclick="copyAddress()">Copy Address</button>
  <p>Expires in: <span id="countdown">15:00</span></p>
  <p id="payment-status">Waiting for payment…</p>
</div>

<script>
// Injected by your server:
const BTC_ADDRESS = "{{ btc_address }}";
const BTC_AMOUNT  = "{{ btc_amount }}";
const ORDER_ID    = "{{ order_id }}";
const EXPIRES_IN  = 15 * 60; // seconds

document.getElementById("btc-amount").textContent  = BTC_AMOUNT;
document.getElementById("btc-address").textContent  = BTC_ADDRESS;

// QR code
new QRCode(document.getElementById("qr-code"), {
  text: `bitcoin:${BTC_ADDRESS}?amount=${BTC_AMOUNT}`,
  width: 200, height: 200
});

// Countdown timer
let secondsLeft = EXPIRES_IN;
const countdownEl = document.getElementById("countdown");
const timer = setInterval(() => {
  secondsLeft--;
  const m = String(Math.floor(secondsLeft / 60)).padStart(2, "0");
  const s = String(secondsLeft % 60).padStart(2, "0");
  countdownEl.textContent = `${m}:${s}`;
  if (secondsLeft <= 0) { clearInterval(timer); countdownEl.textContent = "Expired"; }
}, 1000);

// Poll for payment status every 15 seconds
async function pollPaymentStatus() {
  try {
    const res = await fetch(`/api/order-status?order_id=${ORDER_ID}`);
    const data = await res.json();
    const statusEl = document.getElementById("payment-status");
    if (data.status === "confirmed") {
      statusEl.textContent = "✅ Payment confirmed! Redirecting…";
      clearInterval(pollTimer);
      setTimeout(() => window.location.href = "/order/success?id=" + ORDER_ID, 2000);
    } else if (data.status === "underpaid") {
      statusEl.textContent = "⚠️ Underpayment detected. Please send the remaining amount.";
    } else if (data.status === "expired") {
      statusEl.textContent = "❌ Payment window expired. Please restart checkout.";
      clearInterval(pollTimer);
    }
  } catch (e) { console.warn("Poll failed", e); }
}

const pollTimer = setInterval(pollPaymentStatus, 15000);
pollPaymentStatus(); // check immediately on load

function copyAddress() {
  navigator.clipboard.writeText(BTC_ADDRESS)
    .then(() => alert("Address copied!"))
    .catch(() => { document.getElementById("btc-address").select(); document.execCommand("copy"); });
}
</script>
""",
        "tips": [
            "Use `bitcoin:ADDRESS?amount=BTC_AMOUNT` URI format in the QR code — wallets auto-fill the amount",
            "15-minute expiry is standard; show a countdown so customers don't leave mid-payment",
            "Poll every 15s not every 1s — the server should be authoritative, not the frontend",
            "Redirect to a success page after confirmation to prevent re-polling",
            "Show a 'copy address' button — mobile users can't easily type a Bitcoin address",
        ],
    },

    "react_payment_component": {
        "label": "React — BitcoinPaymentWidget Component",
        "description": "React component for Bitcoin payment with hooks, QR code, and WebSocket/polling support",
        "frameworks": ["React 18+"],
        "snippet": """\
// npm install qrcode.react
import React, { useState, useEffect, useCallback } from "react";
import { QRCodeSVG } from "qrcode.react";

export default function BitcoinPaymentWidget({ orderId, btcAddress, btcAmount, expiresInSeconds = 900 }) {
  const [status, setStatus]         = useState("waiting"); // waiting | confirmed | underpaid | expired
  const [secondsLeft, setSecondsLeft] = useState(expiresInSeconds);
  const [copied, setCopied]         = useState(false);

  // Countdown timer
  useEffect(() => {
    if (secondsLeft <= 0) { setStatus("expired"); return; }
    const id = setTimeout(() => setSecondsLeft(s => s - 1), 1000);
    return () => clearTimeout(id);
  }, [secondsLeft]);

  // Poll for status
  const checkStatus = useCallback(async () => {
    try {
      const res  = await fetch(`/api/order-status?order_id=${orderId}`);
      const data = await res.json();
      if (["confirmed", "underpaid", "expired"].includes(data.status)) {
        setStatus(data.status);
      }
    } catch (e) { console.warn("Status poll failed", e); }
  }, [orderId]);

  useEffect(() => {
    const id = setInterval(checkStatus, 15000);
    checkStatus();
    return () => clearInterval(id);
  }, [checkStatus]);

  const copyAddress = () => {
    navigator.clipboard.writeText(btcAddress).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const mm = String(Math.floor(secondsLeft / 60)).padStart(2, "0");
  const ss = String(secondsLeft % 60).padStart(2, "0");

  return (
    <div style={{ maxWidth: 400, margin: "auto", textAlign: "center", fontFamily: "monospace" }}>
      <h2>Pay with Bitcoin</h2>
      {status === "confirmed" && <p style={{ color: "green" }}>✅ Payment confirmed!</p>}
      {status === "underpaid" && <p style={{ color: "orange" }}>⚠️ Underpayment detected</p>}
      {status === "expired"   && <p style={{ color: "red" }}>❌ Payment window expired</p>}
      {status === "waiting"   && (
        <>
          <QRCodeSVG
            value={`bitcoin:${btcAddress}?amount=${btcAmount}`}
            size={200}
            includeMargin
          />
          <p>Send: <strong>{btcAmount} BTC</strong></p>
          <p style={{ wordBreak: "break-all" }}>{btcAddress}</p>
          <button onClick={copyAddress}>{copied ? "Copied!" : "Copy Address"}</button>
          <p>Expires in: {mm}:{ss}</p>
          <p style={{ color: "#888", fontSize: 12 }}>Checking every 15s…</p>
        </>
      )}
    </div>
  );
}

// Usage in parent component:
// <BitcoinPaymentWidget
//   orderId="order-123"
//   btcAddress="bc1q..."
//   btcAmount="0.00012345"
//   expiresInSeconds={900}
// />
""",
        "tips": [
            "Use QRCodeSVG not canvas QR for better accessibility and resolution",
            "Keep polling logic in a custom hook (useBitcoinPaymentStatus) for reusability",
            "Debounce clicks on 'Copy Address' to prevent spam",
            "Add a WebSocket fallback if your server supports it — faster than polling",
            "Memoize the fetch callback with useCallback to prevent re-render loops",
        ],
    },

    "vue_payment_component": {
        "label": "Vue 3 — Bitcoin Payment Component",
        "description": "Vue 3 Composition API payment page component",
        "frameworks": ["Vue 3"],
        "snippet": """\
<!-- npm install qrcode -->
<template>
  <div class="btc-payment">
    <h2>Pay with Bitcoin</h2>
    <canvas ref="qrCanvas" />
    <p>Send: <strong>{{ btcAmount }} BTC</strong></p>
    <p class="address">{{ btcAddress }}</p>
    <button @click="copyAddress">{{ copied ? 'Copied!' : 'Copy Address' }}</button>
    <p>Expires in: {{ countdown }}</p>
    <p v-if="status === 'confirmed'" class="success">✅ Payment confirmed!</p>
    <p v-else-if="status === 'underpaid'" class="warn">⚠️ Underpayment detected</p>
    <p v-else-if="status === 'expired'" class="error">❌ Expired</p>
    <p v-else class="muted">Waiting for payment…</p>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from "vue";
import QRCode from "qrcode";

const props = defineProps({
  orderId:    String,
  btcAddress: String,
  btcAmount:  String,
  expiresIn:  { type: Number, default: 900 },
});

const qrCanvas   = ref(null);
const secondsLeft = ref(props.expiresIn);
const status      = ref("waiting");
const copied      = ref(false);

const countdown = computed(() => {
  const m = String(Math.floor(secondsLeft.value / 60)).padStart(2, "0");
  const s = String(secondsLeft.value % 60).padStart(2, "0");
  return `${m}:${s}`;
});

let timerInterval, pollInterval;

onMounted(async () => {
  // Render QR
  await QRCode.toCanvas(qrCanvas.value, `bitcoin:${props.btcAddress}?amount=${props.btcAmount}`, { width: 200 });

  // Countdown
  timerInterval = setInterval(() => {
    secondsLeft.value--;
    if (secondsLeft.value <= 0) { status.value = "expired"; clearInterval(timerInterval); }
  }, 1000);

  // Polling
  const poll = async () => {
    const res  = await fetch(`/api/order-status?order_id=${props.orderId}`);
    const data = await res.json();
    if (["confirmed", "underpaid", "expired"].includes(data.status)) {
      status.value = data.status;
      clearInterval(pollInterval);
    }
  };
  poll();
  pollInterval = setInterval(poll, 15000);
});

onUnmounted(() => { clearInterval(timerInterval); clearInterval(pollInterval); });

async function copyAddress() {
  await navigator.clipboard.writeText(props.btcAddress);
  copied.value = true;
  setTimeout(() => { copied.value = false; }, 2000);
}
</script>
""",
        "tips": [
            "Clean up intervals with onUnmounted to avoid memory leaks",
            "Use QRCode.toCanvas for crisp rendering on all screen densities",
            "Emit a 'payment-confirmed' event to the parent component to trigger order flow",
        ],
    },

    "embed_script": {
        "label": "Embed Script — Drop-in Payment Widget",
        "description": "How to add a Bitcoin payment option to any existing HTML page with one script tag",
        "frameworks": ["Any HTML page"],
        "snippet": """\
<!-- Add just before </body> in your checkout page -->
<script
  src="https://your-bitcoin-backend.com/embed.js"
  data-api="https://your-bitcoin-backend.com"
  data-position="bottom-right"
  data-label="Pay with Bitcoin"
  data-theme="dark"
></script>

<!--
The embed.js script:
1. Injects a floating button in the corner
2. On click, opens a payment modal iframe
3. Communicates via postMessage when payment is confirmed
4. Closes itself and calls window.btcPaymentCallback(orderId) if defined

Minimal embed.js implementation:
-->
(function() {
  const API  = document.currentScript.dataset.api;
  const POS  = document.currentScript.dataset.position || "bottom-right";
  const LABEL = document.currentScript.dataset.label || "Pay Bitcoin";

  // Inject button
  const btn = document.createElement("button");
  btn.textContent = "₿ " + LABEL;
  btn.style.cssText = `
    position:fixed; ${POS.includes("bottom") ? "bottom:24px" : "top:24px"};
    ${POS.includes("right") ? "right:24px" : "left:24px"};
    z-index:9998; background:#f7931a; color:#fff;
    border:none; border-radius:8px; padding:12px 20px;
    font-size:15px; cursor:pointer; box-shadow:0 4px 12px rgba(0,0,0,.25);
  `;
  document.body.appendChild(btn);

  // Open modal on click
  btn.addEventListener("click", () => {
    const iframe = document.createElement("iframe");
    iframe.src = `${API}/widget?origin=${encodeURIComponent(location.origin)}`;
    iframe.style.cssText = `
      position:fixed; inset:0; width:100%; height:100%;
      border:none; z-index:9999; background:rgba(0,0,0,.6);
    `;
    document.body.appendChild(iframe);

    // Listen for confirmation
    window.addEventListener("message", function handler(e) {
      if (e.origin !== API) return;
      if (e.data?.type === "btc_payment_confirmed") {
        document.body.removeChild(iframe);
        window.removeEventListener("message", handler);
        if (typeof window.btcPaymentCallback === "function") {
          window.btcPaymentCallback(e.data.orderId);
        }
      }
      if (e.data?.type === "btc_payment_closed") {
        document.body.removeChild(iframe);
        window.removeEventListener("message", handler);
      }
    });
  });
})();
""",
        "tips": [
            "Use postMessage for iframe↔parent communication — never expose payment data in the URL",
            "Set sandbox attribute on the iframe for extra security if you control the embed page",
            "Provide a data-theme attribute so merchants can match their site branding",
            "The embed approach means merchants don't need to rebuild their checkout — just add a script tag",
        ],
    },
}

# ---------------------------------------------------------------------------
# BACKEND PATTERNS
# ---------------------------------------------------------------------------

BACKEND_PATTERNS: dict[str, dict] = {

    "fastapi_webhook": {
        "label": "FastAPI — Bitcoin Webhook Handler",
        "description": "Production-ready FastAPI webhook endpoint with HMAC verification, idempotency, and async processing",
        "frameworks": ["FastAPI", "Python"],
        "snippet": """\
import hashlib, hmac, json, logging
from fastapi import APIRouter, Header, HTTPException, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
logger = logging.getLogger(__name__)

WEBHOOK_SECRET = os.getenv("BLOCKONOMICS_WEBHOOK_SECRET", "")

# ── Blockonomics GET webhook ─────────────────────────────────────────────────
@router.get("/webhook/blockonomics")
async def blockonomics_webhook(
    secret: str,
    addr:   str,
    value:  int,
    txid:   str,
    status: int,
    background_tasks: BackgroundTasks,
):
    # 1. Verify secret token
    if not hmac.compare_digest(secret, WEBHOOK_SECRET):
        logger.warning("Blockonomics webhook: invalid secret from %s", addr)
        raise HTTPException(status_code=403, detail="Forbidden")

    # 2. Idempotency check — don't process same txid+status twice
    idempotency_key = f"{txid}:{status}"
    if await is_already_processed(idempotency_key):
        logger.info("Duplicate webhook skipped: %s", idempotency_key)
        return {"ok": True, "duplicate": True}

    # 3. Enqueue background processing
    background_tasks.add_task(process_bitcoin_payment, addr, value, txid, status, idempotency_key)
    return {"ok": True}


async def process_bitcoin_payment(addr, value_sats, txid, status_code, idempotency_key):
    try:
        order = await get_order_by_btc_address(addr)
        if not order:
            logger.error("No order found for address %s", addr)
            return

        if status_code >= 2:  # confirmed
            if value_sats >= order.expected_sats:
                await fulfill_order(order.id)
            else:
                await mark_underpaid(order.id, received=value_sats)
        elif status_code == 1:
            await mark_partial(order.id, received=value_sats)
        elif status_code == 0:
            await mark_unconfirmed(order.id, txid=txid)

        await mark_webhook_processed(idempotency_key)
    except Exception as e:
        logger.exception("Failed to process webhook %s: %s", idempotency_key, e)


# ── Coinbase Commerce POST webhook ───────────────────────────────────────────
@router.post("/webhook/coinbase")
async def coinbase_webhook(request: Request, x_cc_webhook_signature: str = Header(...)):
    body = await request.body()

    # HMAC-SHA256 verification
    expected = hmac.new(
        os.getenv("COINBASE_WEBHOOK_SECRET", "").encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, x_cc_webhook_signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    event = json.loads(body)
    event_type = event.get("type", "")

    if event_type == "charge:confirmed":
        order_id = event["data"]["metadata"].get("order_id")
        if order_id:
            await fulfill_order_by_ref(order_id)

    return {"ok": True}
""",
        "tips": [
            "Always return HTTP 200 quickly and process asynchronously — gateways retry on non-200",
            "Use idempotency keys to prevent double-fulfillment on webhook retries",
            "Log the raw payload BEFORE processing so you can replay on failure",
            "Verify HMAC/secret before doing ANY database work",
            "For Blockonomics: status >= 2 means confirmed; don't fulfill on status 0 or 1",
        ],
    },

    "flask_webhook": {
        "label": "Flask — Bitcoin Webhook Handler",
        "description": "Flask blueprint for handling Bitcoin payment webhooks",
        "frameworks": ["Flask", "Python"],
        "snippet": """\
import hashlib, hmac, json, logging, os
from flask import Blueprint, request, abort, jsonify
from threading import Thread

webhook_bp = Blueprint("webhook", __name__)
logger = logging.getLogger(__name__)

def verify_hmac(payload: bytes, received_sig: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received_sig)


@webhook_bp.route("/webhook/blockonomics", methods=["GET"])
def blockonomics_webhook():
    secret = request.args.get("secret", "")
    if not hmac.compare_digest(secret, os.getenv("BLOCKONOMICS_WEBHOOK_SECRET", "")):
        abort(403)

    addr   = request.args.get("addr", "")
    value  = int(request.args.get("value", 0))
    txid   = request.args.get("txid", "")
    status = int(request.args.get("status", -1))

    idempotency_key = f"{txid}:{status}"
    if is_already_processed(idempotency_key):
        return jsonify(ok=True, duplicate=True)

    # Non-blocking processing
    Thread(target=process_payment, args=(addr, value, txid, status, idempotency_key), daemon=True).start()
    return jsonify(ok=True)


@webhook_bp.route("/webhook/coinbase", methods=["POST"])
def coinbase_webhook():
    body = request.get_data()
    sig  = request.headers.get("X-CC-Webhook-Signature", "")
    if not verify_hmac(body, sig, os.getenv("COINBASE_WEBHOOK_SECRET", "")):
        abort(403)

    event = request.get_json(force=True)
    if event.get("type") == "charge:confirmed":
        order_id = event["data"]["metadata"].get("order_id")
        if order_id:
            Thread(target=fulfill_order_by_ref, args=(order_id,), daemon=True).start()

    return jsonify(ok=True)
""",
        "tips": [
            "Use Flask blueprints to keep webhook routes separate from main app",
            "Thread(daemon=True) for async processing in Flask — or use Celery for reliability",
            "request.get_data() reads raw bytes — needed for HMAC verification (don't use request.json before verify)",
        ],
    },

    "express_webhook": {
        "label": "Express.js — Bitcoin Webhook Handler",
        "description": "Node.js/Express webhook handler for Bitcoin payment gateways",
        "frameworks": ["Express.js", "Node.js"],
        "snippet": """\
const express = require("express");
const crypto  = require("crypto");
const router  = express.Router();

// Blockonomics GET webhook
router.get("/webhook/blockonomics", (req, res) => {
  const { secret, addr, value, txid, status } = req.query;

  if (!crypto.timingSafeEqual(
    Buffer.from(secret || ""),
    Buffer.from(process.env.BLOCKONOMICS_WEBHOOK_SECRET || "")
  )) {
    return res.status(403).json({ error: "Forbidden" });
  }

  const idempotencyKey = `${txid}:${status}`;
  if (isAlreadyProcessed(idempotencyKey)) {
    return res.json({ ok: true, duplicate: true });
  }

  // Async processing — respond immediately
  res.json({ ok: true });
  setImmediate(() => processPayment(addr, parseInt(value), txid, parseInt(status), idempotencyKey));
});

// Coinbase Commerce POST webhook
router.post("/webhook/coinbase", express.raw({ type: "application/json" }), (req, res) => {
  const sig      = req.headers["x-cc-webhook-signature"] || "";
  const expected = crypto
    .createHmac("sha256", process.env.COINBASE_WEBHOOK_SECRET || "")
    .update(req.body)
    .digest("hex");

  if (!crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(expected))) {
    return res.status(403).json({ error: "Invalid signature" });
  }

  const event = JSON.parse(req.body.toString());
  res.json({ ok: true }); // respond before processing

  if (event.type === "charge:confirmed") {
    const orderId = event.data?.metadata?.order_id;
    if (orderId) setImmediate(() => fulfillOrderByRef(orderId));
  }
});

module.exports = router;
""",
        "tips": [
            "Use express.raw() middleware for HMAC-verified routes — NOT express.json() — to preserve raw bytes",
            "crypto.timingSafeEqual prevents timing-based signature bypass attacks",
            "Call res.json() BEFORE the async work so the gateway gets a fast 200 response",
            "Use setImmediate() or a message queue (Bull, BullMQ) instead of blocking the event loop",
        ],
    },

    "laravel_webhook": {
        "label": "Laravel — Bitcoin Webhook Handler",
        "description": "Laravel controller and route for Bitcoin payment webhook processing",
        "frameworks": ["Laravel", "PHP"],
        "snippet": """\
<?php
// routes/web.php
Route::get('/webhook/blockonomics',  [BitcoinWebhookController::class, 'blockonomics']);
Route::post('/webhook/coinbase',     [BitcoinWebhookController::class, 'coinbase']);
Route::post('/webhook/bitpay',       [BitcoinWebhookController::class, 'bitpay']);

// app/Http/Controllers/BitcoinWebhookController.php
namespace App\\Http\\Controllers;

use Illuminate\\Http\\Request;
use Illuminate\\Support\\Facades\\Log;
use App\\Jobs\\ProcessBitcoinPayment;

class BitcoinWebhookController extends Controller
{
    // Blockonomics: GET with secret in query string
    public function blockonomics(Request $request)
    {
        if (!hash_equals($request->query('secret'), config('services.blockonomics.webhook_secret'))) {
            abort(403, 'Forbidden');
        }

        $addr   = $request->query('addr');
        $value  = (int) $request->query('value');
        $txid   = $request->query('txid');
        $status = (int) $request->query('status');

        $idempotencyKey = "{$txid}:{$status}";
        if (\\App\\Models\\WebhookLog::where('idempotency_key', $idempotencyKey)->exists()) {
            return response()->json(['ok' => true, 'duplicate' => true]);
        }

        // Dispatch to queue — don't block the response
        ProcessBitcoinPayment::dispatch($addr, $value, $txid, $status, $idempotencyKey);
        return response()->json(['ok' => true]);
    }

    // Coinbase: POST with HMAC signature header
    public function coinbase(Request $request)
    {
        $body      = $request->getContent();
        $sig       = $request->header('X-CC-Webhook-Signature', '');
        $secret    = config('services.coinbase.webhook_secret');
        $expected  = hash_hmac('sha256', $body, $secret);

        if (!hash_equals($expected, $sig)) {
            abort(403, 'Invalid signature');
        }

        $event = json_decode($body, true);
        if (($event['type'] ?? '') === 'charge:confirmed') {
            $orderId = $event['data']['metadata']['order_id'] ?? null;
            if ($orderId) {
                \\App\\Jobs\\FulfillOrder::dispatch($orderId);
            }
        }

        return response()->json(['ok' => true]);
    }
}

// app/Jobs/ProcessBitcoinPayment.php
class ProcessBitcoinPayment implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public function __construct(
        public string $address,
        public int    $valueSats,
        public string $txid,
        public int    $statusCode,
        public string $idempotencyKey,
    ) {}

    public function handle(): void
    {
        $order = \\App\\Models\\Order::where('btc_address', $this->address)->firstOrFail();
        match(true) {
            $this->statusCode >= 2 && $this->valueSats >= $order->expected_sats => $order->fulfill(),
            $this->statusCode >= 2                                               => $order->markUnderpaid($this->valueSats),
            $this->statusCode === 0                                              => $order->markUnconfirmed($this->txid),
            default => null,
        };
        \\App\\Models\\WebhookLog::create(['idempotency_key' => $this->idempotencyKey, 'processed' => true]);
    }
}
""",
        "tips": [
            "Use hash_equals() not === for HMAC comparison to prevent timing attacks",
            "Exclude webhook routes from CSRF middleware in VerifyCsrfToken::$except",
            "Use Laravel Queues (Redis-backed) for reliable async processing",
            "Log all incoming payloads before verification for debugging",
        ],
    },

    "django_webhook": {
        "label": "Django — Bitcoin Webhook View",
        "description": "Django class-based view for Bitcoin payment webhook handling",
        "frameworks": ["Django", "Python"],
        "snippet": """\
# views.py
import hashlib, hmac, json, logging, os
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name="dispatch")  # webhooks can't have CSRF tokens
class BlockonomicsWebhookView(View):
    def get(self, request):
        secret = request.GET.get("secret", "")
        if not hmac.compare_digest(secret, os.getenv("BLOCKONOMICS_WEBHOOK_SECRET", "")):
            return JsonResponse({"error": "Forbidden"}, status=403)

        addr   = request.GET.get("addr", "")
        value  = int(request.GET.get("value", 0))
        txid   = request.GET.get("txid", "")
        status = int(request.GET.get("status", -1))

        idempotency_key = f"{txid}:{status}"
        if WebhookEvent.objects.filter(idempotency_key=idempotency_key).exists():
            return JsonResponse({"ok": True, "duplicate": True})

        # Use Celery task for async processing
        from .tasks import process_btc_payment
        process_btc_payment.delay(addr, value, txid, status, idempotency_key)
        return JsonResponse({"ok": True})


@method_decorator(csrf_exempt, name="dispatch")
class CoinbaseWebhookView(View):
    def post(self, request):
        body = request.body
        sig  = request.headers.get("X-CC-Webhook-Signature", "")
        secret = os.getenv("COINBASE_WEBHOOK_SECRET", "")
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(expected, sig):
            return JsonResponse({"error": "Invalid signature"}, status=403)

        event = json.loads(body)
        if event.get("type") == "charge:confirmed":
            order_id = event["data"]["metadata"].get("order_id")
            if order_id:
                from .tasks import fulfill_order
                fulfill_order.delay(order_id)

        return JsonResponse({"ok": True})


# urls.py
from django.urls import path
from . import views
urlpatterns = [
    path("webhook/blockonomics/", views.BlockonomicsWebhookView.as_view()),
    path("webhook/coinbase/",     views.CoinbaseWebhookView.as_view()),
]

# tasks.py (Celery)
from celery import shared_task
@shared_task(bind=True, max_retries=3)
def process_btc_payment(self, addr, value_sats, txid, status_code, idempotency_key):
    try:
        order = Order.objects.get(btc_address=addr)
        if status_code >= 2 and value_sats >= order.expected_sats:
            order.fulfill()
        WebhookEvent.objects.create(idempotency_key=idempotency_key, processed=True)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)
""",
        "tips": [
            "Always add @csrf_exempt to webhook views — webhooks don't use browser sessions",
            "Use Celery with Redis/RabbitMQ for reliable async processing and retries",
            "Add max_retries=3 and countdown backoff to Celery tasks to handle transient failures",
        ],
    },
}

# ---------------------------------------------------------------------------
# PLUGIN ARCHITECTURE (WooCommerce / PrestaShop / WHMCS)
# ---------------------------------------------------------------------------

PLUGIN_ARCHITECTURE: dict[str, dict] = {

    "woocommerce": {
        "label": "WooCommerce Plugin Architecture",
        "description": "How Bitcoin payment gateway plugins hook into WooCommerce",
        "key_hooks": [
            "woocommerce_payment_gateways — register your payment class",
            "woocommerce_update_options_payment_gateways_{id} — save settings",
            "wc_api_{id} — handle incoming webhook callbacks",
            "woocommerce_thankyou_{id} — display order confirmation page",
            "woocommerce_receipt_{id} — display payment instructions before checkout",
        ],
        "class_structure": """\
<?php
// Your gateway class must extend WC_Payment_Gateway:

class WC_Bitcoin_Gateway extends WC_Payment_Gateway {

    public function __construct() {
        $this->id                 = 'my_bitcoin';
        $this->icon               = plugin_dir_url(__FILE__) . 'bitcoin.png';
        $this->has_fields         = false;
        $this->method_title       = 'Bitcoin';
        $this->method_description = 'Accept Bitcoin payments via Blockonomics';
        $this->supports           = ['products'];

        $this->init_form_fields();
        $this->init_settings();

        $this->title       = $this->get_option('title');
        $this->description = $this->get_option('description');
        $this->api_key     = $this->get_option('api_key');

        // Save settings hook
        add_action('woocommerce_update_options_payment_gateways_' . $this->id, [$this, 'process_admin_options']);
        // Webhook hook
        add_action('woocommerce_api_' . $this->id, [$this, 'handle_webhook']);
    }

    public function init_form_fields() {
        $this->form_fields = [
            'enabled'     => ['title' => 'Enable', 'type' => 'checkbox', 'default' => 'yes'],
            'title'       => ['title' => 'Title',  'type' => 'text',     'default' => 'Bitcoin'],
            'api_key'     => ['title' => 'API Key','type' => 'text'],
        ];
    }

    public function process_payment($order_id) {
        $order = wc_get_order($order_id);
        // 1. Generate BTC address via API
        $address = $this->get_new_btc_address();
        // 2. Save to order meta
        $order->update_meta_data('_btc_address', $address);
        $order->save();
        // 3. Mark as pending payment
        $order->update_status('pending', 'Awaiting Bitcoin payment');
        // 4. Redirect to payment page
        return ['result' => 'success', 'redirect' => $this->get_return_url($order)];
    }

    public function handle_webhook() {
        // Webhook URL: https://yourstore.com/?wc-api=my_bitcoin
        $secret = sanitize_text_field($_GET['secret'] ?? '');
        if (!hash_equals($secret, get_option('woocommerce_my_bitcoin_settings')['webhook_secret'] ?? '')) {
            status_header(403); exit;
        }
        $addr   = sanitize_text_field($_GET['addr']   ?? '');
        $value  = (int) ($_GET['value']  ?? 0);
        $txid   = sanitize_text_field($_GET['txid']   ?? '');
        $status = (int) ($_GET['status'] ?? -1);

        // Find order by btc_address meta
        $orders = wc_get_orders(['meta_key' => '_btc_address', 'meta_value' => $addr, 'limit' => 1]);
        if (empty($orders)) { status_header(200); exit; }
        $order = $orders[0];

        if ($status >= 2) { $order->payment_complete($txid); }
        status_header(200);
        exit;
    }
}

// Register the gateway
add_filter('woocommerce_payment_gateways', function($gateways) {
    $gateways[] = 'WC_Bitcoin_Gateway';
    return $gateways;
});
""",
        "settings_page_tips": [
            "Provide a 'Test Setup' button that calls /api/new_address and validates the API key",
            "Show the Callback URL clearly in settings so merchants can paste it into their gateway dashboard",
            "Use WooCommerce's built-in form field renderer for admin settings — it handles nonces automatically",
        ],
        "webhook_url_pattern": "https://yourstore.com/?wc-api={gateway_id}&secret={secret}",
        "order_status_flow": "pending → processing (on confirmation) → completed (on fulfillment)",
    },

    "prestashop": {
        "label": "PrestaShop Module Architecture",
        "description": "How Bitcoin payment modules work in PrestaShop",
        "key_hooks": [
            "paymentOptions — add a payment method to checkout",
            "displayPaymentReturn — show order confirmation with payment details",
            "actionValidateOrder — fired when order is validated",
            "moduleRoutes — register custom URLs for webhooks",
        ],
        "module_structure": """\
<?php
// modules/mybitcoin/mybitcoin.php

class MyBitcoin extends PaymentModule {

    public function __construct() {
        $this->name         = 'mybitcoin';
        $this->tab          = 'payments_gateways';
        $this->version      = '1.0.0';
        $this->author       = 'Your Name';
        $this->need_instance = 0;
        parent::__construct();
        $this->displayName  = 'Bitcoin Payment';
        $this->description  = 'Accept Bitcoin via Blockonomics';
    }

    public function install() {
        return parent::install()
            && $this->registerHook('paymentOptions')
            && $this->registerHook('displayPaymentReturn')
            && Db::getInstance()->execute("
                CREATE TABLE IF NOT EXISTS `{$_DB_PREFIX_}bitcoin_payments` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `id_order` INT NOT NULL,
                    `btc_address` VARCHAR(62) NOT NULL,
                    `expected_sats` BIGINT NOT NULL,
                    `txid` VARCHAR(64),
                    `status` TINYINT DEFAULT 0,
                    INDEX (`btc_address`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            ");
    }

    public function hookPaymentOptions($params) {
        $option = new \\PrestaShop\\PrestaShop\\Core\\Payment\\PaymentOption();
        $option->setCallToActionText('Pay with Bitcoin')
               ->setAction($this->context->link->getModuleLink($this->name, 'payment'))
               ->setLogo(Media::getMediaPath(_PS_MODULE_DIR_ . $this->name . '/bitcoin.png'));
        return [$option];
    }
}

// modules/mybitcoin/controllers/front/payment.php
class MyBitcoinPaymentModuleFrontController extends ModuleFrontController {
    public function postProcess() {
        $cart     = $this->context->cart;
        $address  = $this->module->getNewBtcAddress();
        $amount   = $this->module->convertToBtc($cart->getOrderTotal());
        // Store address with cart and redirect to payment page
        $this->redirectWithNotifications($this->context->link->getModuleLink(
            'mybitcoin', 'paymentpage', ['address' => $address, 'amount' => $amount]
        ));
    }
}
""",
        "webhook_url_pattern": "https://yourstore.com/module/mybitcoin/webhook?secret={secret}",
    },

    "whmcs": {
        "label": "WHMCS Gateway Module Architecture",
        "description": "How Bitcoin payment gateways integrate with WHMCS",
        "key_functions": [
            "yourgateway_config() — return config fields for admin setup page",
            "yourgateway_link() — return HTML for the payment button/page shown to customer",
            "yourgateway_capture() — capture a stored payment (if applicable)",
            "yourgateway_refund() — handle refunds",
            "checkCbTransID() — check transaction ID isn't already logged (prevent duplicates)",
            "logTransaction() — log the incoming callback",
            "addInvoicePayment() — mark invoice as paid",
        ],
        "module_structure": """\
<?php
// /modules/gateways/mybitcoin.php

function mybitcoin_config() {
    return [
        'FriendlyName' => ['Type' => 'System', 'Value' => 'Bitcoin (Blockonomics)'],
        'apiKey'       => ['FriendlyName' => 'API Key',        'Type' => 'text'],
        'webhookSecret' => ['FriendlyName' => 'Webhook Secret', 'Type' => 'password'],
    ];
}

function mybitcoin_link($params) {
    $invoiceId = $params['invoiceid'];
    $amount    = $params['amount'];
    $currency  = $params['currency'];
    $apiKey    = $params['apiKey'];

    // Generate BTC address
    $ch = curl_init("https://www.blockonomics.co/api/new_address");
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_HTTPHEADER     => ["Authorization: Bearer {$apiKey}"],
        CURLOPT_POSTFIELDS     => json_encode(['reset' => 0]),
    ]);
    $response = json_decode(curl_exec($ch), true);
    $btcAddress = $response['address'] ?? null;

    if (!$btcAddress) return '<p>Error: Could not generate Bitcoin address.</p>';

    // Store address → invoice mapping
    // (use a custom DB table or WHMCS custom fields)

    return <<<HTML
<div style="text-align:center">
  <p>Send Bitcoin to:</p>
  <code>{$btcAddress}</code>
  <br><small>Amount: {$amount} {$currency}</small>
</div>
HTML;
}

// Callback file: /modules/gateways/callback/mybitcoin.php
<?php
require_once '../../../init.php';
require_once '../../../includes/gatewayfunctions.php';
require_once '../../../includes/invoicefunctions.php';

$gatewayModuleName = 'mybitcoin';
$gatewayParams     = getGatewayVariables($gatewayModuleName);
if (!$gatewayParams['type']) die('Module Not Activated');

$secret    = $_GET['secret'] ?? '';
$invoiceId = /* look up from btc_address */ 0;
$txid      = $_GET['txid'] ?? '';
$amountBtc = 0; // convert from satoshis

if (!hash_equals($secret, $gatewayParams['webhookSecret'])) { http_response_code(403); die; }
if (checkCbTransID($txid)) { http_response_code(200); die; } // already processed

$invoice = localAPI('GetInvoice', ['invoiceid' => $invoiceId]);
if ($invoice['result'] === 'success') {
    logTransaction($gatewayModuleName, $_GET, 'Successful');
    addInvoicePayment($invoiceId, $txid, $amountBtc, 0, $gatewayModuleName);
}
http_response_code(200);
""",
        "webhook_url_pattern": "https://yourwhmcs.com/modules/gateways/callback/mybitcoin.php",
    },
}

# ---------------------------------------------------------------------------
# SECURITY CHECKLIST
# ---------------------------------------------------------------------------

SECURITY_KNOWLEDGE: dict[str, list] = {
    "critical": [
        "Verify HMAC signature on EVERY webhook before any processing (timing-safe compare)",
        "Never trust the webhook payload amount alone — query the blockchain or gateway API to verify",
        "Use idempotency keys to prevent double-fulfillment when webhooks are retried",
        "Store API keys in environment variables, never hardcoded in source code",
        "Require HTTPS (TLS 1.2+) for all webhook endpoints — reject plain HTTP",
        "Rate-limit webhook endpoints to prevent abuse (e.g. 100 req/min per IP)",
        "Validate and sanitize all webhook query parameters before database writes",
        "Reject webhooks with a timestamp older than 5 minutes (replay attack prevention)",
        "Never expose xpub keys in frontend code or API responses",
    ],
    "important": [
        "Log raw webhook payloads before processing so you can replay failed events",
        "Add database-level uniqueness constraint on btc_address (one address per order)",
        "Implement underpayment detection — fulfill only when received >= expected",
        "Set a minimum order amount (e.g. $1) to avoid dust attack orders",
        "Use CSP headers to prevent XSS on payment pages",
        "Escape all user-facing output containing Bitcoin addresses or transaction IDs",
        "Implement CSRF protection on admin settings pages (CORS + token)",
    ],
    "recommended": [
        "Generate a fresh Bitcoin address per order — never reuse addresses",
        "Add a payment expiry (15 minutes) and handle expired orders gracefully",
        "Send email notifications to merchants on payment confirmation",
        "Monitor for gap limit errors and alert before they block address generation",
        "Use a staging/test environment before going live (testnet or gateway sandbox)",
        "Implement partial payment (underpayment) UI: show remaining amount clearly",
        "Archive old webhook logs after 90 days to control database size",
    ],
}

# ---------------------------------------------------------------------------
# TESTING GUIDE
# ---------------------------------------------------------------------------

TESTING_GUIDES: dict[str, dict] = {
    "blockonomics": {
        "sandbox": "Blockonomics does not have a formal testnet sandbox — use Bitcoin testnet (tBTC) or test with tiny real amounts (0.0001 BTC)",
        "steps": [
            "Use Bitcoin testnet: get a testnet wallet (BlueWallet supports testnet), get free tBTC from a faucet",
            "In Blockonomics, register a testnet xpub (derived from a testnet seed)",
            "Set BLOCKONOMICS_API_KEY to your real key but use testnet addresses",
            "Send a testnet transaction to trigger the webhook",
            "Test your webhook locally using ngrok: ngrok http 8000 → use the ngrok URL as callback",
            "Verify all status transitions: 0 (unconfirmed) → 1 (partial if needed) → 2 (confirmed)",
        ],
        "unit_test_snippet": """\
# Unit test: webhook handler with mock secret
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_blockonomics_webhook_valid():
    resp = client.get("/webhook/blockonomics", params={
        "secret": "test_secret",
        "addr": "1A1zP1eP5QGefi2DMPTfTL5SLmv7Divf",
        "value": 100000,
        "txid": "abc" * 21 + "a",
        "status": 2,
    })
    assert resp.status_code == 200

def test_blockonomics_webhook_bad_secret():
    resp = client.get("/webhook/blockonomics", params={
        "secret": "wrong_secret",
        "addr":   "1A1zP1eP5QGefi2DMPTfTL5SLmv7Divf",
        "value":  100000,
        "txid":   "abc" * 21 + "a",
        "status": 2,
    })
    assert resp.status_code == 403
""",
    },
    "coinbase": {
        "sandbox": "Use commerce.coinbase.com with test mode — create a charge with a test API key from the sandbox environment",
        "steps": [
            "Log in to commerce.coinbase.com → Toggle 'Test Mode' in the dashboard",
            "Test mode generates fake charges you can mark as paid without real crypto",
            "Use the test webhook event tool in the dashboard to simulate charge:confirmed",
            "Test your webhook endpoint locally with: ngrok http 8000",
            "Simulate failed signatures by sending a wrong X-CC-Webhook-Signature header",
        ],
    },
    "bitpay": {
        "sandbox": "Use test.bitpay.com for sandbox testing — generate a test API token there",
        "steps": [
            "Create an account at test.bitpay.com (separate from bitpay.com)",
            "Generate a test API token under Payment Tools → API Token",
            "Use BASE_URL = 'https://test.bitpay.com' in your code during testing",
            "BitPay test environment accepts simulated payments — no real BTC needed",
            "Switch to bitpay.com and a live token when going to production",
        ],
    },
    "general_testing": {
        "checklist": [
            "Happy path: customer pays exact amount → order fulfilled",
            "Underpayment: customer pays less → order marked underpaid, not fulfilled",
            "Overpayment: customer pays more → order fulfilled, overpayment noted",
            "Duplicate webhook: same txid+status sent twice → processed only once",
            "Invalid signature: webhook with wrong secret → 403, no DB writes",
            "Expired order: payment arrives after expiry → handle gracefully",
            "No address found: webhook for unknown address → log and return 200",
            "Network error: API call to generate address fails → return meaningful error",
            "Gap limit reached: generate address when gap limit exceeded → clear error message",
        ],
    },
}

# ---------------------------------------------------------------------------
# WEB PAGE ARCHITECTURE
# ---------------------------------------------------------------------------

WEB_PAGE_ARCHITECTURE: dict[str, dict] = {

    "checkout_flow": {
        "label": "End-to-End Bitcoin Checkout Flow",
        "description": "The complete request/response cycle for a Bitcoin payment checkout",
        "flow": [
            "1. Customer clicks 'Pay with Bitcoin' on checkout page",
            "2. Frontend sends POST /api/create-btc-order { order_id, amount_usd } to your backend",
            "3. Backend calls gateway API to generate a fresh Bitcoin address",
            "4. Backend stores { order_id → btc_address, expected_sats } in the database",
            "5. Backend returns { btc_address, btc_amount, expires_in: 900 } to frontend",
            "6. Frontend renders payment page: QR code + address + countdown timer",
            "7. Customer opens Bitcoin wallet, scans QR, sends payment",
            "8. Bitcoin network broadcasts the transaction",
            "9. Gateway detects the transaction → sends webhook GET/POST to your server",
            "10. Your server verifies webhook signature, looks up order, checks amount",
            "11. If confirmed and amount correct → call fulfill_order(order_id)",
            "12. Frontend polls GET /api/order-status?order_id=X every 15s",
            "13. When status == 'confirmed', frontend redirects to success page",
        ],
        "error_paths": [
            "Address generation fails → show 'try again' button, don't block checkout",
            "Webhook never arrives → set a background job to check status after 30 min",
            "Underpayment detected → email merchant, show 'remaining amount' to customer",
            "Order expires → allow customer to restart with new address + current BTC price",
        ],
    },

    "html_payment_page_structure": {
        "label": "HTML Page Structure for Bitcoin Payment",
        "description": "Semantic, accessible HTML structure for a Bitcoin payment page",
        "snippet": """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Bitcoin Payment</title>
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'self'; script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; img-src 'self' data:">
  <style>
    :root { --btc-orange: #f7931a; }
    body { font-family: system-ui, sans-serif; max-width: 480px; margin: 40px auto; padding: 0 16px; }
    .payment-card { border: 1px solid #e0e0e0; border-radius: 12px; padding: 24px; text-align: center; }
    .btc-amount { font-size: 2rem; font-weight: bold; color: var(--btc-orange); }
    .address { word-break: break-all; font-family: monospace; font-size: 0.85rem; background: #f5f5f5; padding: 10px; border-radius: 6px; }
    .countdown { font-size: 1.5rem; color: #e53935; }
    .status-badge { display: inline-block; padding: 6px 14px; border-radius: 20px; font-weight: bold; }
    .status-waiting   { background: #fff3e0; color: #e65100; }
    .status-confirmed { background: #e8f5e9; color: #2e7d32; }
    .status-expired   { background: #ffebee; color: #c62828; }
  </style>
</head>
<body>
  <div class="payment-card" role="main" aria-live="polite">
    <h1>Pay with Bitcoin</h1>
    <div id="qr-container" aria-label="Bitcoin QR code"></div>
    <p class="btc-amount" id="amount"></p>
    <div class="address" id="address" role="textbox" aria-readonly="true" tabindex="0"></div>
    <button id="copy-btn" aria-label="Copy Bitcoin address">Copy Address</button>
    <p>Time remaining: <span class="countdown" id="countdown" aria-live="polite">15:00</span></p>
    <span class="status-badge status-waiting" id="status" role="status">Waiting for payment…</span>
  </div>
  <!-- Scripts loaded here -->
</body>
</html>
""",
        "accessibility_tips": [
            "Add aria-live='polite' to status messages so screen readers announce updates",
            "Use role='status' on the payment status badge",
            "Ensure QR code has alt text or an adjacent text description of the payment URI",
            "Keyboard-navigable copy button with aria-label",
        ],
    },

    "api_endpoint_design": {
        "label": "REST API Endpoints for Bitcoin Payment Integration",
        "description": "The minimum set of API endpoints needed to power a Bitcoin checkout",
        "endpoints": {
            "POST /api/btc/create-payment": {
                "purpose": "Generate a BTC address for an order and save to DB",
                "request":  '{"order_id": "abc123", "amount_usd": 49.99}',
                "response": '{"btc_address": "bc1q...", "btc_amount": "0.00052", "expected_sats": 52000, "expires_at": "2024-01-01T12:15:00Z"}',
            },
            "GET /api/btc/order-status": {
                "purpose": "Poll payment status — called by frontend every 15s",
                "request":  "?order_id=abc123",
                "response": '{"status": "waiting|confirmed|underpaid|expired", "received_sats": 0}',
            },
            "GET /webhook/blockonomics": {
                "purpose": "Receive payment notification from Blockonomics",
                "params":   "?secret=X&addr=Y&value=Z&txid=T&status=S",
                "response": '{"ok": true}',
            },
            "POST /webhook/coinbase": {
                "purpose": "Receive payment notification from Coinbase Commerce",
                "headers":  "X-CC-Webhook-Signature: hmac_value",
                "response": '{"ok": true}',
            },
        },
    },
}

# ---------------------------------------------------------------------------
# Public API used by agent/tools.py
# ---------------------------------------------------------------------------

def get_db_schema(db_type: str) -> str:
    """
    Return a database schema guide for Bitcoin payment integration.
    db_type: mysql_woocommerce | postgresql_custom | sqlite_minimal
    """
    db_type = db_type.lower().strip().replace("-", "_").replace(" ", "_")
    if db_type not in DB_SCHEMAS:
        available = ", ".join(DB_SCHEMAS.keys())
        return f"Unknown db_type '{db_type}'. Available: {available}"

    s = DB_SCHEMAS[db_type]
    lines = [f"## {s['label']}\n", f"{s['description']}\n"]

    if s.get("sql"):
        lines.append("**SQL Schema:**")
        lines.append("```sql")
        lines.append(s["sql"].strip())
        lines.append("```\n")

    for key in ("orm_models", "sqlalchemy_models"):
        if s.get(key):
            lang = "python"
            lines.append(f"**ORM Models:**")
            lines.append(f"```{lang}")
            lines.append(s[key].strip())
            lines.append("```\n")

    if s.get("tips"):
        lines.append("**Tips:**")
        for t in s["tips"]:
            lines.append(f"  - {t}")

    return "\n".join(lines)


def get_frontend_pattern(framework: str) -> str:
    """
    Return a frontend code pattern for Bitcoin payment UI.
    framework: vanilla_js_payment_page | react_payment_component | vue_payment_component | embed_script
    """
    key = framework.lower().strip().replace("-", "_").replace(" ", "_")
    # fuzzy match
    match = next((k for k in FRONTEND_PATTERNS if key in k or k in key), None)
    if not match:
        available = ", ".join(FRONTEND_PATTERNS.keys())
        return f"Unknown framework '{framework}'. Available: {available}"

    p = FRONTEND_PATTERNS[match]
    lines = [f"## {p['label']}\n", f"{p['description']}\n"]

    if p.get("frameworks"):
        lines.append(f"**Works with:** {', '.join(p['frameworks'])}\n")

    lines.append("**Code:**")
    ext = "jsx" if "react" in match else "vue" if "vue" in match else "html"
    lines.append(f"```{ext}")
    lines.append(p["snippet"].strip())
    lines.append("```\n")

    if p.get("tips"):
        lines.append("**Tips:**")
        for t in p["tips"]:
            lines.append(f"  - {t}")

    return "\n".join(lines)


def get_backend_pattern(framework: str) -> str:
    """
    Return a backend webhook handler pattern.
    framework: fastapi | flask | express | laravel | django
    """
    key = framework.lower().strip()
    match = next((k for k in BACKEND_PATTERNS if key in k), None)
    if not match:
        available = ", ".join(BACKEND_PATTERNS.keys())
        return f"Unknown framework '{framework}'. Available: {available}"

    p = BACKEND_PATTERNS[match]
    lines = [f"## {p['label']}\n", f"{p['description']}\n"]

    if p.get("frameworks"):
        lines.append(f"**Works with:** {', '.join(p['frameworks'])}\n")

    lang = "php" if "laravel" in match else "javascript" if "express" in match else "python"
    lines.append("**Code:**")
    lines.append(f"```{lang}")
    lines.append(p["snippet"].strip())
    lines.append("```\n")

    if p.get("tips"):
        lines.append("**Tips:**")
        for t in p["tips"]:
            lines.append(f"  - {t}")

    return "\n".join(lines)


def get_plugin_architecture(platform: str) -> str:
    """
    Return plugin architecture guide for a specific platform.
    platform: woocommerce | prestashop | whmcs
    """
    key = platform.lower().strip()
    match = next((k for k in PLUGIN_ARCHITECTURE if key in k), None)
    if not match:
        available = ", ".join(PLUGIN_ARCHITECTURE.keys())
        return f"Unknown platform '{platform}'. Available: {available}"

    p = PLUGIN_ARCHITECTURE[match]
    lines = [f"## {p['label']}\n", f"{p['description']}\n"]

    if p.get("key_hooks"):
        lines.append("**Key Hooks/Functions:**")
        for h in p["key_hooks"]:
            lines.append(f"  - `{h}`")
        lines.append("")

    if p.get("key_functions"):
        lines.append("**Key Functions:**")
        for f in p["key_functions"]:
            lines.append(f"  - `{f}`")
        lines.append("")

    if p.get("class_structure") or p.get("module_structure"):
        code = p.get("class_structure") or p.get("module_structure", "")
        lines.append("**Plugin/Module Structure:**")
        lines.append("```php")
        lines.append(code.strip())
        lines.append("```\n")

    if p.get("webhook_url_pattern"):
        lines.append(f"**Webhook URL pattern:** `{p['webhook_url_pattern']}`\n")

    if p.get("order_status_flow"):
        lines.append(f"**Order status flow:** {p['order_status_flow']}\n")

    if p.get("settings_page_tips"):
        lines.append("**Settings Page Tips:**")
        for t in p["settings_page_tips"]:
            lines.append(f"  - {t}")

    return "\n".join(lines)


def get_security_checklist() -> str:
    """Return a comprehensive security checklist for Bitcoin payment integrations."""
    lines = ["## Bitcoin Payment Gateway Security Checklist\n"]

    for severity, items in SECURITY_KNOWLEDGE.items():
        lines.append(f"### {severity.upper()}")
        for item in items:
            prefix = "🔴" if severity == "critical" else "🟡" if severity == "important" else "🟢"
            lines.append(f"  {prefix} {item}")
        lines.append("")

    return "\n".join(lines)


def get_testing_guide(gateway: str) -> str:
    """
    Return a testing guide for a specific gateway.
    gateway: blockonomics | coinbase | bitpay | general
    """
    key = gateway.lower().strip()
    match = next((k for k in TESTING_GUIDES if key in k), "general_testing")

    guide = TESTING_GUIDES.get(match, TESTING_GUIDES["general_testing"])
    lines = [f"## Testing Guide — {gateway.title()}\n"]

    if guide.get("sandbox"):
        lines.append(f"**Sandbox/Test Environment:** {guide['sandbox']}\n")

    if guide.get("steps"):
        lines.append("**Setup Steps:**")
        for i, step in enumerate(guide["steps"], 1):
            lines.append(f"  {i}. {step}")
        lines.append("")

    if guide.get("checklist"):
        lines.append("**Test Case Checklist:**")
        for item in guide["checklist"]:
            lines.append(f"  ☐ {item}")
        lines.append("")

    if guide.get("unit_test_snippet"):
        lines.append("**Unit Test Example:**")
        lines.append("```python")
        lines.append(guide["unit_test_snippet"].strip())
        lines.append("```")

    return "\n".join(lines)


def get_checkout_flow_architecture() -> str:
    """Return the end-to-end Bitcoin checkout flow and API design."""
    flow = WEB_PAGE_ARCHITECTURE["checkout_flow"]
    api  = WEB_PAGE_ARCHITECTURE["api_endpoint_design"]
    page = WEB_PAGE_ARCHITECTURE["html_payment_page_structure"]

    lines = [f"## {flow['label']}\n", f"{flow['description']}\n"]
    lines.append("**Happy Path Flow:**")
    for step in flow["flow"]:
        lines.append(f"  {step}")

    lines.append("\n**Error Paths:**")
    for ep in flow["error_paths"]:
        lines.append(f"  - {ep}")

    lines.append(f"\n## {api['label']}\n")
    for endpoint, detail in api["endpoints"].items():
        lines.append(f"**`{endpoint}`** — {detail['purpose']}")
        if detail.get("request"):
            lines.append(f"  Request: `{detail['request']}`")
        if detail.get("response"):
            lines.append(f"  Response: `{detail['response']}`")
        if detail.get("params"):
            lines.append(f"  Params: `{detail['params']}`")
        if detail.get("headers"):
            lines.append(f"  Headers: `{detail['headers']}`")
        lines.append("")

    lines.append(f"## {page['label']}\n")
    lines.append("```html")
    lines.append(page["snippet"].strip())
    lines.append("```\n")
    lines.append("**Accessibility Tips:**")
    for t in page["accessibility_tips"]:
        lines.append(f"  - {t}")

    return "\n".join(lines)


def list_architecture_topics() -> str:
    """List all available architecture topics and their sub-topics."""
    lines = ["## Available Architecture Topics\n"]

    lines.append("**Database Schemas:**")
    for k, v in DB_SCHEMAS.items():
        lines.append(f"  - `{k}` — {v['label']}")

    lines.append("\n**Frontend Patterns:**")
    for k, v in FRONTEND_PATTERNS.items():
        lines.append(f"  - `{k}` — {v['label']} ({', '.join(v['frameworks'])})")

    lines.append("\n**Backend Patterns:**")
    for k, v in BACKEND_PATTERNS.items():
        lines.append(f"  - `{k}` — {v['label']} ({', '.join(v['frameworks'])})")

    lines.append("\n**Plugin Architecture:**")
    for k, v in PLUGIN_ARCHITECTURE.items():
        lines.append(f"  - `{k}` — {v['label']}")

    lines.append("\n**Other Topics:**")
    lines.append("  - Security checklist (get_security_checklist)")
    lines.append("  - Testing guides: blockonomics, coinbase, bitpay, general")
    lines.append("  - Checkout flow + API design (get_checkout_flow_architecture)")

    return "\n".join(lines)
