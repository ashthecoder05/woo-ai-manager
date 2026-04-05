"""
UCP (Universal Commerce Protocol) Manifest MCP Server

Generates and validates /.well-known/ucp JSON-LD manifests for all 6
Bitcoin payment gateways so AI shopping agents can discover and pay
a merchant automatically.

Covers: Blockonomics, Coinbase Commerce, BitPay, Stripe (Bridge),
        NOWPayments, CoinGate

For Python 3.10+ run as MCP:
  python mcp_server/ucp_server.py

For Python 3.8 compatibility this is wired as a regular tool in agent/tools.py
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Gateway-specific UCP profile definitions
# Each profile describes how an AI agent should interact with that gateway
# ---------------------------------------------------------------------------

GATEWAY_PROFILES: dict[str, dict] = {
    "blockonomics": {
        "label":       "Blockonomics",
        "currency":    "BTC",
        "protocol":    "bitcoin-onchain",
        "capabilities": [
            "bitcoin-payment",
            "address-generation",
            "webhook-notification",
            "underpayment-detection",
            "transaction-lookup",
        ],
        "address_endpoint_path":  "/api/btc/new-address",
        "webhook_path":           "/webhook/blockonomics",
        "payment_method_type":    "BitcoinPayment",
        "confirmations_default":  2,
        "agent_instructions": (
            "To initiate payment: POST to {address_endpoint} to receive a fresh Bitcoin address. "
            "Convert the order amount to BTC using the current price from "
            "https://www.blockonomics.co/api/price?currency=USD. "
            "Send the exact BTC amount to the address. "
            "Poll GET {webhook_endpoint} or wait for webhook callback. "
            "Payment is confirmed after {confirmations} block confirmation(s). "
            "Status codes: 0=unconfirmed, 1=partial, 2=confirmed."
        ),
        "docs_url": "https://www.blockonomics.co/api",
    },
    "coinbase": {
        "label":       "Coinbase Commerce",
        "currency":    "BTC,ETH,USDC,LTC,BCH",
        "protocol":    "coinbase-commerce",
        "capabilities": [
            "multi-currency-payment",
            "hosted-checkout",
            "webhook-notification",
            "charge-expiry-handling",
            "automatic-currency-conversion",
        ],
        "address_endpoint_path":  "/api/coinbase/create-charge",
        "webhook_path":           "/webhook/coinbase",
        "payment_method_type":    "CoinbaseCommercePayment",
        "confirmations_default":  3,
        "agent_instructions": (
            "To initiate payment: POST to {address_endpoint} with "
            "{{name, pricing_type: 'fixed_price', local_price: {{amount, currency: 'USD'}}}}. "
            "Redirect the buyer to the returned hosted_url for multi-currency crypto checkout. "
            "Coinbase Commerce handles currency selection and conversion automatically. "
            "Listen for webhook event type 'charge:confirmed' at {webhook_endpoint}. "
            "Verify webhook using HMAC-SHA256 signature in X-CC-Webhook-Signature header. "
            "Charges expire after 60 minutes — create a fresh charge if expired."
        ),
        "docs_url": "https://docs.cloud.coinbase.com/commerce/reference",
    },
    "bitpay": {
        "label":       "BitPay",
        "currency":    "BTC,ETH,XRP,DOGE,LTC,USDC",
        "protocol":    "bitpay-invoice",
        "capabilities": [
            "multi-currency-payment",
            "invoice-based-checkout",
            "ipn-notification",
            "lightning-network",
            "refund-support",
        ],
        "address_endpoint_path":  "/api/bitpay/create-invoice",
        "webhook_path":           "/webhook/bitpay",
        "payment_method_type":    "BitPayInvoicePayment",
        "confirmations_default":  2,
        "agent_instructions": (
            "To initiate payment: POST to {address_endpoint} with "
            "{{price, currency: 'USD', orderId, notificationURL: '{webhook_endpoint}'}}. "
            "Redirect buyer to the returned invoice URL. "
            "BitPay handles coin selection. Invoices expire in 15 minutes. "
            "Listen for IPN POST callbacks at {webhook_endpoint}. "
            "Fulfill order when invoice status is 'confirmed' or 'complete'. "
            "Use 'medium' transaction speed for standard orders (1 confirmation)."
        ),
        "docs_url": "https://bitpay.com/docs/api",
    },
    "stripe": {
        "label":       "Stripe (Bridge / Crypto)",
        "currency":    "USDC,ETH",
        "protocol":    "stripe-crypto",
        "capabilities": [
            "crypto-payment",
            "fiat-settlement",
            "stripe-elements-integration",
            "webhook-notification",
            "automatic-fiat-conversion",
        ],
        "address_endpoint_path":  "/api/stripe/create-session",
        "webhook_path":           "/webhook/stripe",
        "payment_method_type":    "StripeCryptoPayment",
        "confirmations_default":  1,
        "agent_instructions": (
            "To initiate payment: POST to {address_endpoint} with "
            "{{amount_usd, order_id, success_url}}. "
            "Redirect buyer to the returned Stripe Checkout session URL. "
            "Stripe Bridge handles crypto-to-fiat conversion automatically. "
            "Listen for webhook event 'payment_intent.succeeded' at {webhook_endpoint}. "
            "Verify using Stripe-Signature header with endpoint signing secret. "
            "Supported payment method: 'crypto' (requires Stripe Bridge activation)."
        ),
        "docs_url": "https://stripe.com/docs/payments/crypto",
    },
    "nowpayments": {
        "label":       "NOWPayments",
        "currency":    "BTC,ETH,USDT,LTC,XRP,300+",
        "protocol":    "nowpayments-api",
        "capabilities": [
            "300-plus-currencies",
            "auto-conversion",
            "ipn-notification",
            "underpayment-handling",
            "fixed-rate-payment",
            "sub-partner-support",
        ],
        "address_endpoint_path":  "/api/nowpayments/create-payment",
        "webhook_path":           "/webhook/nowpayments",
        "payment_method_type":    "NOWPaymentsPayment",
        "confirmations_default":  2,
        "agent_instructions": (
            "To initiate payment: POST to {address_endpoint} with "
            "{{price_amount, price_currency: 'USD', pay_currency: 'BTC', "
            "order_id, ipn_callback_url: '{webhook_endpoint}'}}. "
            "Display returned pay_address and pay_amount to buyer. "
            "Buyer selects cryptocurrency; NOWPayments auto-converts. "
            "Listen for IPN POST at {webhook_endpoint}. "
            "Verify using HMAC-SHA512 of sorted JSON body vs x-nowpayments-sig header. "
            "Fulfill when payment_status is 'confirmed' or 'finished'."
        ),
        "docs_url": "https://documenter.getpostman.com/view/7907941/2s93JqTRWN",
    },
    "coingate": {
        "label":       "CoinGate",
        "currency":    "BTC,ETH,USDT,LTC,70+",
        "protocol":    "coingate-order",
        "capabilities": [
            "70-plus-currencies",
            "fiat-settlement",
            "callback-notification",
            "refund-api",
            "sandbox-environment",
            "sepa-settlement",
        ],
        "address_endpoint_path":  "/api/coingate/create-order",
        "webhook_path":           "/webhook/coingate",
        "payment_method_type":    "CoinGateOrderPayment",
        "confirmations_default":  2,
        "agent_instructions": (
            "To initiate payment: POST to {address_endpoint} with "
            "{{order_id, price_amount, price_currency: 'USD', "
            "receive_currency: 'USDT', callback_url: '{webhook_endpoint}', "
            "success_url, cancel_url}}. "
            "Redirect buyer to returned payment_url. "
            "CoinGate handles coin selection and settlement. "
            "Receive POST callback at {webhook_endpoint} when order status changes. "
            "Always verify by calling GET /v2/orders/{{id}} server-side. "
            "Fulfill when status is 'paid'."
        ),
        "docs_url": "https://developer.coingate.com/reference",
    },
}


# ---------------------------------------------------------------------------
# Validators (reused from services/ucp.py pattern)
# ---------------------------------------------------------------------------

class ValidationError:
    def __init__(self, field: str, message: str, severity: str = "error"):
        self.field = field
        self.message = message
        self.severity = severity

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.field}: {self.message}"


def _validate_url(url: str, field: str) -> list[ValidationError]:
    errors = []
    if not url:
        errors.append(ValidationError(field, "URL is required"))
        return errors
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        errors.append(ValidationError(field, f"Must use http/https, got '{p.scheme}'"))
    if not p.netloc:
        errors.append(ValidationError(field, "Must include a valid domain"))
    return errors


def _validate_manifest(manifest: dict) -> list[ValidationError]:
    errors: list[ValidationError] = []

    if not manifest.get("@context"):
        errors.append(ValidationError("@context", "Missing — must include https://schema.org"))

    types = manifest.get("@type", [])
    if isinstance(types, str):
        types = [types]
    if "Organization" not in types:
        errors.append(ValidationError("@type", "Must include 'Organization'", "warning"))

    if not manifest.get("name"):
        errors.append(ValidationError("name", "Merchant name is required"))

    errors += _validate_url(manifest.get("url", ""), "url")

    methods = manifest.get("ucp:paymentMethods", [])
    if not methods:
        errors.append(ValidationError("ucp:paymentMethods", "At least one payment method required"))

    for i, m in enumerate(methods):
        if m.get("@type") != "PaymentMethod":
            errors.append(ValidationError(f"paymentMethods[{i}].@type", "Must be 'PaymentMethod'", "warning"))
        if m.get("addressEndpoint"):
            errors += _validate_url(m["addressEndpoint"], f"paymentMethods[{i}].addressEndpoint")
        if m.get("webhookEndpoint"):
            errors += _validate_url(m["webhookEndpoint"], f"paymentMethods[{i}].webhookEndpoint")

    if not manifest.get("ucp:agentInstructions"):
        errors.append(ValidationError("ucp:agentInstructions", "Missing — AI agents need this to know how to pay", "warning"))

    contact = manifest.get("contactPoint", {})
    if contact.get("email") and not re.match(r"[^@]+@[^@]+\.[^@]+", contact["email"]):
        errors.append(ValidationError("contactPoint.email", "Invalid email format"))

    return errors


# ---------------------------------------------------------------------------
# Core manifest builder
# ---------------------------------------------------------------------------

def _build_manifest(
    gateway: str,
    merchant_name: str,
    merchant_url: str,
    description: str = "",
    support_email: str = "",
    confirmations_required: int | None = None,
    accepted_currencies: list[str] | None = None,
    extra_capabilities: list[str] | None = None,
) -> dict[str, Any]:
    profile = GATEWAY_PROFILES[gateway]
    base_url = merchant_url.rstrip("/")
    confirmations = confirmations_required if confirmations_required is not None else profile["confirmations_default"]

    address_endpoint = base_url + profile["address_endpoint_path"]
    webhook_endpoint = base_url + profile["webhook_path"]

    instructions = profile["agent_instructions"].format(
        address_endpoint=address_endpoint,
        webhook_endpoint=webhook_endpoint,
        confirmations=confirmations,
    )

    currencies = accepted_currencies or profile["currency"].split(",")

    capabilities = list(profile["capabilities"])
    if extra_capabilities:
        capabilities += [c for c in extra_capabilities if c not in capabilities]

    manifest: dict[str, Any] = {
        "@context": [
            "https://schema.org",
            {"ucp": "https://ucp.dev/vocab#"},
        ],
        "@type": ["Organization", "ucp:Merchant"],
        "name": merchant_name,
        "url": merchant_url,
        "ucp:apiVersion": "1.0",
        "ucp:gateway": profile["label"],
        "ucp:capabilities": capabilities,
        "ucp:paymentMethods": [
            {
                "@type": "PaymentMethod",
                "identifier": profile["protocol"],
                "name": f"{profile['label']} — {', '.join(currencies[:3])}{'...' if len(currencies) > 3 else ''}",
                "provider": profile["label"],
                "currency": currencies,
                "confirmationsRequired": confirmations,
                "addressEndpoint": address_endpoint,
                "webhookEndpoint": webhook_endpoint,
                "docsUrl": profile["docs_url"],
            }
        ],
        "ucp:agentInstructions": instructions,
    }

    if description:
        manifest["description"] = description

    if support_email:
        manifest["contactPoint"] = {
            "@type": "ContactPoint",
            "email": support_email,
            "contactType": "customer support",
        }

    return manifest


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

SUPPORTED_GATEWAYS = list(GATEWAY_PROFILES.keys())


def generate_ucp_manifest(
    gateway: str,
    merchant_name: str,
    merchant_url: str,
    description: str = "",
    support_email: str = "",
    confirmations_required: int | None = None,
    accepted_currencies: list[str] | None = None,
) -> str:
    """
    Generate a UCP manifest for a specific gateway.
    Returns formatted JSON-LD string with validation summary.
    """
    gateway = gateway.lower().strip()
    if gateway not in GATEWAY_PROFILES:
        available = ", ".join(SUPPORTED_GATEWAYS)
        return f"Unknown gateway '{gateway}'. Supported: {available}"

    manifest = _build_manifest(
        gateway=gateway,
        merchant_name=merchant_name,
        merchant_url=merchant_url,
        description=description,
        support_email=support_email,
        confirmations_required=confirmations_required,
        accepted_currencies=accepted_currencies,
    )

    errors = _validate_manifest(manifest)
    hard   = [e for e in errors if e.severity == "error"]
    warns  = [e for e in errors if e.severity == "warning"]

    lines = [
        f"## UCP Manifest — {GATEWAY_PROFILES[gateway]['label']}",
        f"Save this as `/.well-known/ucp` on your server (serve as `application/ld+json`).\n",
        "```json",
        json.dumps(manifest, indent=2),
        "```\n",
    ]

    if not errors:
        lines.append("**Validation: PASSED ✓** — Manifest is valid and ready to serve.")
    else:
        if hard:
            lines.append(f"**Validation errors ({len(hard)}):**")
            for e in hard:
                lines.append(f"  ✗ {e}")
        if warns:
            lines.append(f"**Warnings ({len(warns)}):**")
            for w in warns:
                lines.append(f"  ⚠ {w}")

    lines += [
        f"\n**What this does:**",
        f"AI shopping agents (like Claude, GPT, and others) discover this file at {merchant_url}/.well-known/ucp",
        f"and use the instructions inside to pay your store automatically — no human checkout needed.",
        f"\n**How to serve it:**",
        f"  1. Save the JSON above to a file named `ucp` (no extension)",
        f"  2. Place it at the path `/.well-known/ucp` on your web server",
        f"  3. Serve with Content-Type: `application/ld+json`",
        f"  4. Verify: curl {merchant_url}/.well-known/ucp",
    ]

    return "\n".join(lines)


def generate_all_gateway_manifests(
    merchant_name: str,
    merchant_url: str,
    description: str = "",
    support_email: str = "",
) -> str:
    """
    Generate UCP manifests for ALL 6 gateways side by side.
    Useful for merchants who want to support multiple payment options.
    """
    lines = [
        f"## UCP Manifests — All Gateways",
        f"**Merchant:** {merchant_name}",
        f"**URL:** {merchant_url}\n",
        "Serve ONE of these at `/.well-known/ucp` depending on which gateway you use.",
        "Or combine `ucp:paymentMethods` arrays from multiple gateways into a single manifest",
        "if you accept payments from more than one gateway.\n",
        "─" * 60,
    ]

    for gw in SUPPORTED_GATEWAYS:
        manifest = _build_manifest(
            gateway=gw,
            merchant_name=merchant_name,
            merchant_url=merchant_url,
            description=description,
            support_email=support_email,
        )
        profile = GATEWAY_PROFILES[gw]
        lines += [
            f"\n### {profile['label']}",
            f"**Protocol:** `{profile['protocol']}`  |  **Currencies:** {profile['currency']}",
            "```json",
            json.dumps(manifest, indent=2),
            "```",
            "─" * 60,
        ]

    return "\n".join(lines)


def generate_multi_gateway_manifest(
    gateways: list[str],
    merchant_name: str,
    merchant_url: str,
    description: str = "",
    support_email: str = "",
) -> str:
    """
    Generate a single UCP manifest combining multiple gateways.
    Useful for merchants who accept several payment processors.
    """
    invalid = [g for g in gateways if g.lower() not in GATEWAY_PROFILES]
    if invalid:
        return f"Unknown gateways: {', '.join(invalid)}. Supported: {', '.join(SUPPORTED_GATEWAYS)}"

    base_url = merchant_url.rstrip("/")
    all_capabilities: list[str] = []
    all_methods: list[dict] = []

    for gw in gateways:
        gw = gw.lower().strip()
        profile = GATEWAY_PROFILES[gw]
        confirmations = profile["confirmations_default"]
        address_endpoint = base_url + profile["address_endpoint_path"]
        webhook_endpoint = base_url + profile["webhook_path"]

        for cap in profile["capabilities"]:
            if cap not in all_capabilities:
                all_capabilities.append(cap)

        all_methods.append({
            "@type": "PaymentMethod",
            "identifier": profile["protocol"],
            "name": f"{profile['label']} — {profile['currency']}",
            "provider": profile["label"],
            "currency": profile["currency"].split(","),
            "confirmationsRequired": confirmations,
            "addressEndpoint": address_endpoint,
            "webhookEndpoint": webhook_endpoint,
            "docsUrl": profile["docs_url"],
        })

    gateway_names = " + ".join(GATEWAY_PROFILES[g.lower()]["label"] for g in gateways)
    instructions = (
        f"This merchant accepts payments via: {gateway_names}. "
        f"Each payment method has its own addressEndpoint and webhookEndpoint. "
        f"Select the appropriate method based on the buyer's preferred currency. "
        f"Initiate payment by POSTing to the relevant addressEndpoint."
    )

    manifest: dict[str, Any] = {
        "@context": ["https://schema.org", {"ucp": "https://ucp.dev/vocab#"}],
        "@type": ["Organization", "ucp:Merchant"],
        "name": merchant_name,
        "url": merchant_url,
        "ucp:apiVersion": "1.0",
        "ucp:gateways": [GATEWAY_PROFILES[g.lower()]["label"] for g in gateways],
        "ucp:capabilities": all_capabilities,
        "ucp:paymentMethods": all_methods,
        "ucp:agentInstructions": instructions,
    }
    if description:
        manifest["description"] = description
    if support_email:
        manifest["contactPoint"] = {
            "@type": "ContactPoint",
            "email": support_email,
            "contactType": "customer support",
        }

    errors = _validate_manifest(manifest)
    hard  = [e for e in errors if e.severity == "error"]
    warns = [e for e in errors if e.severity == "warning"]

    lines = [
        f"## Multi-Gateway UCP Manifest",
        f"**Gateways included:** {gateway_names}\n",
        "```json",
        json.dumps(manifest, indent=2),
        "```\n",
    ]
    if not errors:
        lines.append("**Validation: PASSED ✓**")
    else:
        if hard:
            lines += [f"**Errors ({len(hard)}):**"] + [f"  ✗ {e}" for e in hard]
        if warns:
            lines += [f"**Warnings ({len(warns)}):**"] + [f"  ⚠ {w}" for w in warns]

    return "\n".join(lines)


def validate_ucp_manifest(manifest_json: str) -> str:
    """
    Validate a UCP manifest provided as a JSON string.
    Returns plain-English validation report.
    """
    try:
        manifest = json.loads(manifest_json)
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {e}\nPlease check the manifest is valid JSON before validating."

    errors = _validate_manifest(manifest)
    if not errors:
        return (
            "**Validation: PASSED ✓**\n"
            "Your UCP manifest is valid and ready to serve at /.well-known/ucp"
        )

    hard  = [e for e in errors if e.severity == "error"]
    warns = [e for e in errors if e.severity == "warning"]
    lines = []

    if hard:
        lines.append(f"**{len(hard)} error(s) — must fix:**")
        for e in hard:
            lines.append(f"  ✗ {e}")
    if warns:
        lines.append(f"\n**{len(warns)} warning(s) — recommended fixes:**")
        for w in warns:
            lines.append(f"  ⚠ {w}")

    return "\n".join(lines)


def explain_ucp() -> str:
    """
    Plain-English explanation of what UCP is and why merchants need it.
    """
    gateways = ", ".join(GATEWAY_PROFILES[g]["label"] for g in SUPPORTED_GATEWAYS)
    return f"""\
