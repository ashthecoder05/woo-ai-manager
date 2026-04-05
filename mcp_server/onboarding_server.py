"""
Onboarding MCP Server — Bitcoin Payment Gateway Setup Guides

Covers: Blockonomics, Coinbase Commerce, BitPay, Stripe (Bridge), NOWPayments, CoinGate
Integration types: plugin, api, custom

For Python 3.10+ run as MCP:
  python mcp_server/onboarding_server.py

For Python 3.8 compatibility this is wired as a regular tool in agent/tools.py
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Onboarding knowledge base
# ---------------------------------------------------------------------------

GUIDES: dict[str, dict[str, dict]] = {
    "blockonomics": {
        "plugin": {
            "label": "Blockonomics — Plugin",
            "platforms": ["WooCommerce", "PrestaShop", "WHMCS", "Invoice Ninja"],
            "steps": [
                "Create a Blockonomics account at blockonomics.co",
                "Add a Bitcoin wallet in Dashboard → Wallets (you need your xpub key)",
                "In WordPress admin: Plugins → Add New → search 'Blockonomics Bitcoin' → Install & Activate",
                "Go to WooCommerce → Settings → Payments → Blockonomics",
                "Paste your API Key from Blockonomics Dashboard → Stores",
                "Copy the Callback URL shown in the plugin and paste it into your Blockonomics store settings",
                "Click 'Test Setup' — all green checkmarks = ready",
            ],
            "requirements": ["WordPress 5.0+", "WooCommerce 4.0+", "PHP 7.4+", "SSL (HTTPS)", "xpub key from your Bitcoin wallet"],
            "webhook_format": "GET /?wc-api=WC_Blockonomics&secret=SECRET&addr=ADDR&value=VALUE&txid=TXID&status=STATUS",
            "status_codes": {"0": "unconfirmed", "1": "partial", "2": "confirmed"},
            "common_issues": [
                "Test Setup failed → API key wrong or xpub not added in Blockonomics dashboard",
                "Orders not updating → web host blocking Blockonomics IPs, ask host to whitelist them",
                "Gap limit error → increase gap limit to 100 in Blockonomics dashboard",
            ],
            "docs_url": "https://www.blockonomics.co/views/bitcoin_woocommerce.html",
        },
        "api": {
            "label": "Blockonomics — Direct API",
            "platforms": ["Any backend"],
            "steps": [
                "Get your API Key from Blockonomics Dashboard → Stores",
                "Store it in your environment: BLOCKONOMICS_API_KEY=...",
                "Call POST /api/new_address to generate a fresh Bitcoin address per order",
                "Call GET /api/price?currency=USD to get current BTC price and convert order amount",
                "Display the address + BTC amount + QR code to the customer",
                "Receive GET webhook at your callback URL with params: addr, value, txid, status",
                "Fulfill the order when status >= 2 (confirmed)",
            ],
            "requirements": ["HTTPS endpoint for webhooks", "Blockonomics API key", "xpub wallet registered in dashboard"],
            "code_snippet": """\
import httpx, os

API_KEY = os.getenv("BLOCKONOMICS_API_KEY")
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

def new_btc_address():
    r = httpx.post("https://www.blockonomics.co/api/new_address",
                   headers=HEADERS, json={"reset": 0})
    return r.json()["address"]

def get_btc_price_usd():
    r = httpx.get("https://www.blockonomics.co/api/price?currency=USD")
    return r.json()["price"]

# Webhook handler (FastAPI)
from fastapi import APIRouter, Query
router = APIRouter()

@router.get("/webhook/blockonomics")
def webhook(secret: str = Query(...), addr: str = Query(...),
            value: int = Query(...), txid: str = Query(...), status: int = Query(...)):
    if status >= 2:
        pass  # fulfill_order(addr, value)
    return {"ok": True}
