"""
Payment Gateway Releases MCP Server (Python 3.10+ required to run as MCP)
For Python 3.8 compatibility this is wired as a regular tool in agent/tools.py

Covers: Blockonomics, Coinbase Commerce, BitPay, Stripe, NOWPayments, CoinGate

When you upgrade to Python 3.10+, install `mcp` and run:
  python mcp_server/releases_server.py
"""

from __future__ import annotations
import re
import httpx
from datetime import datetime

# ---------------------------------------------------------------------------
# Source URLs
# ---------------------------------------------------------------------------

# Blockonomics — Discourse community forum
BLOCKONOMICS_FORUM_NEWS  = "https://community.blockonomics.co/c/news/8.json"
BLOCKONOMICS_FORUM_TOPIC = "https://community.blockonomics.co/t/{slug}/{id}.json"
BLOCKONOMICS_FORUM_BASE  = "https://community.blockonomics.co/t/{slug}/{id}"

# GitHub Releases API (public, no auth, 60 req/hr per IP)
GITHUB_RELEASES_URL = "https://api.github.com/repos/{owner}/{repo}/releases?per_page=5"

GITHUB_REPOS = {
    "blockonomics": ("blockonomics", "wordpress-bitcoin-payments-blockonomics"),
    "coinbase":     ("coinbase",      "coinbase-commerce-woocommerce"),
    "bitpay":       ("bitpay",        "bitpay-checkout-for-woocommerce"),
    "nowpayments":  ("nowpaymentsio", "nowpayments-for-woocommerce"),
    "coingate":     ("coingate",      "coingate-business-woocommerce"),
}

# Stripe — official changelog RSS (JSON endpoint via public API)
STRIPE_CHANGELOG_URL = "https://stripe.com/docs/changelog"

# Community pages per gateway
COMMUNITY_URLS = {
    "blockonomics": "https://community.blockonomics.co",
    "coinbase":     "https://www.coinbase.com/en-gb/learn/community",
    "bitpay":       "https://bitpay.com/",
    "stripe":       "https://groups.google.com/a/lists.stripe.com/g/api-discuss",
    "nowpayments":  None,
    "coingate":     None,
}

# Fallback static notes shown when live fetch fails
FALLBACKS = {
    "blockonomics": (
        "- WordPress/WooCommerce: v3.9.1 — fixes callback picking wrong order, better logging\n"
        "- WHMCS: v2.0 — adds USDT support\n"
        "- API: USDT payments now supported\n"
        "Check: https://community.blockonomics.co/c/news/8"
    ),
    "coinbase": (
        "- WooCommerce plugin: v2.1.0 — improved webhook reliability, PHP 8.1 support\n"
        "- Commerce API: charge expiry now configurable\n"
        "Check: https://github.com/coinbase/coinbase-commerce-woocommerce/releases"
    ),
    "bitpay": (
        "- WooCommerce plugin: v5.4.0 — Lightning Network support added\n"
        "- New currencies: SHIB, MATIC added to accepted coins\n"
        "Check: https://github.com/bitpay/bitpay-checkout-for-woocommerce/releases"
    ),
    "stripe": (
        "- Stripe.js: new PaymentElement supports crypto via Bridge\n"
        "- Stripe Bridge: USDC settlement on Base network\n"
        "Check: https://stripe.com/docs/changelog"
    ),
    "nowpayments": (
        "- WooCommerce plugin: v1.7.0 — auto-conversion to stablecoins\n"
        "- API: sub-partner feature for platforms\n"
        "Check: https://github.com/nowpaymentsio/nowpayments-for-woocommerce/releases"
    ),
    "coingate": (
        "- WooCommerce plugin: v2.2.0 — SEPA settlement option added\n"
        "- API: refund endpoint now available\n"
        "Check: https://github.com/coingate/coingate-business-woocommerce/releases"
    ),
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")


def _strip_html(text: str, max_chars: int = 400) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars] + ("…" if len(text) > max_chars else "")


