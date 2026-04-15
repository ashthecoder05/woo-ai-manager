"""
wc_tools.py — Azure OpenAI tool definitions for WooCommerce.

TOOL_DEFINITIONS is the schema list passed to the API.
run_wc_tool() executes the named tool against a merchant's store.
"""

from __future__ import annotations

import json
import logging

from services import wc_api

logger = logging.getLogger(__name__)

WC_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_revenue",
            "description": (
                "Get revenue summary for a time period: total sales, net sales, "
                "order count, refunds, tax, shipping, and average order value. "
                "Use 'prior_7d' or 'prior_30d' as the period to get comparison data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "enum": ["today", "7d", "14d", "30d", "prior_7d", "prior_30d"],
                        "description": "Time period: today, 7d, 14d, 30d, prior_7d (prev week), prior_30d (prev month)",
                    }
                },
                "required": ["period"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_orders",
            "description": (
                "List orders with optional filters. Use this to find pending orders, "
                "stuck orders, orders by a customer, or recent activity."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by status: pending, processing, on-hold, completed, cancelled, refunded. Omit for all.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of orders to return (1–50). Default 10.",
                    },
                    "after": {
                        "type": "string",
                        "description": "ISO date (YYYY-MM-DD) — return orders after this date.",
                    },
                    "before": {
                        "type": "string",
                        "description": "ISO date (YYYY-MM-DD) — return orders before this date.",
                    },
                    "customer": {
                        "type": "integer",
                        "description": "Filter by WooCommerce customer ID.",
                    },
                    "search": {
                        "type": "string",
                        "description": "Search orders by customer name or email.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_products",
            "description": (
                "List products. Use stock_status='outofstock' for out-of-stock items, "
                "low_stock=true for products running low, or search by name."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Product status: publish (default), draft, private.",
                    },
                    "stock_status": {
                        "type": "string",
                        "description": "Filter by stock: instock, outofstock, onbackorder.",
                    },
                    "low_stock": {
                        "type": "boolean",
                        "description": "Set true to return only products below their low-stock threshold.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of products to return (1–50). Default 10.",
                    },
                    "search": {
                        "type": "string",
                        "description": "Search products by name.",
                    },
                    "category": {
                        "type": "string",
                        "description": "Filter by category slug.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_products",
            "description": "Get best-selling products by quantity sold for a period.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "enum": ["7d", "30d", "90d"],
                        "description": "Time period: 7d, 30d, or 90d.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of top products to return (1–20). Default 5.",
                    },
                },
                "required": ["period"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_customers",
            "description": "List customers. Sort by total_spent to find your biggest buyers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of customers (1–50). Default 10.",
                    },
                    "search": {
                        "type": "string",
                        "description": "Search by name or email.",
                    },
                    "orderby": {
                        "type": "string",
                        "enum": ["registered_date", "total_spent", "last_active"],
                        "description": "Sort customers by this field.",
                    },
                    "order": {
                        "type": "string",
                        "enum": ["asc", "desc"],
                        "description": "Sort direction. Default desc.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_coupon",
            "description": (
                "Create a discount coupon. IMPORTANT: Before calling this, present the "
                "coupon details to the merchant and ask for explicit confirmation. "
                "Only call this after the merchant says 'yes', 'confirm', or equivalent."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Coupon code (e.g. SUMMER20). Uppercase, no spaces.",
                    },
                    "discount_type": {
                        "type": "string",
                        "enum": ["percent", "fixed_cart", "fixed_product"],
                        "description": "Discount type: percent, fixed_cart, or fixed_product.",
                    },
                    "amount": {
                        "type": "string",
                        "description": "Discount value as a string (e.g. '20' for 20% or $20).",
                    },
                    "minimum_amount": {
                        "type": "string",
                        "description": "Minimum cart total required to use the coupon.",
                    },
                    "expiry_date": {
                        "type": "string",
                        "description": "Expiry date as YYYY-MM-DD. Omit for no expiry.",
                    },
                    "usage_limit": {
                        "type": "integer",
                        "description": "Max total uses across all customers. 0 = unlimited.",
                    },
                },
                "required": ["code", "discount_type", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_product",
            "description": (
                "Update a product's price, stock, or status. IMPORTANT: Present the "
                "planned change to the merchant and ask for confirmation before calling this. "
                "You must have a product_id — use get_products to find it first."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "integer",
                        "description": "WooCommerce product ID (required).",
                    },
                    "regular_price": {
                        "type": "string",
                        "description": "New regular price as a string (e.g. '29.99').",
                    },
                    "sale_price": {
                        "type": "string",
                        "description": "New sale price. Pass empty string '' to clear the sale.",
                    },
                    "stock_quantity": {
                        "type": "integer",
                        "description": "New stock quantity. Also enables stock management.",
                    },
                    "stock_status": {
                        "type": "string",
                        "enum": ["instock", "outofstock", "onbackorder"],
                        "description": "Set stock status directly.",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["publish", "draft", "private"],
                        "description": "Product visibility status.",
                    },
                },
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_order",
            "description": (
                "Update an order's status or add an order note. IMPORTANT: "
                "Confirm the change with the merchant before calling this."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "integer",
                        "description": "WooCommerce order ID.",
                    },
                    "status": {
                        "type": "string",
                        "description": "New status: pending, processing, on-hold, completed, cancelled, refunded.",
                    },
                    "note": {
                        "type": "string",
                        "description": "Internal order note to add (not shown to customer).",
                    },
                },
                "required": ["order_id"],
            },
        },
    },
]


