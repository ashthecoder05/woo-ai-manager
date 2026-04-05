from __future__ import annotations
"""
Setup Engine — detects platform, picks integration strategy, and generates code snippets.
"""

import json
import re
from pathlib import Path

_CAPS_PATH = Path(__file__).parent.parent / "knowledge" / "platform_capabilities.json"
_CAPABILITIES: dict = json.loads(_CAPS_PATH.read_text())


# ---------------------------------------------------------------------------
# Platform Detection
# ---------------------------------------------------------------------------

def detect_platform(context: str) -> str:
    """
    Detect which platform the user is working with based on free-text context
    (e.g. their question, file names, code snippets).

    Returns a platform key from platform_capabilities.json, or 'custom_python' as fallback.
    """
    context_lower = context.lower()
    platforms = _CAPABILITIES["platforms"]

    scores: dict[str, int] = {}
    for key, info in platforms.items():
        score = sum(1 for kw in info["detection_keywords"] if kw.lower() in context_lower)
        if score:
            scores[key] = score

    if not scores:
        return _CAPABILITIES["default_platform"]

    return max(scores, key=lambda k: scores[k])


# ---------------------------------------------------------------------------
# Strategy Picker
# ---------------------------------------------------------------------------

def pick_strategy(platform_key: str) -> dict:
    """
    Return the recommended integration strategy for a platform.
    """
    platforms = _CAPABILITIES["platforms"]
    if platform_key not in platforms:
        platform_key = _CAPABILITIES["default_platform"]

    info = platforms[platform_key]
    method = info["integration_method"]

    strategies = {
        "plugin": {
            "name": "Plugin Install",
            "steps": [
                "Install the official Blockonomics plugin from the marketplace",
                "Enter your API key in the plugin settings",
                "Register your xpub wallet in the Blockonomics dashboard",
                "Set your webhook callback URL",
                "Run Test Setup to verify everything works",
            ],
            "complexity": "low",
        },
        "hosted_redirect": {
            "name": "Hosted Redirect",
            "steps": [
                "Create a store in the Blockonomics merchant dashboard",
                "Copy the hosted payment page URL template",
                "Add the redirect script to your checkout page",
                "Set your webhook callback URL in the dashboard",
                "Test with a minimal purchase",
            ],
            "complexity": "low",
        },
        "api_direct": {
            "name": "Direct API Integration",
            "steps": [
                "Install the httpx (Python) or enable curl (PHP) library",
                "Store your API key securely in environment variables",
                "Call /api/new_address to generate a payment address per order",
                "Show the address + QR code to the customer",
                "Receive and verify webhook callbacks to confirm payment",
                "Fulfill the order on status >= 2 (confirmed)",
            ],
            "complexity": "medium",
        },
    }

    return {
        "platform": info["label"],
        "method": method,
        "strategy": strategies.get(method, strategies["api_direct"]),
        "requires_xpub": info["requires_xpub"],
        "requires_ssl": info["requires_ssl"],
        "webhook_path": info["webhook_path"],
        "guide": info["guide"],
    }


# ---------------------------------------------------------------------------
# Code Generation
# ---------------------------------------------------------------------------

def generate_code(platform_key: str, webhook_secret: str = "CHANGE_ME") -> dict[str, str]:
    """
    Generate ready-to-use code snippets for the given platform.
    Returns a dict of { filename: code_content }.
    """
    snippets: dict[str, str] = {}

    if platform_key == "custom_python":
        snippets["blockonomics_client.py"] = _python_client()
        snippets["webhook_handler.py"] = _python_webhook(webhook_secret)

    elif platform_key == "custom_php":
        snippets["blockonomics.php"] = _php_client()
        snippets["webhook.php"] = _php_webhook(webhook_secret)

    elif platform_key == "woocommerce":
        snippets["instructions.md"] = _woocommerce_instructions()

    elif platform_key == "shopify":
        snippets["instructions.md"] = _shopify_instructions()

    else:
        snippets["blockonomics_client.py"] = _python_client()
        snippets["webhook_handler.py"] = _python_webhook(webhook_secret)

    return snippets