""",
            "docs_url": "https://www.blockonomics.co/api",
        },
        "custom": {
            "label": "Blockonomics — Custom Integration",
            "platforms": ["React", "Vue", "Mobile", "Any framework"],
            "steps": [
                "Use the Direct API to generate addresses and get BTC price",
                "Build your own payment UI: show address, BTC amount, QR code, countdown timer",
                "Set up a webhook receiver endpoint on your server",
                "Register the webhook URL in Blockonomics Dashboard → Stores → Callback URL",
                "On confirmation (status=2) trigger your fulfillment logic",
                "Optionally use mempool.space API to show real-time confirmation progress",
            ],
            "requirements": ["HTTPS server", "Blockonomics API key", "QR code library (e.g. qrcode.js)"],
            "common_issues": [
                "Address reuse → always call /api/new_address per order, never reuse",
                "Underpayment → add 1% buffer or use detect_underpayment tool",
            ],
            "docs_url": "https://www.blockonomics.co/api",
        },
    },

    "coinbase": {
        "plugin": {
            "label": "Coinbase Commerce — Plugin",
            "platforms": ["WooCommerce", "Shopify", "PrestaShop", "Magento"],
            "steps": [
                "Sign up at commerce.coinbase.com and create a store",
                "Go to Settings → API keys → Create an API key",
                "Note your Webhook Shared Secret from the same page",
                "In WordPress: Plugins → Add New → search 'Coinbase Commerce' → Install & Activate",
                "Go to WooCommerce → Settings → Payments → Coinbase Commerce",
                "Enter your API Key and Webhook Shared Secret",
                "Set the Webhook URL in Coinbase Commerce dashboard to: https://yoursite.com/?wc-api=wc_coinbase",
                "Save and place a test order",
            ],
            "requirements": ["WordPress + WooCommerce OR Shopify/PrestaShop", "SSL (HTTPS)", "Coinbase Commerce account"],
            "webhook_format": "POST /webhook — JSON body with charge object, verified via X-CC-Webhook-Signature header",
            "status_codes": {"NEW": "created", "PENDING": "payment detected", "CONFIRMED": "confirmed", "FAILED": "failed"},
            "common_issues": [
                "Signature mismatch → ensure Webhook Shared Secret is copied exactly (no trailing spaces)",
                "Order not updating → webhook URL must be publicly accessible (not localhost)",
                "Multi-currency → Coinbase auto-converts, no xpub needed",
            ],
            "docs_url": "https://docs.cloud.coinbase.com/commerce/docs/getting-started",
        },
        "api": {
            "label": "Coinbase Commerce — REST API",
            "platforms": ["Any backend"],
            "steps": [
                "Get API Key from commerce.coinbase.com → Settings → API keys",
                "Install the SDK: pip install coinbase-commerce (Python) or npm install coinbase-commerce (Node)",
                "Create a Charge object with name, description, pricing_type, local_price",
                "Redirect the customer to charge.hosted_url for payment",
                "Receive POST webhook and verify signature using your Webhook Shared Secret",
                "Check event.type == 'charge:confirmed' to fulfill the order",
            ],
            "requirements": ["Coinbase Commerce API key", "HTTPS webhook endpoint"],
            "code_snippet": """\
import hmac, hashlib, requests, os

API_KEY = os.getenv("COINBASE_COMMERCE_API_KEY")
WEBHOOK_SECRET = os.getenv("COINBASE_WEBHOOK_SECRET")

def create_charge(amount_usd: float, order_id: str) -> str:
    resp = requests.post(
        "https://api.commerce.coinbase.com/charges",
        headers={"X-CC-Api-Key": API_KEY, "X-CC-Version": "2018-03-22"},
        json={
            "name": f"Order {order_id}",
            "pricing_type": "fixed_price",
            "local_price": {"amount": str(amount_usd), "currency": "USD"},
            "metadata": {"order_id": order_id},
        },
    )
    return resp.json()["data"]["hosted_url"]

def verify_webhook(payload: bytes, sig_header: str) -> bool:
    computed = hmac.new(WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, sig_header)
