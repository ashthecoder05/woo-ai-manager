"""
Bitcoin Fee Advisor MCP Server

Helps merchants and customers understand Bitcoin network fees and
how to factor them into product pricing, payment thresholds, and
checkout decisions — in plain English.

Topics covered:
  - What is a Bitcoin network fee (gas fee)?
  - Current fee rates and what they mean
  - Product pricing recommendations based on fee levels
  - Minimum viable order amount by fee environment
  - Fee impact per product category (micro, low, mid, high value)
  - How to absorb, pass on, or offset fees
  - Customer-facing fee explainer
  - RBF / CPFP fee bumping guide

For Python 3.10+ run as MCP:
  python mcp_server/fee_advisor.py
"""

from __future__ import annotations
import httpx
from datetime import datetime, timezone

_BASE = "https://mempool.space/api"


# ---------------------------------------------------------------------------
# Live fee fetching
# ---------------------------------------------------------------------------

def _fetch_fees() -> dict:
    try:
        r = httpx.get(f"{_BASE}/v1/fees/recommended", timeout=10)
        r.raise_for_status()
        d = r.json()
        return {
            "fastest":  d.get("fastestFee", 50),
            "half_hour": d.get("halfHourFee", 30),
            "hour":     d.get("hourFee", 20),
            "economy":  d.get("economyFee", 10),
            "minimum":  d.get("minimumFee", 1),
        }
    except Exception:
        return {"fastest": 50, "half_hour": 30, "hour": 20, "economy": 10, "minimum": 1}


def _fetch_btc_price_usd() -> float:
    try:
        r = httpx.get("https://www.blockonomics.co/api/price?currency=USD", timeout=8)
        r.raise_for_status()
        return float(r.json()["price"])
    except Exception:
        return 65000.0


def _fetch_mempool() -> dict:
    try:
        r = httpx.get(f"{_BASE}/mempool", timeout=8)
        r.raise_for_status()
        d = r.json()
        vsize = d.get("vsize", 0)
        count = d.get("count", 0)
        if vsize > 50_000_000:
            congestion = "very high"
        elif vsize > 10_000_000:
            congestion = "high"
        elif vsize > 2_000_000:
            congestion = "moderate"
        else:
            congestion = "low"
        return {"congestion": congestion, "pending_tx": count, "vsize": vsize}
    except Exception:
        return {"congestion": "unknown", "pending_tx": 0, "vsize": 0}


# ---------------------------------------------------------------------------
# Fee maths helpers
# ---------------------------------------------------------------------------

# A typical Bitcoin transaction is ~225 vBytes (P2PKH, 1-in 2-out)
# A SegWit (P2WPKH) transaction is ~140 vBytes
TYPICAL_TX_VBYTES = 225
SEGWIT_TX_VBYTES  = 140


def _fee_in_sats(fee_rate: float, vbytes: int = TYPICAL_TX_VBYTES) -> int:
    return int(fee_rate * vbytes)


def _sats_to_usd(sats: int, btc_price: float) -> float:
    return round((sats / 1e8) * btc_price, 4)


def _usd_to_sats(usd: float, btc_price: float) -> int:
    return int((usd / btc_price) * 1e8)


def _fee_pct_of_order(fee_sats: int, order_usd: float, btc_price: float) -> float:
    fee_usd = _sats_to_usd(fee_sats, btc_price)
    return round((fee_usd / order_usd) * 100, 2) if order_usd > 0 else 0


def _congestion_label(fees: dict) -> str:
    fastest = fees["fastest"]
    if fastest >= 100:
        return "VERY HIGH 🔴"
    if fastest >= 50:
        return "HIGH 🟠"
    if fastest >= 20:
        return "MODERATE 🟡"
    return "LOW 🟢"


def _now() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# ---------------------------------------------------------------------------
# Product category thresholds
# ---------------------------------------------------------------------------

