"""
wc_api.py — WooCommerce REST API client.

All functions take (store_url, consumer_key, consumer_secret) and return
plain Python dicts/lists. Errors are returned as {"error": "..."} strings
so the AI can report them gracefully rather than crashing.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = 15  # seconds per WC API call


def _wc_url(store_url: str, path: str) -> tuple[str, dict]:
    """
    Return (url, base_params) for a WC REST API path.

    Uses the index.php?rest_route= form which works on ALL WordPress sites
    regardless of permalink settings. The pretty-URL form (/wp-json/) requires
    mod_rewrite / pretty permalinks to be enabled, which isn't always the case.
    """
    base = store_url.rstrip("/") + "/index.php"
    route = "/wc/v3/" + path.lstrip("/")
    return base, {"rest_route": route}


def _parse_wc_response(r: httpx.Response) -> Any:
    """
    Parse a WC REST API response, handling PHP warnings prepended to valid JSON.
    WooCommerce on PHP 7.x may emit PHP notices/warnings before the JSON body.
    """
    text = r.text
    # Fast path: clean JSON response
    if text and text[0] in ("{", "["):
        return r.json()
    # PHP warnings are prepended — find the first JSON object or array
    for start_char in ("{", "["):
        idx = text.find(start_char)
        if idx != -1:
            try:
                import json as _json
                return _json.loads(text[idx:])
            except Exception:
                pass
    # Couldn't extract JSON — raise so caller gets a clean error
    raise ValueError(f"Non-JSON response (HTTP {r.status_code}): {text[:120]}")


def _get(store_url: str, key: str, secret: str, path: str, params: dict | None = None) -> Any:
    url, base_params = _wc_url(store_url, path)
    all_params = {**base_params, **(params or {})}
    try:
        r = httpx.get(url, auth=(key, secret), params=all_params, timeout=_TIMEOUT, follow_redirects=True)
        r.raise_for_status()
        return _parse_wc_response(r)
    except httpx.ConnectError:
        logger.warning("WC API connection error: %s", url)
        return {"error": f"Could not connect to store at {store_url}. Is the store URL correct and publicly reachable?"}
    except httpx.TimeoutException:
        logger.warning("WC API timeout: %s", url)
        return {"error": f"Request to {store_url} timed out after {_TIMEOUT}s. Is the store running?"}
    except httpx.HTTPStatusError as e:
        logger.warning("WC API HTTP error %s: %s", e.response.status_code, url)
        if e.response.status_code == 401:
            return {"error": "Invalid Consumer Key or Secret — WC returned 401 Unauthorized."}
        return {"error": f"WC API returned HTTP {e.response.status_code}. Check credentials."}
    except Exception as e:
        logger.error("WC API error (%s): %s", url, e)
        return {"error": str(e)}


def _post(store_url: str, key: str, secret: str, path: str, body: dict) -> Any:
    url, base_params = _wc_url(store_url, path)
    try:
        r = httpx.post(url, auth=(key, secret), params=base_params, json=body, timeout=_TIMEOUT, follow_redirects=True)
        r.raise_for_status()
        return _parse_wc_response(r)
    except httpx.HTTPStatusError as e:
        try:
            detail = _parse_wc_response(e.response).get("message", str(e))
        except Exception:
            detail = str(e)
        return {"error": detail}
    except httpx.TimeoutException:
        return {"error": f"Request to {store_url} timed out."}
    except Exception as e:
        return {"error": str(e)}


def _put(store_url: str, key: str, secret: str, path: str, body: dict) -> Any:
    url, base_params = _wc_url(store_url, path)
    try:
        r = httpx.put(url, auth=(key, secret), params=base_params, json=body, timeout=_TIMEOUT, follow_redirects=True)
        r.raise_for_status()
        return _parse_wc_response(r)
    except httpx.HTTPStatusError as e:
        try:
            detail = _parse_wc_response(e.response).get("message", str(e))
        except Exception:
            detail = str(e)
        return {"error": detail}
    except httpx.TimeoutException:
        return {"error": f"Request to {store_url} timed out."}
    except Exception as e:
        return {"error": str(e)}


def _date_range(period: str) -> tuple[str, str]:
    """Return (date_min, date_max) ISO strings for a named period."""
    now = datetime.now(tz=timezone.utc)
    today = now.date()
    if period == "today":
        return str(today), str(today)
    if period == "7d":
        return str(today - timedelta(days=7)), str(today)
    if period == "14d":
        return str(today - timedelta(days=14)), str(today)
    if period == "30d":
        return str(today - timedelta(days=30)), str(today)
    if period == "prior_7d":
        return str(today - timedelta(days=14)), str(today - timedelta(days=7))
    if period == "prior_30d":
        return str(today - timedelta(days=60)), str(today - timedelta(days=30))
    # fallback
    return str(today - timedelta(days=30)), str(today)


# ── Public tool functions ──────────────────────────────────────────────────────

def get_revenue(store_url: str, key: str, secret: str, period: str = "30d") -> str:
    """Get revenue summary for a time period."""
    date_min, date_max = _date_range(period)
    data = _get(store_url, key, secret, "reports/sales", {
        "date_min": date_min,
        "date_max": date_max,
    })
    if isinstance(data, dict) and "error" in data:
        return data["error"]
    # WC returns a list with one summary object
    if isinstance(data, list) and data:
        s = data[0]
        return json.dumps({
            "period": period,
            "date_range": f"{date_min} to {date_max}",
            "total_sales": s.get("total_sales"),
            "net_sales": s.get("net_sales"),
            "total_orders": s.get("total_orders"),
            "total_items": s.get("total_items"),
            "total_refunds": s.get("total_refunds"),
            "total_discount": s.get("total_discount"),
            "total_shipping": s.get("total_shipping"),
            "total_tax": s.get("total_tax"),
            "average_sales": s.get("average_sales"),
        })
    return json.dumps({"period": period, "date_range": f"{date_min} to {date_max}", "note": "No data"})


def get_orders(
    store_url: str, key: str, secret: str,
    status: str = "",
    limit: int = 10,
    after: str = "",
    before: str = "",
    customer: int = 0,
    search: str = "",
) -> str:
    """Get a list of orders with optional filters."""
    params: dict = {"per_page": min(limit, 50), "orderby": "date", "order": "desc"}
    if status:
        params["status"] = status
    if after:
        params["after"] = after
    if before:
        params["before"] = before
    if customer:
        params["customer"] = customer
    if search:
        params["search"] = search

    data = _get(store_url, key, secret, "orders", params)
    if isinstance(data, dict) and "error" in data:
        return data["error"]

    orders = []
    for o in (data or []):
        orders.append({
            "id": o.get("id"),
            "status": o.get("status"),
            "total": o.get("total"),
            "currency": o.get("currency"),
            "customer_name": f"{o.get('billing', {}).get('first_name', '')} {o.get('billing', {}).get('last_name', '')}".strip() or o.get("billing", {}).get("email", "Guest"),
            "customer_email": o.get("billing", {}).get("email", ""),
            "date_created": o.get("date_created", "")[:10],
            "items": [{"name": i.get("name"), "quantity": i.get("quantity"), "total": i.get("total")} for i in o.get("line_items", [])],
            "payment_method": o.get("payment_method_title", ""),
        })
    return json.dumps({"count": len(orders), "orders": orders})


def get_products(
    store_url: str, key: str, secret: str,
    status: str = "publish",
    stock_status: str = "",
    low_stock: bool = False,
    limit: int = 10,
    search: str = "",
    category: str = "",
) -> str:
    """Get a list of products."""
    params: dict = {"per_page": min(limit, 50), "status": status}
    if stock_status:
        params["stock_status"] = stock_status
    if low_stock:
        params["low_in_stock"] = True
    if search:
        params["search"] = search
    if category:
        params["category"] = category

    data = _get(store_url, key, secret, "products", params)
    if isinstance(data, dict) and "error" in data:
        return data["error"]

    products = []
    for p in (data or []):
        products.append({
            "id": p.get("id"),
            "name": p.get("name"),
            "status": p.get("status"),
            "price": p.get("price"),
            "regular_price": p.get("regular_price"),
            "sale_price": p.get("sale_price"),
            "stock_status": p.get("stock_status"),
            "stock_quantity": p.get("stock_quantity"),
            "manage_stock": p.get("manage_stock"),
            "total_sales": p.get("total_sales"),
            "categories": [c.get("name") for c in p.get("categories", [])],
        })
    return json.dumps({"count": len(products), "products": products})


def get_top_products(store_url: str, key: str, secret: str, period: str = "30d", limit: int = 5) -> str:
    """Get best-selling products."""
    wc_period_map = {"7d": "week", "30d": "month", "90d": "year"}
    wc_period = wc_period_map.get(period, "month")
    data = _get(store_url, key, secret, "reports/top_sellers", {
        "period": wc_period,
        "per_page": min(limit, 20),
    })
    if isinstance(data, dict) and "error" in data:
        return data["error"]

    results = []
    for item in (data or []):
        results.append({
            "product_id": item.get("product_id"),
            "name": item.get("name"),
            "quantity": item.get("quantity"),
        })
    return json.dumps({"period": period, "top_sellers": results})


def get_customers(
    store_url: str, key: str, secret: str,
    limit: int = 10,
    search: str = "",
    orderby: str = "registered_date",
    order: str = "desc",
) -> str:
    """Get a list of customers."""
    params: dict = {"per_page": min(limit, 50), "orderby": orderby, "order": order}
    if search:
        params["search"] = search

    data = _get(store_url, key, secret, "customers", params)
    if isinstance(data, dict) and "error" in data:
        return data["error"]

    customers = []
    for c in (data or []):
        customers.append({
            "id": c.get("id"),
            "name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip(),
            "email": c.get("email"),
            "orders_count": c.get("orders_count"),
            "total_spent": c.get("total_spent"),
            "date_created": (c.get("date_created") or "")[:10],
            "last_order_date": (c.get("last_order", {}) or {}).get("date_created_gmt", "")[:10],
            "city": c.get("billing", {}).get("city", ""),
            "country": c.get("billing", {}).get("country", ""),
        })
    return json.dumps({"count": len(customers), "customers": customers})


def create_coupon(
    store_url: str, key: str, secret: str,
    code: str,
    discount_type: str,
    amount: str,
    minimum_amount: str = "",
    expiry_date: str = "",
    usage_limit: int = 0,
) -> str:
    """Create a WooCommerce coupon."""
    body: dict = {
        "code": code,
        "discount_type": discount_type,
        "amount": amount,
    }
    if minimum_amount:
        body["minimum_amount"] = minimum_amount
    if expiry_date:
        body["date_expires"] = expiry_date
    if usage_limit:
        body["usage_limit"] = usage_limit

    data = _post(store_url, key, secret, "coupons", body)
    if isinstance(data, dict) and "error" in data:
        return f"Failed to create coupon: {data['error']}"
    return json.dumps({
        "success": True,
        "coupon_id": data.get("id"),
        "code": data.get("code"),
        "discount_type": data.get("discount_type"),
        "amount": data.get("amount"),
        "expiry_date": data.get("date_expires"),
        "usage_limit": data.get("usage_limit"),
    })


def update_product(
    store_url: str, key: str, secret: str,
    product_id: int,
    regular_price: str = None,
    sale_price: str = None,
    stock_quantity: int = None,
    stock_status: str = None,
    status: str = None,
) -> str:
    """Update a WooCommerce product."""
    body: dict = {}
    if regular_price is not None:
        body["regular_price"] = regular_price
    if sale_price is not None:
        body["sale_price"] = sale_price
    if stock_quantity is not None:
        body["stock_quantity"] = stock_quantity
        body["manage_stock"] = True
    if stock_status is not None:
        body["stock_status"] = stock_status
    if status is not None:
        body["status"] = status

    if not body:
        return "No changes specified."

    data = _put(store_url, key, secret, f"products/{product_id}", body)
    if isinstance(data, dict) and "error" in data:
        return f"Failed to update product: {data['error']}"
    return json.dumps({
        "success": True,
        "product_id": data.get("id"),
        "name": data.get("name"),
        "price": data.get("price"),
        "stock_quantity": data.get("stock_quantity"),
        "stock_status": data.get("stock_status"),
        "status": data.get("status"),
    })


def update_order(
    store_url: str, key: str, secret: str,
    order_id: int,
    status: str = None,
    note: str = None,
) -> str:
    """Update a WooCommerce order status or add a note."""
    results = []

    if status:
        body = {"status": status}
        data = _put(store_url, key, secret, f"orders/{order_id}", body)
        if isinstance(data, dict) and "error" in data:
            return f"Failed to update order: {data['error']}"
        results.append(f"Status changed to '{data.get('status')}'")

    if note:
        body = {"note": note, "customer_note": False}
        data = _post(store_url, key, secret, f"orders/{order_id}/notes", body)
        if isinstance(data, dict) and "error" in data:
            return f"Order status updated but note failed: {data['error']}"
        results.append(f"Note added: '{note[:50]}...'")

    return json.dumps({"success": True, "order_id": order_id, "changes": results})


def test_credentials(store_url: str, key: str, secret: str) -> tuple[bool, str]:
    """
    Test WC credentials by fetching a single order (requires authentication —
    unlike products, orders are never publicly readable).
    Returns (ok: bool, message: str).
    """
    data = _get(store_url, key, secret, "orders", {"per_page": 1})
    if isinstance(data, dict) and "error" in data:
        return False, data["error"]
    if isinstance(data, list):
        return True, "Credentials verified. Store connected successfully."
    return False, "Unexpected response from store — check the store URL and credentials."