""",
            "docs_url": "https://docs.cloud.coinbase.com/commerce/reference",
        },
        "custom": {
            "label": "Coinbase Commerce — Custom UI",
            "platforms": ["Any frontend/backend"],
            "steps": [
                "Create a Charge via REST API and get the charge code",
                "Use Coinbase Commerce JS SDK to embed the payment modal: npm install @coinbase/commerce-js",
                "Or build your own UI using the charge's addresses object (multi-coin addresses returned)",
                "Poll GET /charges/{code} or use webhooks to detect payment confirmation",
                "Handle charge:confirmed event to trigger fulfillment",
            ],
            "requirements": ["Coinbase Commerce API key", "HTTPS for webhooks"],
            "docs_url": "https://docs.cloud.coinbase.com/commerce/docs/custom-integration",
        },
    },

    "bitpay": {
        "plugin": {
            "label": "BitPay — Plugin",
            "platforms": ["WooCommerce", "Magento", "PrestaShop", "Shopify", "BigCommerce"],
            "steps": [
                "Create a BitPay Business account at bitpay.com",
                "Go to Payment Tools → Merchant → Generate API Token (set facade to 'merchant')",
                "In WordPress: Plugins → Add New → search 'BitPay for WooCommerce' → Install & Activate",
                "Go to WooCommerce → Settings → Payments → BitPay",
                "Click 'Connect to BitPay' and enter your API Token",
                "Set transaction speed: 'High' (unconfirmed) or 'Medium' (1 conf) or 'Low' (6 conf)",
                "Save settings and place a test order using BitPay's test environment",
            ],
            "requirements": ["WooCommerce 3.0+", "PHP 7.1+", "SSL (HTTPS)", "BitPay Business account"],
            "webhook_format": "POST IPN — JSON body with invoice object, verified via BitPay signature",
            "status_codes": {"new": "created", "paid": "payment detected", "confirmed": "confirmed", "complete": "settled"},
            "common_issues": [
                "Invalid token → re-generate token with 'merchant' facade, not 'pos'",
                "Invoice expired → BitPay invoices expire in 15 minutes, ensure customer pays promptly",
                "Test vs live → switch environment in plugin settings (test.bitpay.com vs bitpay.com)",
            ],
            "docs_url": "https://bitpay.com/docs/woocommerce",
        },
        "api": {
            "label": "BitPay — REST API",
            "platforms": ["Any backend"],
            "steps": [
                "Generate a keypair and API token at bitpay.com → Payment Tools → API Token",
                "Install SDK: pip install bitpay (Python) or npm install bitpay (Node)",
                "Create an Invoice with price, currency, orderId, notificationURL",
                "Redirect customer to invoice.url for payment",
                "Receive POST IPN to notificationURL and verify using BitPay's public key",
                "Fulfill order when invoice status == 'confirmed' or 'complete'",
            ],
            "requirements": ["BitPay API token (merchant facade)", "HTTPS IPN endpoint"],
            "code_snippet": """\
import requests, os

API_TOKEN = os.getenv("BITPAY_API_TOKEN")
BASE = "https://bitpay.com"  # use https://test.bitpay.com for testing

def create_invoice(amount_usd: float, order_id: str, notify_url: str) -> str:
    resp = requests.post(
        f"{BASE}/invoices",
        headers={"Authorization": f"Token {API_TOKEN}", "Content-Type": "application/json"},
        json={
            "price": amount_usd,
            "currency": "USD",
            "orderId": order_id,
            "notificationURL": notify_url,
            "transactionSpeed": "medium",
        },
    )
    data = resp.json()["data"]
    return data["url"]  # redirect customer here
