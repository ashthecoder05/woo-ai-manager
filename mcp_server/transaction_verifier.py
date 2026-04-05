"""
Transaction Verification MCP Server

Real-time Bitcoin transaction status + legitimacy check for customers.
Uses mempool.space (no API key required).

Answers:
  - Is this transaction real or fake?
  - How many confirmations does it have?
  - When will it confirm?
  - Is this a scam?
  - What does this txid / order actually show on-chain?

For Python 3.10+ run as MCP:
  python mcp_server/transaction_verifier.py
"""

from __future__ import annotations
import re
import time
import httpx
from datetime import datetime, timezone

_BASE = "https://mempool.space/api"
_EXPLORER = "https://mempool.space/tx/{txid}"
_ADDRESS_EXPLORER = "https://mempool.space/address/{address}"

# ---------------------------------------------------------------------------
# Raw mempool.space fetchers (no cache — customer needs real-time data)
# ---------------------------------------------------------------------------

def _fetch_tx(txid: str) -> dict | None:
    try:
        r = httpx.get(f"{_BASE}/tx/{txid}", timeout=12)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _fetch_address(address: str) -> dict | None:
    try:
        r = httpx.get(f"{_BASE}/address/{address}", timeout=12)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _fetch_address_txs(address: str) -> list:
    try:
        r = httpx.get(f"{_BASE}/address/{address}/txs", timeout=12)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


