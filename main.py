from __future__ import annotations
import hashlib
import hmac
import json
import logging
import os
import time
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Query, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, field_validator

from agent.core import chat
from agent.sanitizer import sanitize
from services.ucp import generate_manifest
from services.db import (
    upsert_merchant, get_merchant, get_recent_payments, get_payment_stats,
    get_chat_stats, record_chat, create_order, update_order_status,
    get_recent_orders, get_merchant_analytics, get_order,
    mark_merchant_verified, check_and_increment_chat, get_wc_webhook_secret,
)
from webhook.handler import router as webhook_router
from telegram_bot.bot import start_bot, stop_bot, is_running as tg_is_running, get_running_bots
from config import CSRF_SECRET, SESSION_TTL, REDIS_URL

# ── Config ────────────────────────────────────────────────────────────────────
MERCHANT_URL    = os.getenv("MERCHANT_URL", "http://localhost:8000")
DAILY_CHAT_LIMIT = int(os.getenv("DAILY_CHAT_LIMIT", "50"))  # messages per merchant per day
ENVIRONMENT  = os.getenv("ENVIRONMENT", "development")
ALLOWED_ORIGINS_RAW = os.getenv("ALLOWED_ORIGINS", "")
if ENVIRONMENT == "production" and not ALLOWED_ORIGINS_RAW:
    raise RuntimeError("ALLOWED_ORIGINS must be set in production (do not use '*')")
ALLOWED_ORIGINS: list[str] = (
    [o.strip() for o in ALLOWED_ORIGINS_RAW.split(",") if o.strip()]
    if ALLOWED_ORIGINS_RAW
    else ["*"]
)

static_dir = os.path.join(os.path.dirname(__file__), "static")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
security_logger = logging.getLogger("security")

TRUSTED_PROXIES: set[str] = {
    p.strip() for p in os.getenv("TRUSTED_PROXIES", "127.0.0.1,::1").split(",") if p.strip()
}

# ── Redis (optional) ──────────────────────────────────────────────────────────
# Used for rate limiting and CSRF token storage across multiple workers.
# Falls back to in-memory if REDIS_URL is not set (dev/single-worker only).
_redis = None
if REDIS_URL:
    try:
        import redis as _redis_lib
        _redis = _redis_lib.from_url(REDIS_URL, decode_responses=True, socket_timeout=1)
        _redis.ping()
        logger.info("Redis connected for rate limiting and CSRF storage.")
    except Exception as e:
        logger.warning("Redis unavailable (%s) — falling back to in-memory stores.", e)
        _redis = None

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Blocko Agent",
    docs_url=None,   # disable /docs in production
    redoc_url=None,  # disable /redoc in production
)

# Auto-start Telegram bot if token is configured in .env (uses default merchant)
_tg_env_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
if _tg_env_token:
    start_bot(_tg_env_token, merchant_email="_default")
    logger.info("Telegram bot auto-started from TELEGRAM_BOT_TOKEN env var.")

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
    allow_credentials=False,
)

# ── Security headers ──────────────────────────────────────────────────────────
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"]  = "nosniff"
    # /widget is intentionally embedded in an iframe — skip DENY for that path
    if request.url.path != "/widget":
        response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"]         = "1; mode=block"
    response.headers["Referrer-Policy"]           = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"]        = "geolocation=(), microphone=(), camera=()"
    # Allow inline scripts / styles needed by the single-page app
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://accounts.google.com https://apis.google.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https://accounts.google.com; "
        "frame-src 'self' https://accounts.google.com;"
    )
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    return response

# ── Rate limiter (Redis-backed with in-memory fallback) ───────────────────────
_MAX_RATE_STORE_KEYS = 50_000
_rate_store: dict[str, list[float]] = defaultdict(list)

