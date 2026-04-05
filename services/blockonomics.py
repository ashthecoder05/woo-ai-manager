from __future__ import annotations
import httpx
from config import BLOCKONOMICS_API_KEY, BLOCKONOMICS_BASE_URL, CACHE_TTL_SECONDS
from services import cache

_HEADERS = {"Authorization": f"Bearer {BLOCKONOMICS_API_KEY}"}


def _get(path: str, params: dict | None = None) -> dict:
    cache_key = f"{path}:{params}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    url = f"{BLOCKONOMICS_BASE_URL}{path}"
    with httpx.Client(timeout=10) as client:
        resp = client.get(url, headers=_HEADERS, params=params)
        resp.raise_for_status()
        data = resp.json()

    cache.set(cache_key, data, CACHE_TTL_SECONDS)
    return data


def get_balance(address: str) -> dict:
    """Get BTC balance for a Bitcoin address."""
    data = _get("/balance", params={"addr": address})
    # Return only safe fields
    if "response" in data and isinstance(data["response"], list):
        entries = data["response"]
        if entries:
            entry = entries[0]
            return {
                "address": address,
                "confirmed": entry.get("confirmed", 0),
                "unconfirmed": entry.get("unconfirmed", 0),
            }
    return {"address": address, "confirmed": 0, "unconfirmed": 0}


def get_transactions(address: str) -> list[dict]:
    """Get recent transactions for a Bitcoin address."""
    data = _get("/searchhistory", params={"addr": address})
    txs = data.get("history", [])
    safe = []
    for tx in txs[:10]:  # limit to 10
        safe.append({
            "txid": tx.get("txid", ""),
            "value": tx.get("value", 0),
            "time": tx.get("time", 0),
            "confirmations": tx.get("confirmations", 0),
        })
    return safe


def get_price() -> dict:
    """Get current BTC price in USD."""
    data = _get("/price", params={"currency": "USD"})
    return {"usd": data.get("price", 0)}