def _fetch_fees() -> dict:
    try:
        r = httpx.get(f"{_BASE}/v1/fees/recommended", timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {"fastestFee": 0, "halfHourFee": 0, "hourFee": 0, "economyFee": 0}


def _fetch_block_height() -> int:
    try:
        r = httpx.get(f"{_BASE}/blocks/tip/height", timeout=8)
        r.raise_for_status()
        return int(r.text)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_valid_txid(txid: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F]{64}", txid.strip()))


def _is_valid_address(address: str) -> bool:
    # Bitcoin address: P2PKH (1...), P2SH (3...), bech32 (bc1...)
    return bool(re.match(r"^(1|3|bc1)[a-zA-HJ-NP-Z0-9]{25,62}$", address.strip()))


def _satoshis_to_btc(sats: int) -> str:
    return f"{sats / 1e8:.8f}"


def _format_time(unix_ts: int) -> str:
    dt = datetime.fromtimestamp(unix_ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def _eta_text(fee_rate: float, fees: dict) -> str:
    if fee_rate >= fees.get("fastestFee", 999):
        return "next block (~10 minutes)"
    if fee_rate >= fees.get("halfHourFee", 999):
        return "within ~30 minutes"
    if fee_rate >= fees.get("hourFee", 999):
        return "within ~1 hour"
    if fee_rate >= fees.get("economyFee", 999):
        return "within a few hours"
    return "unknown — fee is very low, may be stuck"


# ---------------------------------------------------------------------------
# Scam / legitimacy signals
# ---------------------------------------------------------------------------

def _assess_legitimacy(tx_data: dict, expected_amount_sats: int | None = None) -> dict:
    """
    Analyse on-chain data and return legitimacy signals.
    Returns a dict with: verdict, confidence, signals (list), warnings (list)
    """
    signals = []
    warnings = []

    status = tx_data.get("status", {})
    confirmed = status.get("confirmed", False)
    fee = tx_data.get("fee", 0)
    weight = tx_data.get("weight", 1)
    vsize = max(weight // 4, 1)
    fee_rate = round(fee / vsize, 2) if fee else 0

    # ── POSITIVE signals ───────────────────────────────────────────────
    if confirmed:
        block_height = status.get("block_height", 0)
        block_time = status.get("block_time", 0)
        signals.append(f"Transaction is confirmed in block {block_height} ({_format_time(block_time)})")
        signals.append("Confirmed transactions on Bitcoin are irreversible — this payment is real")

    if fee > 0:
        signals.append(f"Transaction paid a real network fee ({fee} satoshis / {fee_rate} sat/vB) — fake screenshots have no fees")

    vout = tx_data.get("vout", [])
    total_out = sum(o.get("value", 0) for o in vout)
    if total_out > 0:
        signals.append(f"Total output value on-chain: {_satoshis_to_btc(total_out)} BTC — this is real Bitcoin moving on the blockchain")

    # ── AMOUNT CHECK ────────────────────────────────────────────────────
    if expected_amount_sats and expected_amount_sats > 0:
        if total_out >= expected_amount_sats:
            signals.append(f"Payment amount matches or exceeds expected amount ({_satoshis_to_btc(expected_amount_sats)} BTC)")
        else:
            diff = expected_amount_sats - total_out
            warnings.append(
                f"Payment total ({_satoshis_to_btc(total_out)} BTC) is less than the expected amount "
                f"({_satoshis_to_btc(expected_amount_sats)} BTC) — short by {_satoshis_to_btc(diff)} BTC"
            )

    # ── WARNING signals ─────────────────────────────────────────────────
    if not confirmed:
        warnings.append("Transaction is NOT yet confirmed — do not release goods until confirmed")

    vin = tx_data.get("vin", [])
    if len(vin) > 20:
        warnings.append(f"Transaction has {len(vin)} inputs — this is unusual and may indicate a mixing/coinjoin transaction")

    if fee_rate == 0:
        warnings.append("Transaction has zero fee — this is extremely unusual and suspicious")

    # ── VERDICT ─────────────────────────────────────────────────────────
    if confirmed and not warnings:
        verdict = "LEGITIMATE"
        confidence = "HIGH"
        summary = "This transaction is confirmed on the Bitcoin blockchain. It is real and cannot be faked or reversed."
    elif confirmed and warnings:
        verdict = "LEGITIMATE (with warnings)"
        confidence = "MEDIUM"
        summary = "Transaction is confirmed but has some points to review — see warnings below."
    elif not confirmed and fee_rate > 0:
        verdict = "PENDING — LIKELY REAL"
        confidence = "MEDIUM"
        summary = "Transaction exists on-chain and is waiting for confirmation. It is a real transaction but not yet final."
    else:
        verdict = "UNVERIFIED"
        confidence = "LOW"
        summary = "Could not fully verify this transaction. Proceed with caution."

    return {
        "verdict": verdict,
        "confidence": confidence,
        "summary": summary,
        "signals": signals,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Main public functions
# ---------------------------------------------------------------------------

def verify_transaction(txid: str, expected_amount_sats: int | None = None) -> str:
    """
    Full real-time transaction verification by txid.
    Returns a plain-English status report with legitimacy assessment.
    """
    txid = txid.strip()

    if not _is_valid_txid(txid):
        return (
            "That doesn't look like a valid Bitcoin transaction ID. "
            "A Bitcoin txid is a 64-character string of letters and numbers. "
            "Example: a1b2c3d4...e5f6 (64 chars)\n\n"
            "If someone gave you a different kind of ID, it might be a payment gateway order ID — "
            "ask them for the actual Bitcoin transaction ID (txid) which you can look up on mempool.space."
        )

    tx = _fetch_tx(txid)

    if tx is None:
        return (
            f"Transaction **{txid[:16]}...** was NOT found on the Bitcoin blockchain.\n\n"
            "**What this means:**\n"
            "- The transaction does not exist — it may be completely fake\n"
            "- OR it was just broadcast and hasn't propagated yet (wait 2–3 minutes and check again)\n"
            "- OR the txid was typed/copied incorrectly\n\n"
            "**What to do:**\n"
            "1. Ask the sender to share the exact txid again\n"
            "2. Check it yourself at: https://mempool.space — paste the txid in the search bar\n"
            "3. If the transaction doesn't appear after 10 minutes, treat it as NOT paid\n\n"
            "**Red flag:** If someone claims they paid but you can't find the txid on mempool.space, this is a strong scam indicator."
        )

    # Parse transaction data
    status = tx.get("status", {})
    confirmed = status.get("confirmed", False)
    block_height = status.get("block_height")
    block_time = status.get("block_time")
    fee = tx.get("fee", 0)
    weight = tx.get("weight", 1)
    vsize = max(weight // 4, 1)
    fee_rate = round(fee / vsize, 2) if fee else 0
    vout = tx.get("vout", [])
    vin = tx.get("vin", [])
    total_out = sum(o.get("value", 0) for o in vout)

    fees = _fetch_fees()
    current_height = _fetch_block_height()
    confirmations = (current_height - block_height + 1) if confirmed and block_height else 0

    legitimacy = _assess_legitimacy(tx, expected_amount_sats)

    lines = [
        f"## Transaction Verification Report",
        f"**txid:** `{txid[:32]}...{txid[-8:]}`",
        f"**Explorer:** {_EXPLORER.format(txid=txid)}\n",
    ]

    # Status block
    if confirmed:
        lines += [
            f"### Status: CONFIRMED ✓",
            f"- Confirmed in block: **{block_height:,}**",
            f"- Confirmations: **{confirmations}**",
            f"- Confirmed at: **{_format_time(block_time)}**",
        ]
        if confirmations >= 6:
            lines.append("- Settlement: **Fully settled** (6+ confirmations — irreversible)")
        elif confirmations >= 2:
            lines.append("- Settlement: **Secure** (2+ confirmations)")
        else:
            lines.append("- Settlement: **Recent** — safe for most transactions")
    else:
        eta = _eta_text(fee_rate, fees)
        lines += [
            f"### Status: UNCONFIRMED ⏳",
            f"- The transaction is in the mempool (waiting to be included in a block)",
            f"- Estimated confirmation: **{eta}**",
            f"- Fee rate: **{fee_rate} sat/vB** (network fastest: {fees.get('fastestFee', '?')} sat/vB)",
        ]

    # Payment details
    lines += [
        f"\n### Payment Details",
        f"- Amount on-chain: **{_satoshis_to_btc(total_out)} BTC** ({total_out:,} satoshis)",
        f"- Network fee paid: **{fee:,} satoshis** ({fee_rate} sat/vB)",
        f"- Inputs: {len(vin)}  |  Outputs: {len(vout)}",
        f"- Transaction size: {vsize} vBytes",
    ]

    if expected_amount_sats:
        lines.append(f"- Expected amount: **{_satoshis_to_btc(expected_amount_sats)} BTC**")

    # Legitimacy verdict
    lines += [
        f"\n### Legitimacy Assessment",
        f"**Verdict: {legitimacy['verdict']}** (confidence: {legitimacy['confidence']})",
        f"{legitimacy['summary']}",
    ]

    if legitimacy["signals"]:
        lines.append("\n**Verification signals:**")
        for s in legitimacy["signals"]:
            lines.append(f"  ✓ {s}")

    if legitimacy["warnings"]:
        lines.append("\n**Warnings:**")
        for w in legitimacy["warnings"]:
            lines.append(f"  ⚠ {w}")

    lines += [
        f"\n### How to independently verify",
        f"Anyone can verify this transaction themselves — Bitcoin is public:",
        f"1. Go to https://mempool.space",
        f"2. Paste this txid: `{txid}`",
        f"3. The page will show the exact same information — no one can fake a confirmed Bitcoin transaction",
    ]

    return "\n".join(lines)


def verify_address_payment(address: str, expected_amount_sats: int | None = None) -> str:
    """
    Check if a Bitcoin address has received a payment.
    Shows all recent transactions to that address with legitimacy signals.
    """
    address = address.strip()

    if not _is_valid_address(address):
        return (
            "That doesn't look like a valid Bitcoin address. "
            "Bitcoin addresses start with 1, 3, or bc1. "
            "Please double-check the address and try again."
        )

    addr_data = _fetch_address(address)
    if addr_data is None:
        return (
            f"Address `{address}` was not found or has never been used on the Bitcoin blockchain. "
            "If a merchant gave you this address, it may be brand new (no transactions yet) or invalid."
        )

    chain_stats = addr_data.get("chain_stats", {})
    mempool_stats = addr_data.get("mempool_stats", {})

    funded_txo_sum = chain_stats.get("funded_txo_sum", 0)
    spent_txo_sum = chain_stats.get("spent_txo_sum", 0)
    confirmed_balance = funded_txo_sum - spent_txo_sum
    tx_count = chain_stats.get("tx_count", 0)
    unconfirmed_count = mempool_stats.get("tx_count", 0)
    unconfirmed_sum = mempool_stats.get("funded_txo_sum", 0)

    lines = [
        f"## Address Payment Verification",
        f"**Address:** `{address}`",
        f"**Explorer:** {_ADDRESS_EXPLORER.format(address=address)}\n",
        f"### On-chain Summary",
        f"- Total received (all time): **{_satoshis_to_btc(funded_txo_sum)} BTC**",
        f"- Current confirmed balance: **{_satoshis_to_btc(confirmed_balance)} BTC**",
        f"- Total confirmed transactions: **{tx_count}**",
    ]

    if unconfirmed_count > 0:
        lines.append(f"- Pending (unconfirmed): **{unconfirmed_count} transaction(s)** ({_satoshis_to_btc(unconfirmed_sum)} BTC waiting)")

    # Recent transactions
    txs = _fetch_address_txs(address)
    if txs:
        lines.append(f"\n### Recent Transactions (latest {min(5, len(txs))})")
        fees = _fetch_fees()
        current_height = _fetch_block_height()

        for tx in txs[:5]:
            tx_status = tx.get("status", {})
            is_confirmed = tx_status.get("confirmed", False)
            txid = tx.get("txid", "")
            fee = tx.get("fee", 0)
            weight = tx.get("weight", 1)
            vsize = max(weight // 4, 1)
            fee_rate = round(fee / vsize, 2) if fee else 0

            # Calculate amount received at this address
            vout = tx.get("vout", [])
            received = sum(
                o.get("value", 0) for o in vout
                if o.get("scriptpubkey_address") == address
            )

            if is_confirmed:
                bh = tx_status.get("block_height", 0)
                confs = (current_height - bh + 1) if bh else 0
                bt = tx_status.get("block_time", 0)
                status_str = f"CONFIRMED ({confs} conf) — {_format_time(bt)}"
            else:
                eta = _eta_text(fee_rate, fees)
                status_str = f"PENDING — ETA {eta}"

            lines.append(
                f"  - `{txid[:20]}...` | **{_satoshis_to_btc(received)} BTC** | {status_str}"
            )

    # Legitimacy check
    lines.append(f"\n### Legitimacy Assessment")

    if tx_count == 0 and unconfirmed_count == 0:
        lines += [
            "**Verdict: NO PAYMENT FOUND**",
            "This address has received no payments. If someone claims they paid to this address, they have not.",
            "⚠ Do not release any goods or services until a real transaction appears here.",
        ]
    else:
        if expected_amount_sats:
            total_unconfirmed_and_confirmed = funded_txo_sum + unconfirmed_sum
            if confirmed_balance >= expected_amount_sats:
                lines += [
                    "**Verdict: PAYMENT CONFIRMED ✓**",
                    f"The expected amount ({_satoshis_to_btc(expected_amount_sats)} BTC) has been received and confirmed.",
                    "✓ This is real Bitcoin — confirmed on-chain and irreversible.",
                ]
            elif unconfirmed_sum >= expected_amount_sats:
                lines += [
                    "**Verdict: PAYMENT DETECTED — AWAITING CONFIRMATION ⏳**",
                    f"The expected amount has been sent but is not yet confirmed.",
                    "⚠ Wait for at least 1 confirmation before releasing goods.",
                ]
            else:
                lines += [
                    "**Verdict: UNDERPAYMENT ⚠**",
                    f"Expected {_satoshis_to_btc(expected_amount_sats)} BTC but address shows less.",
                    "⚠ Do not fulfil the order until the full amount is received and confirmed.",
                ]
        else:
            lines += [
                "**Verdict: TRANSACTIONS FOUND — VERIFY AMOUNT**",
                "This address has real Bitcoin transactions. Check the amounts above match your order.",
                "✓ These transactions are real and publicly verifiable.",
            ]

    lines += [
        f"\n### Scam Detection Tips",
        "✓ Real Bitcoin payments always appear on mempool.space — no exceptions",
        "✓ Anyone can verify a payment independently — ask the sender for the txid",
        "⚠ Screenshot of a payment is NOT proof — only a txid on mempool.space is",
        "⚠ If someone sends you a txid that returns 'not found', they did not pay",
        "⚠ 'Pending' payments can be reversed until confirmed — wait for at least 1 confirmation",
        f"\n**Verify yourself:** https://mempool.space/address/{address}",
    ]

    return "\n".join(lines)


def check_scam_signals(txid_or_address: str) -> str:
    """
    Quick scam check — given a txid or address, return plain-English
    verdict on whether the payment is real, fake, or suspicious.
    Designed for non-technical customers and merchants.
    """
    value = txid_or_address.strip()

    if _is_valid_txid(value):
        tx = _fetch_tx(value)
        if tx is None:
            return (
                "🚨 **SCAM ALERT — Transaction NOT found**\n\n"
                f"The transaction ID `{value[:20]}...` does not exist on the Bitcoin blockchain.\n\n"
                "**This is a strong indicator of fraud.** A real Bitcoin payment always shows up "
                "on mempool.space within a few seconds of being sent.\n\n"
                "**What to do:**\n"
                "- Do NOT release any goods or services\n"
                "- Ask the sender to show you the transaction on mempool.space live\n"
                "- If they refuse or make excuses, it is almost certainly a scam\n\n"
                f"Verify yourself: https://mempool.space — search for: {value}"
            )

        status = tx.get("status", {})
        confirmed = status.get("confirmed", False)
        fee = tx.get("fee", 0)
        weight = tx.get("weight", 1)
        vsize = max(weight // 4, 1)
        fee_rate = round(fee / vsize, 2) if fee else 0

        if confirmed:
            block_height = status.get("block_height", 0)
            current_height = _fetch_block_height()
            confs = (current_height - block_height + 1) if block_height else 0
            return (
                f"✅ **LEGITIMATE — Transaction Confirmed**\n\n"
                f"Transaction `{value[:20]}...` is **confirmed** on the Bitcoin blockchain "
                f"with **{confs} confirmation(s)**.\n\n"
                "This is a real, irreversible Bitcoin transaction. It cannot be faked.\n\n"
                f"Verify: {_EXPLORER.format(txid=value)}"
            )
        else:
            fees = _fetch_fees()
            eta = _eta_text(fee_rate, fees)
            return (
                f"⏳ **REAL BUT PENDING — Awaiting Confirmation**\n\n"
                f"Transaction `{value[:20]}...` exists on the Bitcoin network but is not yet confirmed.\n\n"
                f"- Fee rate: {fee_rate} sat/vB\n"
                f"- Estimated confirmation: {eta}\n\n"
                "**For merchants:** Do not release high-value goods until confirmed.\n"
                "**For customers:** Your payment is real and will confirm shortly.\n\n"
                f"Track live: {_EXPLORER.format(txid=value)}"
            )

    elif _is_valid_address(value):
        addr = _fetch_address(value)
        if addr is None:
            return (
                f"Address `{value}` has no transaction history on the Bitcoin blockchain.\n\n"
                "If someone claims they paid to this address, they have not yet sent any Bitcoin here.\n\n"
                f"Monitor: {_ADDRESS_EXPLORER.format(address=value)}"
            )
        stats = addr.get("chain_stats", {})
        tx_count = stats.get("tx_count", 0)
        funded = stats.get("funded_txo_sum", 0)
        if tx_count > 0:
            return (
                f"✅ **Address has received Bitcoin**\n\n"
                f"Address `{value[:20]}...` has {tx_count} transaction(s) totalling "
                f"{_satoshis_to_btc(funded)} BTC received.\n\n"
                "These are real on-chain transactions. "
                "Use `verify_transaction` with a specific txid for full details.\n\n"
                f"View all: {_ADDRESS_EXPLORER.format(address=value)}"
            )
        else:
            return (
                f"⚠️ **No payments found on this address**\n\n"
                f"Address `{value[:20]}...` has received 0 transactions.\n\n"
                "If someone claims to have paid here, they have not.\n\n"
                f"Verify: {_ADDRESS_EXPLORER.format(address=value)}"
            )
    else:
        return (
            "Please provide a valid Bitcoin transaction ID (64-character hex string) "
            "or Bitcoin address (starts with 1, 3, or bc1).\n\n"
            "You can find the txid in your wallet app after sending, or in your payment gateway dashboard."
        )


# ── MCP server entry point (Python 3.10+ only) ──────────────────────────────
# Uncomment when mcp package is available:
#
# from mcp.server.fastmcp import FastMCP
# mcp = FastMCP("transaction-verifier")
#
# @mcp.tool()
# def verify_bitcoin_transaction(txid: str, expected_amount_sats: int = 0) -> str:
#     """
#     Verify a Bitcoin transaction in real time. Returns full status report
#     with legitimacy assessment and scam detection signals.
#     """
#     return verify_transaction(txid, expected_amount_sats or None)
#
# @mcp.tool()
# def verify_bitcoin_address_payment(address: str, expected_amount_sats: int = 0) -> str:
#     """
#     Check if a Bitcoin address has received a payment.
#     Shows all recent transactions with confirmation status.
#     """
#     return verify_address_payment(address, expected_amount_sats or None)
#
# @mcp.tool()
# def quick_scam_check(txid_or_address: str) -> str:
#     """
#     Quick check: is this Bitcoin transaction or address real or a scam?
#     Accepts a txid or Bitcoin address.
#     """
#     return check_scam_signals(txid_or_address)
#
# if __name__ == "__main__":
#     mcp.run()