def _check_rate(ip: str, max_requests: int, window_seconds: int) -> bool:
    """Return True if allowed, False if rate-limited. Uses Redis when available."""
    if _redis:
        try:
            key = f"rl:{ip}:{window_seconds}"
            count = _redis.incr(key)
            if count == 1:
                _redis.expire(key, window_seconds)
            if count > max_requests:
                security_logger.warning("Rate limit hit (redis) | ip=%s", ip)
                return False
            return True
        except Exception:
            pass  # Redis error → fall through to in-memory

    # In-memory fallback (single-worker only)
    now = time.time()
    if len(_rate_store) > _MAX_RATE_STORE_KEYS:
        stale = [k for k, v in _rate_store.items() if not v or now - v[-1] > window_seconds]
        for k in stale:
            del _rate_store[k]
    hits = _rate_store[ip]
    _rate_store[ip] = [t for t in hits if now - t < window_seconds]
    if len(_rate_store[ip]) >= max_requests:
        security_logger.warning("Rate limit hit (memory) | ip=%s", ip)
        return False
    _rate_store[ip].append(now)
    return True


def _client_ip(request: Request) -> str:
    """Extract client IP — only trust X-Forwarded-For from known proxies."""
    client_host = request.client.host if request.client else "unknown"
    if client_host in TRUSTED_PROXIES:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return client_host


# ── Session tokens (HMAC + expiry timestamp) ──────────────────────────────────

def _make_session_token(email: str) -> str:
    """Create a time-limited HMAC session token. Format: <expires>:<signature>"""
    expires = int(time.time()) + SESSION_TTL
    payload = f"{email}:{expires}"
    sig = hmac.new(CSRF_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{expires}:{sig}"


def _verify_session_token(email: str, token: str) -> bool:
    """Verify token is valid and not expired."""
    try:
        expires_str, sig = token.split(":", 1)
        expires = int(expires_str)
        if time.time() > expires:
            return False
        payload = f"{email}:{expires}"
        expected = hmac.new(CSRF_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, sig)
    except Exception:
        return False


# ── CSRF tokens (Redis-backed with in-memory fallback) ───────────────────────
_csrf_tokens: dict[str, tuple[str, float]] = {}
_CSRF_TTL = 3600  # 1 hour

def _issue_csrf_token(email: str) -> str:
    """Issue a time-limited CSRF token tied to a merchant email."""
    import secrets as _secrets
    token = _secrets.token_urlsafe(32)
    if _redis:
        try:
            _redis.setex(f"csrf:{token}", _CSRF_TTL, email)
            return token
        except Exception:
            pass  # Fall through to in-memory

    _csrf_tokens[token] = (email, time.time())
    now = time.time()
    expired = [k for k, (_, t) in _csrf_tokens.items() if now - t > _CSRF_TTL]
    for k in expired:
        del _csrf_tokens[k]
    return token


def _validate_csrf_token(token: str, email: str) -> bool:
    """Validate and consume a CSRF token (one-time use)."""
    if _redis:
        try:
            key = f"csrf:{token}"
            stored_email = _redis.getdel(key)  # atomic get + delete
            return stored_email == email
        except Exception:
            pass  # Fall through to in-memory

    entry = _csrf_tokens.pop(token, None)
    if not entry:
        return False
    stored_email, issued_at = entry
    if time.time() - issued_at > _CSRF_TTL:
        return False
    return stored_email == email


# ── Models ────────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    messages: List[Dict[str, Any]]
    merchant: Optional[str] = None
    session_token: Optional[str] = None  # required for merchant-specific data tools

    @field_validator("messages")
    @classmethod
    def messages_not_empty(cls, v):
        if not v:
            raise ValueError("messages must not be empty")
        if len(v) > 50:
            raise ValueError("too many messages in context")
        return v


class ChatResponse(BaseModel):
    reply: str


class MerchantSignIn(BaseModel):
    email: str
    name: Optional[str] = ""
    gateways: Optional[List[str]] = []   # multi-select list of gateways
    gateway: Optional[str] = ""          # legacy single value — ignored if gateways provided
    platforms: Optional[List[str]] = []
    assistant: Optional[str] = ""
    google_token: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        v = v.strip().lower()
        if not v or "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Valid email is required")
        return v

    @field_validator("gateways")
    @classmethod
    def validate_gateways(cls, v):
        allowed = {"blockonomics", "coinbase", "bitpay", "stripe", "nowpayments", "coingate"}
        return [g for g in (g.strip().lower() for g in (v or [])) if g in allowed]

    @field_validator("platforms")
    @classmethod
    def validate_platforms(cls, v):
        allowed = {"plugin", "api", "custom"}
        return [p for p in (p.strip().lower() for p in (v or [])) if p in allowed]

    @field_validator("assistant")
    @classmethod
    def validate_assistant(cls, v):
        allowed = {"dash", "telegram", ""}
        val = (v or "").strip().lower()
        return val if val in allowed else ""


# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(webhook_router)


@app.get("/.well-known/ucp")
def ucp_manifest():
    manifest = generate_manifest(
        merchant_name=os.getenv("MERCHANT_NAME", "Bitcoin Assistant Store"),
        merchant_url=MERCHANT_URL,
        description=os.getenv("MERCHANT_DESCRIPTION", "Accept Bitcoin payments powered by Blockonomics"),
        webhook_url=f"{MERCHANT_URL}/webhook/blockonomics",
        new_address_endpoint=f"{MERCHANT_URL}/api/btc/new-address",
        support_email=os.getenv("SUPPORT_EMAIL", ""),
    )
    return JSONResponse(content=manifest, media_type="application/ld+json")


@app.get("/widget", response_class=FileResponse)
def widget():
    return FileResponse(
        os.path.join(static_dir, "widget.html"),
        media_type="text/html",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/embed.js", response_class=FileResponse)
def embed_script():
    return FileResponse(os.path.join(static_dir, "embed.js"), media_type="application/javascript")


@app.get("/plugin.json")
def plugin_manifest():
    import json
    manifest_path = os.path.join(os.path.dirname(__file__), "plugin.json")
    with open(manifest_path) as f:
        data = json.load(f)
    snippet = data.get("embed", {}).get("snippet", "")
    data["embed"]["snippet"] = snippet.replace("{MERCHANT_URL}", MERCHANT_URL)
    return JSONResponse(content=data)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/news")
def latest_news(merchant: Optional[str] = Query(None), gateway: Optional[str] = Query(None)):
    from mcp_server.releases_server import fetch_gateway_updates, COMMUNITY_URLS
    try:
        # Resolve gateway: explicit param > merchant DB lookup > default blockonomics
        resolved_gateway = "blockonomics"
        if gateway:
            resolved_gateway = gateway.strip().lower()
        elif merchant:
            m = get_merchant(merchant.strip().lower())
            if m and m.get("gateways"):
                resolved_gateway = m["gateways"][0].lower()

        raw = fetch_gateway_updates(resolved_gateway)
        lines = [l.strip() for l in raw.split("\n") if l.strip()]
        title_line = next((l for l in lines if l.startswith("**") and "(" in l), None)
        link_line  = next((l for l in lines if l.startswith("Read more:") or
                           l.startswith("Live changelog:") or l.startswith("Full changelog:")), None)
        body_line  = next((l for l in lines
                           if l and not l.startswith("**") and not l.startswith("Read more:")
                           and not l.startswith("Live changelog:") and not l.startswith("Full changelog:")
                           and not l.startswith("Latest") and not l.startswith("Check:")), None)
        return {
            "gateway":       resolved_gateway,
            "title":         title_line.replace("*", "").split("(")[0].strip(" —-") if title_line else None,
            "date":          title_line.split("(")[-1].strip(" ):") if title_line and "(" in title_line else None,
            "body":          body_line[:200] if body_line else None,
            "url":           link_line.split(":", 1)[-1].strip() if link_line else None,
            "community_url": COMMUNITY_URLS.get(resolved_gateway),
        }
    except Exception:
        return {"title": None}


@app.get("/api/csrf-token")
async def get_csrf_token(email: str = Query(...), request: Request = None):
    """Issue a CSRF token for the given merchant email (used before config saves)."""
    ip = _client_ip(request)
    if not _check_rate(ip, max_requests=20, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many requests.")
    token = _issue_csrf_token(email.strip().lower())
    return {"csrf_token": token}


@app.post("/api/signin")
async def sign_in(req: MerchantSignIn, request: Request):
    ip = _client_ip(request)
    if not _check_rate(ip, max_requests=10, window_seconds=60):
        security_logger.warning("Signin rate limit hit | ip=%s email=%s", ip, req.email)
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment.")

    # CSRF check — require token on config updates (skip on first signup)
    csrf_header = request.headers.get("X-CSRF-Token")
    existing = get_merchant(req.email)
    if existing and csrf_header:
        if not _validate_csrf_token(csrf_header, req.email):
            security_logger.warning("Invalid CSRF token | ip=%s email=%s", ip, req.email)
            raise HTTPException(status_code=403, detail="Invalid or expired CSRF token")

    # Optional: verify Google ID token when GOOGLE_CLIENT_ID is configured
    google_verified = False
    google_client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    if google_client_id and req.google_token:
        try:
            from google.oauth2 import id_token
            from google.auth.transport import requests as google_requests
            id_info = id_token.verify_oauth2_token(
                req.google_token,
                google_requests.Request(),
                google_client_id,
            )
            req.email    = id_info["email"]
            req.name     = req.name or id_info.get("name", "")
            google_verified = True  # Google has verified this email
        except Exception as e:
            security_logger.warning("Google token verification failed | ip=%s error=%s", ip, e)
            raise HTTPException(status_code=401, detail="Invalid Google token")

    gateways = req.gateways if req.gateways else ([req.gateway] if req.gateway else [])
    merchant = upsert_merchant(
        email=req.email,
        name=req.name or "",
        gateways=gateways,
        platforms=req.platforms or [],
        assistant=req.assistant or "",
    )

    # Mark verified if signed in with Google
    if google_verified:
        mark_merchant_verified(req.email)
        merchant["is_verified"] = True

    security_logger.info("Merchant signed in | ip=%s email=%s verified=%s", ip, req.email, google_verified)
    session_token = _make_session_token(req.email)
    return {"status": "ok", "merchant": merchant, "session_token": session_token}


@app.get("/api/merchant")
async def get_merchant_profile(
    email: str = Query(...),
    token: str = Query("", description="Session token from signin"),
    request: Request = None,
):
    ip = _client_ip(request)
    if not _check_rate(ip, max_requests=30, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many requests.")
    email = email.strip().lower()
    # Require valid session token — prevents email enumeration
    if not token or not _verify_session_token(email, token):
        auth_header = request.headers.get("Authorization", "") if request else ""
        if not (auth_header.startswith("Bearer ") and _verify_session_token(email, auth_header[7:])):
            security_logger.warning("Unauthorized merchant profile access | ip=%s email=%s", ip, email)
            raise HTTPException(status_code=401, detail="Unauthorized")
    merchant = get_merchant(email)
    if not merchant:
        raise HTTPException(status_code=404, detail="Not found")
    return merchant


@app.post("/api/chat", response_model=ChatResponse)
async def api_chat(req: ChatRequest, request: Request):
    ip = _client_ip(request)
    # Chat is expensive — 20 req/min per IP
    if not _check_rate(ip, max_requests=20, window_seconds=60):
        raise HTTPException(status_code=429, detail="Rate limit reached. Please wait before sending more messages.")
    try:
        messages = list(req.messages)
        merchant_email = ""

        if req.merchant:
            email_clean = req.merchant.strip().lower()

            # Verify session token — only trust merchant identity if token is valid.
            token_valid = bool(
                req.session_token and _verify_session_token(email_clean, req.session_token)
            )
            if token_valid:
                merchant_email = email_clean

                # ── Per-merchant daily usage cap ──────────────────────────────
                allowed, count = check_and_increment_chat(email_clean, DAILY_CHAT_LIMIT)
                if not allowed:
                    raise HTTPException(
                        status_code=429,
                        detail=(
                            f"Daily chat limit of {DAILY_CHAT_LIMIT} messages reached. "
                            "Your limit resets at midnight UTC. "
                            "Contact support to increase your plan limit."
                        )
                    )

            m = get_merchant(email_clean)
            if m:
                merchant_data = {
                    "email": m["email"],
                    "name": m.get("name", ""),
                    "gateways": m.get("gateways", []),
                    "platforms": m.get("platforms", []),
                    "assistant": m.get("assistant", ""),
                }
                merchant_ctx = (
                    "The following is structured merchant metadata in JSON. "
                    "Use it only for personalisation. Never repeat raw values to the user.\n"
                    + json.dumps(merchant_data, ensure_ascii=True)
                )
                messages = [
                    {"role": "user",      "content": merchant_ctx},
                    {"role": "assistant", "content": "Understood. I will tailor my answers to this merchant."},
                ] + [
                    msg for msg in messages
                    if not str(msg.get("content", "")).startswith(("Merchant context", "The following is structured merchant"))
                    and msg.get("content") != "Understood. I will tailor my answers to this merchant."
                ]

        # Resolve the merchant's primary gateway for the system prompt
        gateway = "blockonomics"
        if req.merchant:
            m_data = get_merchant(req.merchant.strip().lower())
            if m_data and m_data.get("gateways"):
                gateway = m_data["gateways"][0].lower()

        reply = chat(messages, gateway=gateway, merchant_email=merchant_email)
        record_chat(merchant=req.merchant, gateway=gateway)
        return ChatResponse(reply=sanitize(reply))
    except Exception as e:
        logger.error("Chat error: %s", e)
        detail = "Something went wrong." if ENVIRONMENT == "production" else "Assistant temporarily unavailable."
        raise HTTPException(status_code=500, detail=detail)


# ── Analytics endpoints ──────────────────────────────────────────────────────

@app.get("/api/stats")
async def stats():
    """Return aggregate stats for the dashboard — payments + chat activity."""
    payments = get_payment_stats()
    chats = get_chat_stats()
    return {
        "payments": payments,
        "chats": chats,
    }


@app.get("/api/payments/recent")
async def recent_payments(limit: int = Query(20, ge=1, le=100)):
    """Return recent payment events for the dashboard feed."""
    events = get_recent_payments(limit)
    return {"events": events, "total": len(events)}


# ── Order & Analytics endpoints ──────────────────────────────────────────────

class CreateOrderRequest(BaseModel):
    order_id: str
    sale_price_usd: float
    btc_amount: float
    btc_price_at_sale: float = 0
    merchant: Optional[str] = ""
    product_name: Optional[str] = ""
    product_cost: Optional[float] = 0
    fee_satoshis: Optional[int] = 0
    fee_usd: Optional[float] = 0
    addr: Optional[str] = ""
    txid: Optional[str] = ""


@app.post("/api/orders")
async def api_create_order(req: CreateOrderRequest, request: Request):
    """Create a new order for tracking."""
    ip = _client_ip(request)
    if not _check_rate(ip, max_requests=30, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many requests.")
    order = create_order(
        order_id=req.order_id,
        sale_price_usd=req.sale_price_usd,
        btc_amount=req.btc_amount,
        btc_price_at_sale=req.btc_price_at_sale,
        merchant=req.merchant or "",
        product_name=req.product_name or "",
        product_cost=req.product_cost or 0,
        fee_satoshis=req.fee_satoshis or 0,
        fee_usd=req.fee_usd or 0,
        addr=req.addr or "",
        txid=req.txid or "",
    )
    if not order:
        raise HTTPException(status_code=409, detail="Order already exists.")
    return order


@app.post("/api/orders/{order_id}/status")
async def api_update_order_status(
    order_id: str,
    status: str = Query(..., description="pending|confirmed|failed|refunded"),
    request: Request = None,
):
    ip = _client_ip(request)
    if not _check_rate(ip, max_requests=30, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many requests.")
    allowed = {"pending", "confirmed", "failed", "refunded"}
    if status not in allowed:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {', '.join(allowed)}")
    ok = update_order_status(order_id, status)
    if not ok:
        raise HTTPException(status_code=404, detail="Order not found.")
    return {"ok": True, "order_id": order_id, "status": status}


@app.get("/api/orders")
async def api_list_orders(
    merchant: Optional[str] = Query(""),
    limit: int = Query(50, ge=1, le=200),
):
    """List recent orders."""
    return {"orders": get_recent_orders(merchant=merchant or "", limit=limit)}


@app.get("/api/analytics")
async def api_analytics(
    merchant: Optional[str] = Query(""),
    period: str = Query("all", description="today|7d|30d|all"),
):
    """Full merchant analytics — revenue, profit, orders, trends, top products."""
    allowed_periods = {"today", "7d", "30d", "all"}
    if period not in allowed_periods:
        period = "all"
    return get_merchant_analytics(merchant=merchant or "", period=period)


# ── WooCommerce webhook setup endpoint ──────────────────────────────────────

@app.get("/api/woocommerce/setup")
async def wc_setup(email: str = Query(...), token: str = Query(...), request: Request = None):
    """Return WooCommerce webhook URL and secret for this merchant."""
    email = email.strip().lower()
    if not _verify_session_token(email, token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    secret = get_wc_webhook_secret(email)
    webhook_url = f"{MERCHANT_URL}/webhook/woocommerce?merchant={email}"
    return {
        "webhook_url": webhook_url,
        "webhook_secret": secret,
        "instructions": (
            "In WooCommerce: WooCommerce → Settings → Advanced → Webhooks → Add webhook. "
            "Topic: Order updated. Delivery URL: the webhook_url above. "
            "Secret: the webhook_secret above."
        ),
    }


# ── Telegram bot endpoints ───────────────────────────────────────────────────

class TelegramTokenRequest(BaseModel):
    token: str = ""
    email: str

    @field_validator("token")
    @classmethod
    def token_clean(cls, v):
        return (v or "").strip()


@app.post("/api/telegram/start")
async def telegram_start(req: TelegramTokenRequest, request: Request):
    ip = _client_ip(request)
    if not _check_rate(ip, max_requests=20, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many requests.")

    email = req.email.strip().lower()
    merchant = get_merchant(email)
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found. Please sign in first.")

    if not req.token:
        raise HTTPException(status_code=400, detail="Bot token is required to start.")

    if tg_is_running(email):
        return {"status": "already_running", "message": "Telegram bot is already running for your account."}

    ok = start_bot(req.token, merchant_email=email)
    if ok:
        logger.info("Telegram bot started by merchant=%s", email)
        return {"status": "started", "message": "Telegram bot is now running."}
    else:
        raise HTTPException(status_code=500, detail="Failed to start Telegram bot. Check the token.")


@app.post("/api/telegram/stop")
async def telegram_stop(req: TelegramTokenRequest, request: Request):
    ip = _client_ip(request)
    if not _check_rate(ip, max_requests=20, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many requests.")

    email = req.email.strip().lower()
    if not tg_is_running(email):
        return {"status": "not_running", "message": "Telegram bot is not running for your account."}

    stop_bot(email)
    return {"status": "stopped", "message": "Telegram bot stopped."}


@app.get("/api/telegram/status")
async def telegram_status(email: str = Query("_default")):
    email = email.strip().lower() if email != "_default" else "_default"
    return {"running": tg_is_running(email), "active_bots": len(get_running_bots())}


# ── Merchant demo (served at /demo/) ─────────────────────────────────────────
demo_dir = os.path.join(os.path.dirname(__file__), "merchant_demo")
if os.path.isdir(demo_dir):
    app.mount("/demo", StaticFiles(directory=demo_dir, html=True), name="merchant_demo")

# ── Static files (must be last) ───────────────────────────────────────────────
if os.path.isdir(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