## What is UCP (Universal Commerce Protocol)?

**In plain English:**
UCP is a small file you put on your website that tells AI shopping agents
(like Claude, GPT-based agents, and autonomous buyers) exactly how to pay your store
— without a human going through your checkout flow.

Think of it like a business card for your payment system. When an AI agent wants
to buy something from your store, it reads this file and knows:
- Which payment gateways you support
- Which cryptocurrencies you accept
- Where to send the payment request
- How many confirmations to wait for

**Why does this matter?**
Agentic commerce is growing — AI assistants are starting to make purchases on behalf
of users. Without a UCP manifest, your store is invisible to these agents.
With one, your store can accept payments 24/7 from any AI buyer automatically.

**Supported gateways in this system:**
{gateways}

**How it works:**
1. You generate a manifest file for your gateway (takes 30 seconds)
2. You place it at `https://yourstore.com/.well-known/ucp`
3. AI agents discover it and can pay your store autonomously
4. You receive payments just like any other Bitcoin/crypto payment

**What it looks like:**
A JSON-LD file (structured data) served at a well-known URL path.
AI agents check this URL automatically — you don't need to do anything after setup.

**Generate your manifest:**
Ask me: "Generate a UCP manifest for [gateway name] for my store [URL]"
"""


# ── MCP server entry point (Python 3.10+ only) ──────────────────────────────
# Uncomment when mcp package is available:
#
# from mcp.server.fastmcp import FastMCP
# mcp = FastMCP("ucp-manifest-server")
#
# @mcp.tool()
# def generate_gateway_ucp_manifest(
#     gateway: str, merchant_name: str, merchant_url: str,
#     description: str = "", support_email: str = "",
#     confirmations_required: int = 0,
# ) -> str:
#     """Generate a UCP manifest for a specific payment gateway."""
#     return generate_ucp_manifest(gateway, merchant_name, merchant_url,
#                                  description, support_email,
#                                  confirmations_required or None)
#
# @mcp.tool()
# def generate_all_ucp_manifests(
#     merchant_name: str, merchant_url: str,
#     description: str = "", support_email: str = "",
# ) -> str:
#     """Generate UCP manifests for all 6 supported payment gateways."""
#     return generate_all_gateway_manifests(merchant_name, merchant_url,
#                                           description, support_email)
#
# @mcp.tool()
# def generate_combined_ucp_manifest(
#     gateways: list[str], merchant_name: str, merchant_url: str,
#     description: str = "", support_email: str = "",
# ) -> str:
#     """Generate a single UCP manifest combining multiple gateways."""
#     return generate_multi_gateway_manifest(gateways, merchant_name, merchant_url,
#                                            description, support_email)
#
# @mcp.tool()
# def validate_ucp(manifest_json: str) -> str:
#     """Validate a UCP manifest JSON string."""
#     return validate_ucp_manifest(manifest_json)
#
# @mcp.tool()
# def what_is_ucp() -> str:
#     """Explain what UCP is and why merchants need it."""
#     return explain_ucp()
#
# if __name__ == "__main__":
#     mcp.run()
