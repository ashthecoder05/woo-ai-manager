from __future__ import annotations
"""
mempool.space blockchain intelligence service.

Provides fee monitoring, transaction lookup, and mempool congestion data
without requiring an API key (mempool.space is a public API).
"""

import time
import httpx
from services import cache

_BASE = "https://mempool.space/api"
_CACHE_SHORT = 15   # seconds — fees & mempool change quickly
_CACHE_LONG = 300   # seconds — confirmed tx data is stable


def _get(path: str, ttl: int = _CACHE_SHORT) -> dict | list:
    cached = cache.get(path)
    if cached is not None:
        return cached
    with httpx.Client(timeout=10) as client:
        resp = client.get(f"{_BASE}{path}")
        resp.raise_for_status()
        data = resp.json()
    cache.set(path, data, ttl)
    return data


# ---------------------------------------------------------------------------
# Fee Monitoring
# ---------------------------------------------------------------------------

def get_recommended_fees() -> dict:
    """
    Returns sat/vByte estimates for different confirmation targets.
    Source: mempool.space /api/v1/fees/recommended
    """
    data = _get("/v1/fees/recommended", ttl=_CACHE_SHORT)
    return {
        "fastest_fee":    data.get("fastestFee", 0),    # next block (~10 min)
        "half_hour_fee":  data.get("halfHourFee", 0),   # ~30 min
        "hour_fee":       data.get("hourFee", 0),        # ~1 hour
        "economy_fee":    data.get("economyFee", 0),     # ~few hours
        "minimum_fee":    data.get("minimumFee", 1),     # min relay fee
    }


def classify_fee(fee_rate: float) -> str:
    """Label a fee rate relative to current network conditions."""
    fees = get_recommended_fees()
    if fee_rate >= fees["fastest_fee"]:
        return "high (next block)"
    if fee_rate >= fees["hour_fee"]:
        return "medium (~1 hour)"
    if fee_rate >= fees["economy_fee"]:
        return "low (several hours)"
    return "very low (may be stuck)"


# ---------------------------------------------------------------------------
# Mempool Stats
# ---------------------------------------------------------------------------

def get_mempool_stats() -> dict:
    """
    Returns current mempool size, fee histogram, and congestion level.
    """
    data = _get("/mempool", ttl=_CACHE_SHORT)
    count = data.get("count", 0)
    vsize = data.get("vsize", 0)  # bytes of pending txs

    # Rough congestion labels
    if vsize > 50_000_000:
        congestion = "very high"
    elif vsize > 10_000_000:
        congestion = "high"
    elif vsize > 2_000_000:
        congestion = "moderate"
    else:
        congestion = "low"

    return {
        "pending_transactions": count,
        "pending_vsize_bytes": vsize,
        "congestion": congestion,
    }


# ---------------------------------------------------------------------------
# Transaction Lookup
# ---------------------------------------------------------------------------

def get_transaction(txid: str) -> dict:
    """
    Fetch full transaction details from mempool.space.
    Returns safe fields only.
    """
    data = _get(f"/tx/{txid}", ttl=_CACHE_LONG)
    status = data.get("status", {})
    fee = data.get("fee", 0)
    weight = data.get("weight", 1)
    vsize = max(weight // 4, 1)
    fee_rate = round(fee / vsize, 2) if fee else 0

    return {
        "txid": txid,
        "confirmed": status.get("confirmed", False),
        "block_height": status.get("block_height"),
        "block_time": status.get("block_time"),
        "fee_satoshis": fee,
        "fee_rate_sat_vbyte": fee_rate,
        "vsize_vbytes": vsize,
        "input_count": len(data.get("vin", [])),
        "output_count": len(data.get("vout", [])),
    }


def get_block_height() -> int:
    """Return the current Bitcoin block tip height."""
    return int(_get("/blocks/tip/height", ttl=_CACHE_SHORT))


# ---------------------------------------------------------------------------
# Underpayment Detection
# ---------------------------------------------------------------------------

def detect_underpayment(received_satoshis: int, expected_satoshis: int) -> dict:
    """
    Compare received vs expected amounts and classify the result.
    """
    diff = received_satoshis - expected_satoshis
    pct = (received_satoshis / expected_satoshis * 100) if expected_satoshis else 0

    if diff >= 0:
        status = "exact" if diff == 0 else "overpaid"
    elif abs(diff) <= 500:          # dust tolerance (< 500 sat)
        status = "dust_underpayment"
    elif pct >= 99:
        status = "minor_underpayment"
    else:
        status = "underpaid"

    return {
        "received_satoshis": received_satoshis,
        "expected_satoshis": expected_satoshis,
        "difference_satoshis": diff,
        "received_pct": round(pct, 2),
        "status": status,
    }


# ---------------------------------------------------------------------------
# Stuck Transaction Diagnosis
# ---------------------------------------------------------------------------

def diagnose_stuck_tx(txid: str) -> dict:
    """
    Diagnose why a transaction might be unconfirmed or stuck.
    Compares its fee rate to current network recommendations.
    """
    tx = get_transaction(txid)
    fees = get_recommended_fees()
    mempool = get_mempool_stats()

    fee_rate = tx["fee_rate_sat_vbyte"]
    diagnosis: list[str] = []
    recommendation: str = ""

    if tx["confirmed"]:
        return {
            "txid": txid,
            "confirmed": True,
            "block_height": tx["block_height"],
            "diagnosis": "Transaction is confirmed.",
            "recommendation": "No action needed.",
        }

    # Fee rate comparison
    if fee_rate < fees["minimum_fee"]:
        diagnosis.append(f"Fee rate ({fee_rate} sat/vB) is below the network minimum ({fees['minimum_fee']} sat/vB).")
        recommendation = "This transaction may never confirm. Consider using CPFP (Child Pays For Parent) or contact your wallet for RBF (Replace-By-Fee)."
    elif fee_rate < fees["economy_fee"]:
        diagnosis.append(f"Fee rate ({fee_rate} sat/vB) is very low — economy rate is {fees['economy_fee']} sat/vB.")
        recommendation = f"Use CPFP or RBF to bump the fee to at least {fees['hour_fee']} sat/vB for ~1 hour confirmation."
    elif fee_rate < fees["hour_fee"]:
        diagnosis.append(f"Fee rate ({fee_rate} sat/vB) is below the 1-hour target ({fees['hour_fee']} sat/vB).")
        recommendation = f"Consider bumping to {fees['half_hour_fee']} sat/vB for a ~30 minute confirmation."
    else:
        diagnosis.append(f"Fee rate ({fee_rate} sat/vB) looks adequate.")
        recommendation = "Network may be temporarily congested. Wait a bit longer."

    if mempool["congestion"] in ("high", "very high"):
        diagnosis.append(f"Mempool is currently {mempool['congestion']} ({mempool['pending_transactions']:,} pending transactions).")

    return {
        "txid": txid,
        "confirmed": False,
        "fee_rate_sat_vbyte": fee_rate,
        "network_fastest_fee": fees["fastest_fee"],
        "network_hour_fee": fees["hour_fee"],
        "network_economy_fee": fees["economy_fee"],
        "mempool_congestion": mempool["congestion"],
        "diagnosis": " ".join(diagnosis),
        "recommendation": recommendation,
    }