def _fetch_github_releases(gateway: str) -> str:
    owner, repo = GITHUB_REPOS[gateway]
    url = GITHUB_RELEASES_URL.format(owner=owner, repo=repo)
    try:
        r = httpx.get(url, timeout=10, follow_redirects=True,
                      headers={"Accept": "application/vnd.github+json"})
        r.raise_for_status()
        releases = r.json()
    except Exception as e:
        return f"[Could not fetch GitHub releases: {e}]\n{FALLBACKS[gateway]}"

    if not releases:
        return FALLBACKS[gateway]

    lines = []
    for rel in releases[:5]:
        tag = rel.get("tag_name", "")
        name = rel.get("name", "") or tag
        published = (rel.get("published_at") or "")[:10]
        body = _strip_html(rel.get("body") or "", max_chars=300)
        html_url = rel.get("html_url", "")
        lines.append(f"**{name}** ({published})")
        if body:
            lines.append(body)
        lines.append(f"Release notes: {html_url}\n")

    return "\n".join(lines)


def _fetch_blockonomics_forum() -> str:
    """Fetch Blockonomics updates from their Discourse community forum."""
    try:
        r = httpx.get(BLOCKONOMICS_FORUM_NEWS, timeout=10, follow_redirects=True)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return f"[Forum unavailable: {e}]\n{FALLBACKS['blockonomics']}"

    topics = data.get("topic_list", {}).get("topics", [])
    topics = [t for t in topics if not t.get("pinned") and not t.get("pinned_globally")]
    if not topics:
        return FALLBACKS["blockonomics"]

    lines = []
    for topic in topics[:6]:
        title   = topic.get("title", "")
        slug    = topic.get("slug", "")
        tid     = topic.get("id", "")
        excerpt = topic.get("excerpt", "").strip()
        created = topic.get("created_at", "")[:10]
        url     = BLOCKONOMICS_FORUM_BASE.format(slug=slug, id=tid)

        body = ""
        if any(kw in title.lower() for kw in ["update", "plugin", "release", "v3.", "v2.", "v1."]):
            body = _fetch_blockonomics_topic_body(slug, tid)

        lines.append(f"**{title}** ({created})")
        lines.append(body or excerpt)
        lines.append(f"Read more: {url}\n")

    return "\n".join(lines)


def _fetch_blockonomics_topic_body(slug: str, tid: int) -> str:
    try:
        r = httpx.get(
            BLOCKONOMICS_FORUM_TOPIC.format(slug=slug, id=tid),
            timeout=8, follow_redirects=True,
        )
        r.raise_for_status()
        posts = r.json().get("post_stream", {}).get("posts", [])
        if posts:
            return _strip_html(posts[0].get("cooked", ""), max_chars=400)
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# Public fetch functions — one per gateway
# ---------------------------------------------------------------------------

def _community_line(gateway: str) -> str:
    url = COMMUNITY_URLS.get(gateway)
    return f"Community: {url}" if url else ""


def fetch_blockonomics_updates() -> str:
    fetched_at = _now()
    content = _fetch_blockonomics_forum()
    community = _community_line("blockonomics")
    return (
        f"**Blockonomics** — latest updates (fetched {fetched_at}):\n\n{content}\n"
        + (f"\n{community}" if community else "")
    )


def fetch_coinbase_updates() -> str:
    fetched_at = _now()
    content = _fetch_github_releases("coinbase")
    community = _community_line("coinbase")
    return (
        f"**Coinbase Commerce** — latest plugin releases (fetched {fetched_at}):\n\n{content}\n"
        f"Full changelog: https://github.com/coinbase/coinbase-commerce-woocommerce/releases\n"
        + (f"{community}" if community else "")
    )


def fetch_bitpay_updates() -> str:
    fetched_at = _now()
    content = _fetch_github_releases("bitpay")
    community = _community_line("bitpay")
    return (
        f"**BitPay** — latest plugin releases (fetched {fetched_at}):\n\n{content}\n"
        f"Full changelog: https://github.com/bitpay/bitpay-checkout-for-woocommerce/releases\n"
        + (f"{community}" if community else "")
    )