""",
            "docs_url": "https://bitpay.com/docs/api",
        },
        "custom": {
            "label": "BitPay — Custom Integration",
            "platforms": ["Any frontend/backend"],
            "steps": [
                "Create an Invoice via API and get the invoice ID and payment addresses",
                "Use BitPay's embeddable payment modal: include bitpay.js and call window.bitpay.showInvoice(invoiceId)",
                "Or build your own UI using invoice.addresses for BTC/ETH/etc.",
                "Listen for IPN POST callbacks — verify X-BitPay-Signature header",
                "On status='confirmed', fulfill the order",
            ],
            "requirements": ["BitPay API token", "HTTPS webhook", "bitpay.js (optional for modal)"],
            "docs_url": "https://bitpay.com/docs/custom-integration",
        },
    },

    "stripe": {
        "plugin": {
            "label": "Stripe (Bridge/Crypto) — Plugin",
            "platforms": ["WooCommerce", "Shopify", "Squarespace"],
            "steps": [
                "Create a Stripe account at stripe.com and enable crypto payments via Stripe Bridge",
                "Go to Stripe Dashboard → Developers → API keys → copy Publishable and Secret keys",
                "In WordPress: Plugins → Add New → search 'WooCommerce Stripe Payment Gateway' → Install & Activate",
                "Go to WooCommerce → Settings → Payments → Stripe → Enable and configure",
                "Enter your Stripe Publishable Key and Secret Key",
                "Enable 'Crypto' under payment methods (requires Stripe Bridge activation)",
                "Set the Webhook endpoint URL in Stripe Dashboard → Developers → Webhooks",
                "Copy the Webhook Signing Secret and paste into plugin settings",
            ],
            "requirements": ["WooCommerce 3.0+", "PHP 7.2+", "SSL (HTTPS)", "Stripe account with Bridge enabled"],
            "webhook_format": "POST — JSON with event object, verified via Stripe-Signature header using signing secret",
            "status_codes": {"payment_intent.created": "pending", "payment_intent.succeeded": "confirmed", "payment_intent.payment_failed": "failed"},
            "common_issues": [
                "Crypto not showing → Bridge must be explicitly enabled in Stripe Dashboard → Settings → Payment methods",
                "Webhook failing → use Stripe CLI for local testing: stripe listen --forward-to localhost:8000/webhook",
                "Test mode → use test keys (sk_test_...) and Stripe test card numbers",
            ],
            "docs_url": "https://docs.stripe.com/payments/crypto",
        },
        "api": {
            "label": "Stripe (Bridge) — REST API",
            "platforms": ["Any backend"],
            "steps": [
                "Get your Secret Key from Stripe Dashboard → Developers → API keys",
                "Install SDK: pip install stripe (Python) or npm install stripe (Node)",
                "Create a PaymentIntent or Checkout Session with crypto as a payment method",
                "Redirect customer to session.url (Checkout) or handle client-side with Stripe.js",
                "Listen for webhook events: payment_intent.succeeded to fulfill the order",
                "Verify webhook signature using Stripe-Signature header and your signing secret",
            ],
            "requirements": ["Stripe secret key", "HTTPS webhook endpoint", "Stripe Bridge enabled"],
            "code_snippet": """\
import stripe, os

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