def _python_client() -> str:
    return '''\
import os
import httpx

API_KEY = os.getenv("BLOCKONOMICS_API_KEY", "")
BASE = "https://www.blockonomics.co/api"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}


def new_address() -> str:
    r = httpx.post(f"{BASE}/new_address", headers=HEADERS, json={"reset": 0})
    r.raise_for_status()
    return r.json()["address"]


def get_price_usd() -> float:
    r = httpx.get(f"{BASE}/price?currency=USD")
    r.raise_for_status()
    return float(r.json()["price"])


def usd_to_satoshis(usd: float) -> int:
    return int((usd / get_price_usd()) * 1e8)
'''


def _python_webhook(secret: str) -> str:
    return f'''\
from fastapi import APIRouter, Query, HTTPException

router = APIRouter()
WEBHOOK_SECRET = "{secret}"


@router.get("/webhook/blockonomics")
def blockonomics_webhook(
    secret: str = Query(...),
    addr: str = Query(...),
    value: int = Query(...),
    txid: str = Query(...),
    status: int = Query(...),
):
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="forbidden")

    # status: 0=unconfirmed, 1=partial, 2=confirmed
    if status >= 2:
        # TODO: fulfill_order(addr, value)
        pass

    return {{"ok": True}}
'''


def _php_client() -> str:
    return '''\
<?php
function blockonomics_new_address(string $api_key): string {
    $ch = curl_init(\'https://www.blockonomics.co/api/new_address\');
    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => json_encode([\'reset\' => 0]),
        CURLOPT_HTTPHEADER => [\'Authorization: Bearer \' . $api_key, \'Content-Type: application/json\'],
        CURLOPT_RETURNTRANSFER => true,
    ]);
    $resp = json_decode(curl_exec($ch), true);
    curl_close($ch);
    return $resp[\'address\'];
}

function blockonomics_price(string $currency = \'USD\'): float {
    $data = json_decode(file_get_contents(
        \'https://www.blockonomics.co/api/price?currency=\' . urlencode($currency)
    ), true);
    return (float) $data[\'price\'];
}
'''


def _php_webhook(secret: str) -> str:
    return f'''\
<?php
define(\'WEBHOOK_SECRET\', \'{secret}\');

$secret = $_GET[\'secret\'] ?? \'\';
if ($secret !== WEBHOOK_SECRET) {{
    http_response_code(403);
    exit(json_encode([\'error\' => \'forbidden\']));
}}

$addr   = $_GET[\'addr\']   ?? \'\';
$value  = (int)($_GET[\'value\']  ?? 0);
$txid   = $_GET[\'txid\']   ?? \'\';
$status = (int)($_GET[\'status\'] ?? -1);

if ($status >= 2) {{
    // TODO: fulfill_order($addr, $value);
}}

echo json_encode([\'ok\' => true]);
'''


def _woocommerce_instructions() -> str:
    return (
        "# WooCommerce Setup\n"
        "1. Go to Plugins → Add New → search 'Blockonomics'\n"
        "2. Install and activate the plugin\n"
        "3. Go to WooCommerce → Settings → Payments → Blockonomics\n"
        "4. Enter your API key and save\n"
        "5. In Blockonomics dashboard, register your xpub and set webhook URL\n"
        "6. Click 'Test Setup' to verify\n"
    )


def _shopify_instructions() -> str:
    return (
        "# Shopify Setup\n"
        "1. In Blockonomics dashboard → Merchants → Stores → Add Store → Shopify\n"
        "2. Copy the hosted payment link template\n"
        "3. In Shopify admin → Settings → Checkout → Additional Scripts\n"
        "4. Paste the redirect snippet\n"
        "5. Test with a low-value product\n"
    )


# ---------------------------------------------------------------------------
# Public summary helper (used by agent tools)
# ---------------------------------------------------------------------------

def get_setup_summary(context: str) -> str:
    """Return a human-readable setup guide for the detected platform."""
    platform_key = detect_platform(context)
    strategy = pick_strategy(platform_key)
    snippets = generate_code(platform_key)

    lines = [
        f"**Detected platform:** {strategy['platform']}",
        f"**Integration method:** {strategy['method']}",
        "",
        f"**Steps:**",
    ]
    for i, step in enumerate(strategy["strategy"]["steps"], 1):
        lines.append(f"  {i}. {step}")

    if snippets:
        lines.append("")
        lines.append("**Generated files:**")
        for fname in snippets:
            lines.append(f"  - `{fname}`")

    lines.append(f"\nFull guide: `{strategy['guide']}`")
    return "\n".join(lines)