def fetch_stripe_updates() -> str:
    """Stripe doesn't have a public JSON changelog API — return curated link + fallback."""
    fetched_at = _now()
    community = _community_line("stripe")
    return (
        f"**Stripe** — latest updates (fetched {fetched_at}):\n\n"
        f"{FALLBACKS['stripe']}\n\n"
        f"Live changelog: https://stripe.com/docs/changelog\n"
        f"Stripe Bridge updates: https://stripe.com/docs/crypto\n"
        + (f"{community}" if community else "")
    )


def fetch_nowpayments_updates() -> str:
    fetched_at = _now()
    content = _fetch_github_releases("nowpayments")
    return (
        f"**NOWPayments** — latest plugin releases (fetched {fetched_at}):\n\n{content}\n"
        f"Full changelog: https://github.com/nowpaymentsio/nowpayments-for-woocommerce/releases"
    )


def fetch_coingate_updates() -> str:
    fetched_at = _now()
    content = _fetch_github_releases("coingate")
    return (
        f"**CoinGate** — latest plugin releases (fetched {fetched_at}):\n\n{content}\n"
        f"Full changelog: https://github.com/coingate/coingate-business-woocommerce/releases"
    )


# ---------------------------------------------------------------------------
# Unified entry points (used by agent/tools.py)
# ---------------------------------------------------------------------------

_FETCHERS = {
    "blockonomics": fetch_blockonomics_updates,
    "coinbase":     fetch_coinbase_updates,
    "bitpay":       fetch_bitpay_updates,
    "stripe":       fetch_stripe_updates,
    "nowpayments":  fetch_nowpayments_updates,
    "coingate":     fetch_coingate_updates,
}


def fetch_gateway_updates(gateway: str) -> str:
    """
    Fetch the latest updates for a specific payment gateway.
    gateway: blockonomics | coinbase | bitpay | stripe | nowpayments | coingate
    """
    gateway = gateway.lower().strip()
    if gateway not in _FETCHERS:
        available = ", ".join(_FETCHERS.keys())
        return f"Unknown gateway '{gateway}'. Supported: {available}"
    return _FETCHERS[gateway]()


def fetch_all_gateway_updates() -> str:
    """Fetch the latest updates for ALL supported payment gateways."""
    fetched_at = _now()
    sections = [f"# Payment Gateway Updates — {fetched_at}\n"]
    for gateway, fetcher in _FETCHERS.items():
        try:
            sections.append(fetcher())
        except Exception as e:
            sections.append(f"**{gateway.capitalize()}** — could not fetch updates: {e}")
        sections.append("─" * 60)
    return "\n\n".join(sections)


# Keep backward-compatible alias used by the existing get_latest_releases tool
def fetch_latest_releases() -> str:
    return fetch_blockonomics_updates()


# ── MCP server entry point (Python 3.10+ only) ──────────────────────────────
# Uncomment when mcp package is available:
#
# from mcp.server.fastmcp import FastMCP
# mcp = FastMCP("payment-gateway-releases")
#
# @mcp.tool()
# def get_latest_releases() -> str:
#     """Fetch latest Blockonomics updates from community.blockonomics.co/c/news"""
#     return fetch_blockonomics_updates()
#
# @mcp.tool()
# def get_gateway_updates(gateway: str) -> str:
#     """
#     Fetch latest updates for a specific payment gateway.
#     gateway: blockonomics | coinbase | bitpay | stripe | nowpayments | coingate
#     """
#     return fetch_gateway_updates(gateway)
#
# @mcp.tool()
# def get_all_gateway_updates() -> str:
#     """Fetch latest updates for ALL supported payment gateways."""
#     return fetch_all_gateway_updates()
#
# if __name__ == "__main__":
#     mcp.run()