_PERIOD_LABELS = {
    "today":    "today",
    "7d":       "last 7 days",
    "14d":      "last 14 days",
    "30d":      "last 30 days",
    "prior_7d": "previous week",
    "prior_30d":"previous month",
}

_TOOL_ICONS = {
    "get_revenue":     "📊",
    "get_orders":      "📦",
    "get_products":    "🛍",
    "get_top_products":"🏆",
    "get_customers":   "👥",
    "create_coupon":   "🎟",
    "update_product":  "✏️",
    "update_order":    "✏️",
}


def get_tool_icon(name: str) -> str:
    return _TOOL_ICONS.get(name, "🔍")


def get_tool_label(name: str, args: dict) -> str:
    """Return a human-readable label for a tool call."""
    period = _PERIOD_LABELS.get(args.get("period", ""), args.get("period", ""))

    if name == "get_revenue":
        return f"Revenue — {period}" if period else "Revenue"

    if name == "get_orders":
        status = args.get("status", "")
        search = args.get("search", "")
        if search:
            return f"Orders matching '{search}'"
        return f"{status.capitalize()} orders" if status else "Recent orders"

    if name == "get_products":
        if args.get("low_stock"):
            return "Low-stock products"
        ss = args.get("stock_status", "")
        if ss == "outofstock":
            return "Out-of-stock products"
        search = args.get("search", "")
        if search:
            return f"Products matching '{search}'"
        return "Products"

    if name == "get_top_products":
        return f"Top sellers — {period}" if period else "Top sellers"

    if name == "get_customers":
        orderby = args.get("orderby", "")
        if orderby == "total_spent":
            return "Top customers by spend"
        search = args.get("search", "")
        if search:
            return f"Customers matching '{search}'"
        return "Customers"

    if name == "create_coupon":
        code = args.get("code", "")
        return f"Creating coupon {code}" if code else "Creating coupon"

    if name == "update_product":
        return f"Updating product #{args.get('product_id', '')}"

    if name == "update_order":
        return f"Updating order #{args.get('order_id', '')}"

    return name


def run_wc_tool(name: str, inputs: dict, store_url: str, consumer_key: str, consumer_secret: str) -> str:
    """
    Execute a WC tool by name and return its JSON result as a string.
    All WC API functions return strings — errors included — so the AI
    always gets a response it can work with.
    """
    key = consumer_key
    secret = consumer_secret

    logger.info("WC tool call → %s(%s)", name, inputs)
    try:
        if name == "get_revenue":
            return wc_api.get_revenue(store_url, key, secret, period=inputs.get("period", "30d"))

        if name == "get_orders":
            return wc_api.get_orders(
                store_url, key, secret,
                status=inputs.get("status", ""),
                limit=int(inputs.get("limit", 10)),
                after=inputs.get("after", ""),
                before=inputs.get("before", ""),
                customer=int(inputs.get("customer", 0)),
                search=inputs.get("search", ""),
            )

        if name == "get_products":
            return wc_api.get_products(
                store_url, key, secret,
                status=inputs.get("status", "publish"),
                stock_status=inputs.get("stock_status", ""),
                low_stock=bool(inputs.get("low_stock", False)),
                limit=int(inputs.get("limit", 10)),
                search=inputs.get("search", ""),
                category=inputs.get("category", ""),
            )

        if name == "get_top_products":
            return wc_api.get_top_products(
                store_url, key, secret,
                period=inputs.get("period", "30d"),
                limit=int(inputs.get("limit", 5)),
            )

        if name == "get_customers":
            return wc_api.get_customers(
                store_url, key, secret,
                limit=int(inputs.get("limit", 10)),
                search=inputs.get("search", ""),
                orderby=inputs.get("orderby", "registered_date"),
                order=inputs.get("order", "desc"),
            )

        if name == "create_coupon":
            return wc_api.create_coupon(
                store_url, key, secret,
                code=inputs["code"],
                discount_type=inputs["discount_type"],
                amount=str(inputs["amount"]),
                minimum_amount=str(inputs.get("minimum_amount", "")),
                expiry_date=inputs.get("expiry_date", ""),
                usage_limit=int(inputs.get("usage_limit", 0)),
            )

        if name == "update_product":
            return wc_api.update_product(
                store_url, key, secret,
                product_id=int(inputs["product_id"]),
                regular_price=inputs.get("regular_price"),
                sale_price=inputs.get("sale_price"),
                stock_quantity=int(inputs["stock_quantity"]) if "stock_quantity" in inputs else None,
                stock_status=inputs.get("stock_status"),
                status=inputs.get("status"),
            )

        if name == "update_order":
            return wc_api.update_order(
                store_url, key, secret,
                order_id=int(inputs["order_id"]),
                status=inputs.get("status"),
                note=inputs.get("note"),
            )

        return json.dumps({"error": f"Unknown tool: {name}"})

    except Exception as e:
        logger.error("run_wc_tool(%s) error: %s", name, e)
        return json.dumps({"error": str(e)})