def create_checkout_session(amount_usd: float, order_id: str, success_url: str) -> str:
    session = stripe.checkout.Session.create(
        payment_method_types=["crypto"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": f"Order {order_id}"},
                "unit_amount": int(amount_usd * 100),
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=success_url,
        metadata={"order_id": order_id},
    )
    return session.url

def verify_webhook(payload: bytes, sig_header: str) -> stripe.Event:
    return stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
""",
            "docs_url": "https://docs.stripe.com/api",
        },
        "custom": {
            "label": "Stripe (Bridge) — Custom UI",
            "platforms": ["Any frontend"],
            "steps": [
                "Create a PaymentIntent via API and get the client_secret",
                "Load Stripe.js: <script src='https://js.stripe.com/v3/'></script>",
                "Initialize: const stripe = Stripe('pk_live_...')",
                "Mount the Stripe Payment Element to your form: elements.create('payment')",
                "On form submit: stripe.confirmPayment({ elements, confirmParams })",
                "Handle webhook event payment_intent.succeeded server-side to fulfill",
            ],
            "requirements": ["Stripe publishable key (frontend)", "Stripe secret key (backend)", "Stripe.js"],
            "docs_url": "https://docs.stripe.com/payments/payment-element",
        },
    },

    "nowpayments": {
        "plugin": {
            "label": "NOWPayments — Plugin",
            "platforms": ["WooCommerce", "PrestaShop", "OpenCart", "WHMCS", "Magento"],
            "steps": [
                "Sign up at nowpayments.io and complete merchant verification",
                "Go to Account → Store Settings → API Keys → Generate API Key",
                "Note your IPN Secret Key from the same page",
                "In WordPress: Plugins → Add New → search 'NOWPayments for WooCommerce' → Install & Activate",
                "Go to WooCommerce → Settings → Payments → NOWPayments",
                "Enter your API Key and IPN Secret Key",
                "Select accepted cryptocurrencies (BTC, ETH, USDT, 300+ supported)",
                "Set payment confirmation threshold (1–6 confirmations)",
                "Save settings and test with a small order",
            ],
            "requirements": ["WooCommerce 4.0+", "PHP 7.2+", "SSL (HTTPS)", "NOWPayments merchant account"],
            "webhook_format": "POST IPN — JSON with payment object, verified via x-nowpayments-sig header (HMAC-SHA512)",
            "status_codes": {"waiting": "waiting for payment", "confirming": "detecting payment", "confirmed": "confirmed", "finished": "settled", "failed": "failed"},
            "common_issues": [
                "IPN not received → ensure IPN callback URL is set in NOWPayments dashboard → Store Settings",
                "Signature invalid → IPN Secret Key must match, check for extra whitespace",
                "Currency not shown → enable specific currencies in NOWPayments dashboard → Currencies",
            ],
            "docs_url": "https://documenter.getpostman.com/view/7907941/2s93JqTRWN",
        },
        "api": {
            "label": "NOWPayments — REST API",
            "platforms": ["Any backend"],
            "steps": [
                "Get your API Key from nowpayments.io → Account → Store Settings",
                "Create a payment by calling POST /v1/payment with pay_currency, price_amount, price_currency, order_id",
                "Redirect customer to payment.payment_url or show payment.pay_address + pay_amount",
                "Set ipn_callback_url in the payment creation request",
                "Receive POST IPN and verify signature: HMAC-SHA512 of sorted JSON body using IPN Secret",
                "Fulfill order when payment_status == 'confirmed' or 'finished'",
            ],
            "requirements": ["NOWPayments API key", "HTTPS IPN endpoint"],
            "code_snippet": """\
import hmac, hashlib, json, requests, os

API_KEY = os.getenv("NOWPAYMENTS_API_KEY")
IPN_SECRET = os.getenv("NOWPAYMENTS_IPN_SECRET")

def create_payment(amount_usd: float, order_id: str, callback_url: str) -> dict:
    resp = requests.post(
        "https://api.nowpayments.io/v1/payment",
        headers={"x-api-key": API_KEY, "Content-Type": "application/json"},
        json={
            "price_amount": amount_usd,
            "price_currency": "usd",
            "pay_currency": "btc",
            "order_id": order_id,
            "ipn_callback_url": callback_url,
        },
    )
    return resp.json()  # contains pay_address, pay_amount, payment_url

def verify_ipn(payload: bytes, sig_header: str) -> bool:
    data = json.loads(payload)
    sorted_data = json.dumps(dict(sorted(data.items())), separators=(',', ':'))
    computed = hmac.new(IPN_SECRET.encode(), sorted_data.encode(), hashlib.sha512).hexdigest()
    return hmac.compare_digest(computed, sig_header)
""",
            "docs_url": "https://documenter.getpostman.com/view/7907941/2s93JqTRWN",
        },
        "custom": {
            "label": "NOWPayments — Custom Integration",
            "platforms": ["Any frontend/backend"],
            "steps": [
                "Create a payment via API and get pay_address and pay_amount",
                "Build custom payment UI: show QR code, countdown timer, copy address button",
                "Poll GET /v1/payment/{payment_id} every 30s to check payment_status",
                "Or use IPN webhooks for real-time updates (more reliable)",
                "Support multiple coins: let customers choose pay_currency from GET /v1/currencies",
                "Handle underpayments: NOWPayments supports partial payment detection",
            ],
            "requirements": ["NOWPayments API key", "HTTPS for IPN callbacks"],
            "docs_url": "https://nowpayments.io/payment-tools/api-payment",
        },
    },

    "coingate": {
        "plugin": {
            "label": "CoinGate — Plugin",
            "platforms": ["WooCommerce", "PrestaShop", "Magento", "OpenCart", "WHMCS"],
            "steps": [
                "Create a CoinGate merchant account at coingate.com",
                "Go to Account → API → Apps → Create New App → select 'order' permissions",
                "Copy the Auth Token generated",
                "In WordPress: Plugins → Add New → search 'CoinGate for WooCommerce' → Install & Activate",
                "Go to WooCommerce → Settings → Payments → CoinGate",
                "Enter your Auth Token",
                "Select receive currency (EUR, USD, BTC, USDT, etc.)",
                "Set Callback URL in CoinGate dashboard to: https://yoursite.com/?wc-api=wc_coingate",
                "Test with CoinGate sandbox environment (use sandbox auth token from sandbox.coingate.com)",
            ],
            "requirements": ["WooCommerce 3.0+", "PHP 7.0+", "SSL (HTTPS)", "CoinGate merchant account"],
            "webhook_format": "POST callback — form-encoded or JSON with order object",
            "status_codes": {"pending": "waiting", "confirming": "detecting", "paid": "confirmed", "invalid": "failed", "expired": "expired"},
            "common_issues": [
                "Sandbox vs live → use sandbox.coingate.com token for testing, coingate.com token for live",
                "Callback not received → verify callback URL is public and matches exactly in CoinGate dashboard",
                "Currency not settled → configure receive currency in CoinGate → Account → Settlement",
            ],
            "docs_url": "https://developer.coingate.com/docs/woocommerce-plugin",
        },
        "api": {
            "label": "CoinGate — REST API",
            "platforms": ["Any backend"],
            "steps": [
                "Get Auth Token from coingate.com → Account → API → Apps",
                "Create an order: POST /v2/orders with price_amount, price_currency, receive_currency, callback_url",
                "Redirect customer to order.payment_url",
                "Receive POST callback at callback_url and check order status",
                "Verify callback authenticity by calling GET /v2/orders/{id} and comparing status",
                "Fulfill order when status == 'paid'",
            ],
            "requirements": ["CoinGate auth token", "HTTPS callback endpoint"],
            "code_snippet": """\
import requests, os

AUTH_TOKEN = os.getenv("COINGATE_AUTH_TOKEN")
BASE = "https://api.coingate.com"  # use https://api-sandbox.coingate.com for testing

def create_order(amount_usd: float, order_id: str, callback_url: str, success_url: str) -> str:
    resp = requests.post(
        f"{BASE}/v2/orders",
        headers={"Authorization": f"Token {AUTH_TOKEN}"},
        json={
            "order_id": order_id,
            "price_amount": amount_usd,
            "price_currency": "USD",
            "receive_currency": "USDT",
            "callback_url": callback_url,
            "success_url": success_url,
            "cancel_url": success_url,
        },
    )
    return resp.json()["payment_url"]

def get_order_status(coingate_order_id: int) -> str:
    resp = requests.get(
        f"{BASE}/v2/orders/{coingate_order_id}",
        headers={"Authorization": f"Token {AUTH_TOKEN}"},
    )
    return resp.json()["status"]
""",
            "docs_url": "https://developer.coingate.com/reference",
        },
        "custom": {
            "label": "CoinGate — Custom Integration",
            "platforms": ["Any frontend/backend"],
            "steps": [
                "Create an order via API and get the payment_url and token",
                "Build custom checkout: redirect to payment_url or embed via iframe",
                "Or use the payment addresses from the order object to build a native UI",
                "Set up a callback endpoint to receive POST with order status",
                "Verify by calling GET /v2/orders/{id} (don't trust callback body alone)",
                "Supports 70+ cryptocurrencies — let customer choose pay_currency",
            ],
            "requirements": ["CoinGate auth token", "HTTPS for callbacks"],
            "docs_url": "https://developer.coingate.com/docs",
        },
    },
}


# ---------------------------------------------------------------------------
# Public API used by agent/tools.py
# ---------------------------------------------------------------------------

SUPPORTED_GATEWAYS = list(GUIDES.keys())
SUPPORTED_INTEGRATION_TYPES = ["plugin", "api", "custom"]


def get_onboarding_guide(gateway: str, integration_type: str) -> str:
    """
    Return a structured onboarding guide for a given gateway and integration type.
    gateway: blockonomics | coinbase | bitpay | stripe | nowpayments | coingate
    integration_type: plugin | api | custom
    """
    gateway = gateway.lower().strip()
    integration_type = integration_type.lower().strip()

    if gateway not in GUIDES:
        available = ", ".join(SUPPORTED_GATEWAYS)
        return f"Unknown gateway '{gateway}'. Supported: {available}"

    if integration_type not in GUIDES[gateway]:
        available = ", ".join(GUIDES[gateway].keys())
        return f"Unknown integration type '{integration_type}' for {gateway}. Supported: {available}"

    guide = GUIDES[gateway][integration_type]
    lines = [f"## {guide['label']}\n"]

    if guide.get("platforms"):
        lines.append(f"**Works with:** {', '.join(guide['platforms'])}\n")

    if guide.get("requirements"):
        lines.append("**Requirements:**")
        for r in guide["requirements"]:
            lines.append(f"  - {r}")
        lines.append("")

    lines.append("**Setup Steps:**")
    for i, step in enumerate(guide["steps"], 1):
        lines.append(f"  {i}. {step}")
    lines.append("")

    if guide.get("webhook_format"):
        lines.append(f"**Webhook format:** `{guide['webhook_format']}`\n")

    if guide.get("status_codes"):
        lines.append("**Status codes:**")
        for code, meaning in guide["status_codes"].items():
            lines.append(f"  - `{code}` → {meaning}")
        lines.append("")

    if guide.get("code_snippet"):
        lines.append("**Code snippet:**")
        lines.append("```python")
        lines.append(guide["code_snippet"].strip())
        lines.append("```\n")

    if guide.get("common_issues"):
        lines.append("**Common issues:**")
        for issue in guide["common_issues"]:
            lines.append(f"  - {issue}")
        lines.append("")

    if guide.get("docs_url"):
        lines.append(f"**Official docs:** {guide['docs_url']}")

    return "\n".join(lines)


def list_supported_gateways() -> str:
    """Return a formatted list of all supported gateways and integration types."""
    lines = ["**Supported Bitcoin payment gateways:**\n"]
    for gateway, integrations in GUIDES.items():
        types = ", ".join(integrations.keys())
        lines.append(f"  - **{gateway.capitalize()}** — {types}")
    return "\n".join(lines)


def compare_gateways(integration_type: str = "plugin") -> str:
    """Compare all gateways for a given integration type."""
    integration_type = integration_type.lower().strip()
    lines = [f"## Gateway Comparison — {integration_type.title()} Integration\n"]
    lines.append(f"{'Gateway':<16} {'Platforms':<40} {'Docs'}")
    lines.append("-" * 80)
    for gateway, integrations in GUIDES.items():
        if integration_type in integrations:
            g = integrations[integration_type]
            platforms = ", ".join(g.get("platforms", [])[:3])
            docs = g.get("docs_url", "")
            lines.append(f"{gateway.capitalize():<16} {platforms:<40} {docs}")
    return "\n".join(lines)


# ── MCP server entry point (Python 3.10+ only) ──────────────────────────────
# Uncomment when mcp package is available:
#
# from mcp.server.fastmcp import FastMCP
# mcp = FastMCP("bitcoin-gateway-onboarding")
#
# @mcp.tool()
# def gateway_onboarding_guide(gateway: str, integration_type: str) -> str:
#     """
#     Get a step-by-step onboarding guide for a Bitcoin payment gateway.
#     gateway: blockonomics | coinbase | bitpay | stripe | nowpayments | coingate
#     integration_type: plugin | api | custom
#     """
#     return get_onboarding_guide(gateway, integration_type)
#
# @mcp.tool()
# def list_gateways() -> str:
#     """List all supported Bitcoin payment gateways and integration types."""
#     return list_supported_gateways()
#
# @mcp.tool()
# def compare_payment_gateways(integration_type: str = "plugin") -> str:
#     """Compare all supported gateways for a given integration type (plugin/api/custom)."""
#     return compare_gateways(integration_type)
#
# if __name__ == "__main__":
#     mcp.run()