PRODUCT_CATEGORIES = {
    "micro":   {"label": "Micro purchase",   "example": "tip, coffee, article, song",          "min_usd": 0.01, "max_usd": 5},
    "low":     {"label": "Low-value item",    "example": "ebook, sticker, small merchandise",   "min_usd": 5,    "max_usd": 30},
    "mid":     {"label": "Mid-value item",    "example": "book, clothing, software license",    "min_usd": 30,   "max_usd": 200},
    "high":    {"label": "High-value item",   "example": "electronics, hardware, course",       "min_usd": 200,  "max_usd": 2000},
    "premium": {"label": "Premium purchase",  "example": "jewellery, hardware wallet, luxury",  "min_usd": 2000, "max_usd": 999999},
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def explain_bitcoin_fees() -> str:
    """
    Plain-English explanation of what Bitcoin network fees are,
    why they exist, and how they affect payments.
    """
    fees = _fetch_fees()
    btc_price = _fetch_btc_price_usd()
    mempool = _fetch_mempool()

    fastest_fee_usd  = _sats_to_usd(_fee_in_sats(fees["fastest"]), btc_price)
    economy_fee_usd  = _sats_to_usd(_fee_in_sats(fees["economy"]), btc_price)
    congestion       = _congestion_label(fees)

    return f"""\
## What is a Bitcoin Network Fee?

**In plain English:**
When you send Bitcoin, your transaction needs to be picked up by a miner \
(a computer that processes transactions) and added to the blockchain. \
Miners choose transactions that pay the highest fee — so the fee is essentially \
a priority ticket. Higher fee = faster confirmation.

This is similar to paying for express vs standard shipping:
- Express (next block, ~10 min) = higher fee
- Standard (1 hour) = lower fee
- Economy (few hours) = cheapest

**Key facts:**
- Fees go to miners, NOT to Blockonomics, Coinbase, BitPay, or any gateway
- Fees are paid by whoever SENDS the Bitcoin (usually the customer)
- Fees are fixed per transaction — they do NOT scale with the payment amount
  (sending $5 or $5,000 costs the same fee)
- Fees are measured in sat/vByte (satoshis per virtual byte of data)

---

## Current Network Fees (live — {_now()})

| Speed             | Fee Rate      | Estimated Cost (USD) | Confirmation Time |
|-------------------|---------------|----------------------|-------------------|
| Next block        | {fees["fastest"]} sat/vB   | ~${fastest_fee_usd:.3f}            | ~10 minutes       |
| ~30 minutes       | {fees["half_hour"]} sat/vB   | ~${_sats_to_usd(_fee_in_sats(fees["half_hour"]), btc_price):.3f}            | ~30 minutes       |
| ~1 hour           | {fees["hour"]} sat/vB   | ~${_sats_to_usd(_fee_in_sats(fees["hour"]), btc_price):.3f}            | ~1 hour           |
| Economy           | {fees["economy"]} sat/vB   | ~${economy_fee_usd:.3f}            | Few hours         |

**Mempool congestion: {congestion}** ({mempool["pending_tx"]:,} transactions waiting)

---

## Why does this matter for merchants?

1. **Small orders become expensive at high fees**
   - If the fee is $2 and your product costs $3, the customer pays $5 total — a 67% overhead
   - Consider setting a minimum order value during high-fee periods

2. **Fees don't affect your payout**
   - You receive the exact BTC amount shown on the invoice
   - The customer pays the network fee separately from their wallet

3. **Stuck transactions**
   - If a customer paid with a very low fee during a congested period,
     their transaction may be stuck unconfirmed for hours
   - Use the `diagnose_stuck_transaction` tool to check

4. **For physical goods**: always wait for at least 1 confirmation before shipping
"""


def get_fee_impact_by_product(product_price_usd: float) -> str:
    """
    Show how current Bitcoin fees impact a specific product price.
    Gives plain-English advice on whether to absorb, pass on, or adjust.
    """
    fees = _fetch_fees()
    btc_price = _fetch_btc_price_usd()

    # Determine product category
    category = "premium"
    for cat_key, cat in PRODUCT_CATEGORIES.items():
        if product_price_usd <= cat["max_usd"]:
            category = cat_key
            break
    cat_info = PRODUCT_CATEGORIES[category]

    # Calculate fee impact at different speeds
    rows = []
    for label, rate_key, time_str in [
        ("Next block (~10 min)", "fastest",   "~10 min"),
        ("~30 minutes",          "half_hour", "~30 min"),
        ("~1 hour",              "hour",      "~1 hr"),
        ("Economy",              "economy",   "hours"),
    ]:
        rate = fees[rate_key]
        fee_sats = _fee_in_sats(rate)
        fee_usd = _sats_to_usd(fee_sats, btc_price)
        pct = _fee_pct_of_order(fee_sats, product_price_usd, btc_price)
        rows.append((label, rate, fee_usd, pct, time_str))

    # Recommendation logic
    fastest_fee_usd = _sats_to_usd(_fee_in_sats(fees["fastest"]), btc_price)
    economy_fee_usd = _sats_to_usd(_fee_in_sats(fees["economy"]), btc_price)
    fastest_pct = _fee_pct_of_order(_fee_in_sats(fees["fastest"]), product_price_usd, btc_price)

    if fastest_pct > 20:
        risk = "HIGH FEE IMPACT 🔴"
        advice = (
            f"Network fees ({fastest_fee_usd:.3f} USD) represent over {fastest_pct}% of your product price. "
            f"Consider raising your minimum order value, or temporarily accepting only economy-speed payments."
        )
        recommendation = [
            f"Set a minimum order value of at least ${fastest_fee_usd * 10:.2f} USD during high-fee periods",
            "Display a fee warning at checkout so customers aren't surprised",
            "Consider bundling orders or waiting for lower-fee periods",
            "For digital goods: economy fee is fine — no need to rush confirmation",
        ]
    elif fastest_pct > 5:
        risk = "MODERATE FEE IMPACT 🟡"
        advice = (
            f"Network fees are noticeable ({fastest_pct}% of order value) but manageable. "
            f"Consider absorbing the fee or displaying it clearly at checkout."
        )
        recommendation = [
            "Show the fee estimate at checkout so customers can decide on confirmation speed",
            "For recurring customers: consider Lightning Network for small payments",
            "Economy fee is likely fine for non-urgent orders",
        ]
    else:
        risk = "LOW FEE IMPACT 🟢"
        advice = (
            f"Network fees are minimal ({fastest_pct}% of order value) relative to your product price. "
            f"No major action needed."
        )
        recommendation = [
            "Fees are not a concern at this price point",
            "Offer customers the choice of confirmation speed",
            "Economy fee is recommended to save customers money",
        ]

    lines = [
        f"## Fee Impact Analysis for ${product_price_usd:.2f} Product",
        f"**Category:** {cat_info['label']} ({cat_info['example']})",
        f"**BTC price used:** ${btc_price:,.2f}",
        f"**Fee impact level:** {risk}\n",
        f"### Fee breakdown at current rates",
        f"{'Speed':<22} {'Rate':>10} {'Fee (USD)':>12} {'% of order':>12} {'Time':>10}",
        "-" * 70,
    ]
    for label, rate, fee_usd, pct, time_str in rows:
        lines.append(f"{label:<22} {rate:>7} s/vB  ${fee_usd:>8.4f}  {pct:>9.1f}%  {time_str:>10}")

    lines += [
        f"\n### What this means for you",
        advice,
        f"\n### Recommendations",
    ]
    for r in recommendation:
        lines.append(f"  - {r}")

    lines += [
        f"\n### Pricing strategy for '{cat_info['label']}' products",
        *_pricing_strategy(category, product_price_usd, fastest_fee_usd, economy_fee_usd, btc_price),
    ]

    return "\n".join(lines)


def _pricing_strategy(category: str, price_usd: float, fastest_fee_usd: float,
                       economy_fee_usd: float, btc_price: float) -> list[str]:
    strategies = {
        "micro": [
            "⚠ Micro purchases are NOT recommended for on-chain Bitcoin during normal/high fee periods",
            "Consider: Lightning Network (fees < $0.001), or batch micropayments",
            f"Minimum viable on-chain order at current fees: ${fastest_fee_usd * 5:.2f} USD",
            "If you must accept on-chain: use economy fee and inform customers of long wait",
        ],
        "low": [
            f"Add a small fee buffer of ${fastest_fee_usd:.3f}–${fastest_fee_usd * 1.5:.3f} to your price if absorbing fees",
            "Display a 'network fee included' badge to reassure customers",
            f"Set checkout minimum to ${fastest_fee_usd * 3:.2f} USD during high-fee periods",
            "Economy confirmation speed is fine for digital goods at this price",
        ],
        "mid": [
            "Fees are a small percentage — no major pricing adjustment needed",
            "Offer 2 confirmation speeds: 'Standard (1 hr, free)' and 'Express (10 min, small surcharge)'",
            "Consider displaying BTC + USD equivalent at checkout to build trust",
            "Wait for 1 confirmation before digital delivery, 2 for physical goods",
        ],
        "high": [
            "Fees are negligible relative to order value — absorb them comfortably",
            "Always wait for 2–3 confirmations before shipping physical goods",
            "Consider requesting the customer use SegWit address (bc1...) — saves ~40% on fees",
            "Display mempool.space link at checkout for customers who want to track their payment",
        ],
        "premium": [
            "Fees are completely negligible — no action needed",
            "Require 6 confirmations before releasing premium goods",
            "Offer escrow or multi-sig for very high-value transactions",
            "Consider hardware wallet verification for extra security",
        ],
    }
    return strategies.get(category, strategies["mid"])


def get_fee_adjustment_guide(product_price_usd: float, confirmation_speed: str = "hour") -> str:
    """
    Give merchants a concrete action plan for adjusting prices and
    checkout flow based on current fee levels.
    confirmation_speed: fastest | half_hour | hour | economy
    """
    fees = _fetch_fees()
    btc_price = _fetch_btc_price_usd()
    mempool = _fetch_mempool()

    speed_map = {
        "fastest":    ("fastest",   "next block (~10 min)"),
        "half_hour":  ("half_hour", "~30 minutes"),
        "hour":       ("hour",      "~1 hour"),
        "economy":    ("economy",   "few hours"),
    }
    rate_key, speed_label = speed_map.get(confirmation_speed, speed_map["hour"])
    fee_rate = fees[rate_key]
    fee_sats = _fee_in_sats(fee_rate)
    fee_usd  = _sats_to_usd(fee_sats, btc_price)
    fee_sats_segwit = _fee_in_sats(fee_rate, SEGWIT_TX_VBYTES)
    fee_usd_segwit  = _sats_to_usd(fee_sats_segwit, btc_price)

    order_sats    = _usd_to_sats(product_price_usd, btc_price)
    buffered_sats = order_sats + fee_sats
    buffered_usd  = round(product_price_usd + fee_usd, 2)

    pct = _fee_pct_of_order(fee_sats, product_price_usd, btc_price)
    congestion = _congestion_label(fees)

    lines = [
        f"## Fee Adjustment Guide",
        f"**Product price:** ${product_price_usd:.2f} USD",
        f"**Confirmation speed:** {speed_label}",
        f"**Current fee rate:** {fee_rate} sat/vB",
        f"**Mempool:** {congestion} ({mempool['pending_tx']:,} pending txs)",
        f"**BTC price:** ${btc_price:,.2f}\n",

        f"### Fee Cost Breakdown",
        f"- Standard transaction fee:   **{fee_sats:,} sats** (${fee_usd:.4f} USD)",
        f"- SegWit transaction fee:     **{fee_sats_segwit:,} sats** (${fee_usd_segwit:.4f} USD) — 40% cheaper",
        f"- Fee as % of order:          **{pct}%**\n",

        f"### Option 1 — Absorb the fee (include it in your price)",
        f"  Charge the customer: **${buffered_usd:.2f} USD** (original ${product_price_usd:.2f} + ${fee_usd:.4f} fee)",
        f"  BTC amount to request: **{buffered_sats / 1e8:.8f} BTC** ({buffered_sats:,} sats)",
        f"  Customer experience: simple, no surprises",
        f"  Best for: products under $50 where fee is < 5% of order\n",

        f"### Option 2 — Pass the fee to the customer (show at checkout)",
        f"  Show order total: ${product_price_usd:.2f} + ~${fee_usd:.4f} network fee = **${buffered_usd:.2f} total**",
        f"  Be transparent: explain it's a Bitcoin network fee, not your fee",
        f"  Best for: mid/high value orders where customers expect itemised costs\n",

        f"### Option 3 — Use economy speed (lowest fee)",
        f"  Economy fee rate: {fees['economy']} sat/vB → cost: **{_fee_in_sats(fees['economy']):,} sats** (${_sats_to_usd(_fee_in_sats(fees['economy']), btc_price):.4f} USD)",
        f"  Tradeoff: confirmation in a few hours instead of {speed_label}",
        f"  Best for: digital goods where instant delivery isn't required\n",

        f"### Option 4 — Set a minimum order value",
        f"  Rule of thumb: minimum order = fee × 20 (fee is < 5% of order)",
        f"  At current fees: minimum order = **${fee_usd * 20:.2f} USD**",
        f"  During high fee periods, display: 'Minimum order for Bitcoin payment: ${fee_usd * 20:.2f}'\n",

        f"### Option 5 — Encourage SegWit addresses",
        f"  If your customer pays from a SegWit wallet (bc1... address), their transaction is smaller",
        f"  SegWit fee at {fee_rate} sat/vB: **{fee_sats_segwit:,} sats** (${fee_usd_segwit:.4f} USD) — saves ${fee_usd - fee_usd_segwit:.4f}",
        f"  You can't force it, but you can add a note: 'Using a bc1... address reduces network fees'\n",

        f"### Checkout message templates",
        f"  Low fee environment:",
        f'    "Pay with Bitcoin — current network fee is just ${fee_usd:.3f}. Fast and cheap!"',
        f"  High fee environment:",
        f'    "Bitcoin network fees are currently elevated (${fee_usd:.3f}). Economy speed available — your payment will confirm within a few hours at lower cost."',
        f"  Customer-facing fee explainer:",
        f'    "The network fee is paid to Bitcoin miners to process your transaction — it\'s not charged by us. Think of it like a small postage stamp for your payment."',
    ]

    return "\n".join(lines)


def get_customer_fee_explainer(fee_amount_usd: float | None = None) -> str:
    """
    Plain-English fee explanation designed to be shown directly to customers.
    """
    fees = _fetch_fees()
    btc_price = _fetch_btc_price_usd()
    mempool = _fetch_mempool()

    if fee_amount_usd is None:
        fee_sats = _fee_in_sats(fees["hour"])
        fee_amount_usd = _sats_to_usd(fee_sats, btc_price)

    is_high = fees["fastest"] >= 50
    congestion_note = (
        "The Bitcoin network is currently **busy** — fees are higher than usual. "
        "Choosing the economy option below will save you money, but your order will confirm in a few hours instead of minutes."
        if is_high else
        "The Bitcoin network is currently **quiet** — fees are low. Any speed option works great right now."
    )

    return f"""\
## Understanding Your Bitcoin Payment Fee

**What is this fee?**
When you send Bitcoin, a small amount goes to the computers (called miners) \
that process and verify your payment on the blockchain. \
This is called a **network fee** — it's not charged by the merchant or the payment gateway.

Think of it like a stamp on a letter — you pay a little to get it delivered.

---

**Current fee: ~${fee_amount_usd:.3f} USD**

{congestion_note}

---

**Your options:**

| Option         | Fee        | Confirmation time | Best for                     |
|----------------|------------|-------------------|------------------------------|
| Express        | ${_sats_to_usd(_fee_in_sats(fees["fastest"]), btc_price):.3f}      | ~10 minutes       | Urgent payments              |
| Standard       | ${_sats_to_usd(_fee_in_sats(fees["hour"]), btc_price):.3f}      | ~1 hour           | Most purchases               |
| Economy        | ${_sats_to_usd(_fee_in_sats(fees["economy"]), btc_price):.3f}      | Few hours         | Digital goods, no rush       |

---

**Common questions:**

- **"Can I avoid the fee?"**
  No — this fee goes to the Bitcoin network, not to the merchant. There's no way to bypass it.
  Lightning Network payments have near-zero fees if your wallet supports it.

- **"Why did the fee change?"**
  Bitcoin fees change based on how many people are sending transactions right now.
  Busy times = higher fees. Quiet times = lower fees.

- **"My transaction is taking longer than expected"**
  If you chose a low fee during a busy period, your transaction may be in a queue.
  It will confirm eventually — you can track it at mempool.space using your transaction ID.

- **"The fee seems higher than the item I'm buying"**
  Bitcoin on-chain payments work best for orders above ${_sats_to_usd(_fee_in_sats(fees["fastest"]), btc_price) * 20:.2f}.
  For smaller amounts, ask the merchant if they accept Lightning Network payments (fees < $0.01).

---
**Track your payment live:** https://mempool.space
(Paste your transaction ID after paying to see real-time confirmation status)
"""


def get_all_fee_rates() -> str:
    """Return current live fee rates with plain-English context."""
    fees = _fetch_fees()
    btc_price = _fetch_btc_price_usd()
    mempool = _fetch_mempool()
    congestion = _congestion_label(fees)

    lines = [
        f"## Live Bitcoin Network Fees — {_now()}",
        f"**Network congestion:** {congestion}",
        f"**Pending transactions in mempool:** {mempool['pending_tx']:,}",
        f"**BTC price:** ${btc_price:,.2f}\n",
        f"{'Speed':<22} {'Rate':>10} {'Cost (USD)':>12} {'Time':>12}",
        "-" * 60,
    ]

    for label, key, time_str in [
        ("Express (next block)", "fastest",   "~10 min"),
        ("Fast (~30 min)",       "half_hour", "~30 min"),
        ("Standard (~1 hr)",     "hour",      "~1 hr"),
        ("Economy (few hrs)",    "economy",   "few hours"),
        ("Minimum relay",        "minimum",   "may be stuck"),
    ]:
        rate = fees[key]
        fee_sats = _fee_in_sats(rate)
        fee_usd = _sats_to_usd(fee_sats, btc_price)
        lines.append(f"{label:<22} {rate:>7} s/vB  ${fee_usd:>8.4f}    {time_str:>12}")

    lines += [
        f"\n**What these mean for a typical transaction (~225 vBytes):**",
        f"- SegWit transactions (~140 vBytes) cost ~40% less than legacy transactions",
        f"- Fees are fixed per transaction regardless of payment amount",
        f"- Fees fluctuate — check again before setting invoice amounts",
        f"\n**Merchant tip:** Set your payment timeout to at least 30 minutes so customers ",
        f"have time to complete payment even at economy speed.",
    ]

    return "\n".join(lines)


# ── MCP server entry point (Python 3.10+ only) ──────────────────────────────
# Uncomment when mcp package is available:
#
# from mcp.server.fastmcp import FastMCP
# mcp = FastMCP("bitcoin-fee-advisor")
#
# @mcp.tool()
# def explain_fees() -> str:
#     """Explain what Bitcoin network fees are in plain English, with current rates."""
#     return explain_bitcoin_fees()
#
# @mcp.tool()
# def fee_impact_for_product(product_price_usd: float) -> str:
#     """Show how current fees impact a specific product price, with pricing advice."""
#     return get_fee_impact_by_product(product_price_usd)
#
# @mcp.tool()
# def fee_adjustment_guide(product_price_usd: float, confirmation_speed: str = "hour") -> str:
#     """Get a concrete action plan for adjusting prices and checkout based on current fees."""
#     return get_fee_adjustment_guide(product_price_usd, confirmation_speed)
#
# @mcp.tool()
# def customer_fee_explainer(fee_amount_usd: float = 0) -> str:
#     """Get a customer-facing plain-English explanation of the Bitcoin fee."""
#     return get_customer_fee_explainer(fee_amount_usd or None)
#
# @mcp.tool()
# def current_fee_rates() -> str:
#     """Get all current live Bitcoin fee rates with plain-English context."""
#     return get_all_fee_rates()
#
# if __name__ == "__main__":
#     mcp.run()
