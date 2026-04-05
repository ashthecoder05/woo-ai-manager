from services import blockonomics, blockchain, ucp, marketing
from mcp_server.releases_server import fetch_latest_releases, fetch_gateway_updates, fetch_all_gateway_updates
from mcp_server.architecture_server import (
    get_db_schema, get_frontend_pattern, get_backend_pattern,
    get_plugin_architecture, get_security_checklist,
    get_testing_guide, get_checkout_flow_architecture, list_architecture_topics,
)
from mcp_server.onboarding_server import get_onboarding_guide, list_supported_gateways, compare_gateways
from mcp_server.troubleshooting_server import get_issue_guide, list_known_issues, diagnose_issue
from mcp_server.transaction_verifier import verify_transaction, verify_address_payment, check_scam_signals
from mcp_server.fee_advisor import (
    explain_bitcoin_fees, get_fee_impact_by_product,
    get_fee_adjustment_guide, get_customer_fee_explainer, get_all_fee_rates,
)
from mcp_server.ucp_server import (
    generate_ucp_manifest, generate_all_gateway_manifests,
    generate_multi_gateway_manifest, validate_ucp_manifest, explain_ucp,
)

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_btc_balance",
            "description": "Get the confirmed and unconfirmed BTC balance for a Bitcoin address.",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "Bitcoin address to check"}
                },
                "required": ["address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_transactions",
            "description": "Get the last 10 transactions for a Bitcoin address.",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "Bitcoin address to look up"}
                },
                "required": ["address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_btc_price",
            "description": "Get the current Bitcoin price in USD.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "satoshis_to_btc",
            "description": "Convert a satoshi amount to BTC.",
            "parameters": {
                "type": "object",
                "properties": {
                    "satoshis": {"type": "integer", "description": "Amount in satoshis"}
                },
                "required": ["satoshis"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "btc_to_usd",
            "description": "Convert a BTC amount to USD using the current price.",
            "parameters": {
                "type": "object",
                "properties": {
                    "btc": {"type": "number", "description": "Amount in BTC"}
                },
                "required": ["btc"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_address_summary",
            "description": "Get a full summary of a Bitcoin address including balance and recent transactions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "Bitcoin address to summarize"}
                },
                "required": ["address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_fee_rates",
            "description": "Get the current Bitcoin network fee rates in sat/vByte for different confirmation speeds, plus mempool congestion level.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_transaction_details",
            "description": "Look up a specific Bitcoin transaction by txid. Returns fee rate, confirmation status, vsize, and block info.",
            "parameters": {
                "type": "object",
                "properties": {
                    "txid": {"type": "string", "description": "Bitcoin transaction ID (64-char hex)"}
                },
                "required": ["txid"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_underpayment",
            "description": "Check whether a payment was underpaid, exact, or overpaid by comparing received satoshis to the expected amount.",
            "parameters": {
                "type": "object",
                "properties": {
                    "received_satoshis": {"type": "integer", "description": "Amount actually received in satoshis"},
                    "expected_satoshis": {"type": "integer", "description": "Amount that was invoiced in satoshis"},
                },
                "required": ["received_satoshis", "expected_satoshis"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "diagnose_stuck_transaction",
            "description": "Diagnose why a Bitcoin transaction is unconfirmed or stuck. Compares its fee rate to current network rates and recommends a fix.",
            "parameters": {
                "type": "object",
                "properties": {
                    "txid": {"type": "string", "description": "Bitcoin transaction ID to diagnose"}
                },
                "required": ["txid"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_ucp_manifest",
            "description": "Generate a UCP (Universal Commerce Protocol) JSON-LD manifest for a merchant so AI agents can discover their Bitcoin payment capabilities.",
            "parameters": {
                "type": "object",
                "properties": {
                    "merchant_name": {"type": "string", "description": "The merchant's store name"},
                    "merchant_url": {"type": "string", "description": "The merchant's website URL (e.g. https://mystore.com)"},
                    "description": {"type": "string", "description": "Short description of the store"},
                    "support_email": {"type": "string", "description": "Optional support email address"},
                    "confirmations_required": {"type": "integer", "description": "Number of Bitcoin confirmations before fulfillment (default 2)"},
                },
                "required": ["merchant_name", "merchant_url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_ucp_manifest",
            "description": "Validate a UCP manifest dict for Schema.org correctness and UCP completeness. Returns errors and warnings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "merchant_name": {"type": "string", "description": "Merchant name field to validate"},
                    "merchant_url": {"type": "string", "description": "Merchant URL field to validate"},
                },
                "required": ["merchant_name", "merchant_url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "score_marketing_content",
            "description": (
                "Score a piece of marketing copy (product description, social post, email, etc.) "
                "against a Bitcoin commerce checklist. Returns a grade, checklist results, and actionable suggestions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The marketing copy to score"},
                    "campaign_type": {
                        "type": "string",
                        "enum": ["product_description", "social", "email_subject", "email_body", "banner"],
                        "description": "The type of marketing campaign this copy is for",
                    },
                },
                "required": ["content", "campaign_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "build_optimization_plan",
            "description": (
                "Analyse marketing copy and build a structured rewrite plan: identifies the top priority gaps "
                "and returns plain-English instructions you can use to rewrite the content for a higher score."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The marketing copy to optimise"},
                    "campaign_type": {
                        "type": "string",
                        "enum": ["product_description", "social", "email_subject", "email_body", "banner"],
                        "description": "The type of campaign",
                    },
                },
                "required": ["content", "campaign_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_onchain_proof",
            "description": (
                "Generate a verifiable on-chain proof block for a Bitcoin transaction or address. "
                "Returns a human-readable claim and a mempool.space link that anyone can verify."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "txid": {
                        "type": "string",
                        "description": "Bitcoin transaction ID to generate proof for (optional if using address)",
                    },
                    "address": {
                        "type": "string",
                        "description": "Bitcoin address to generate volume proof for (optional if using txid)",
                    },
                    "confirmed_satoshis": {
                        "type": "integer",
                        "description": "Total confirmed satoshis on the address (required if using address)",
                    },
                    "tx_count": {
                        "type": "integer",
                        "description": "Number of transactions on the address (required if using address)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_latest_releases",
            "description": (
                "Fetch the latest Blockonomics plugin release notes live from GitHub. "
                "Use this whenever a merchant reports a bug or asks about updates — "
                "to check if a new version already fixes their issue."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_gateway_onboarding_guide",
            "description": (
                "Get a step-by-step onboarding guide for a Bitcoin payment gateway. "
                "Covers Blockonomics, Coinbase Commerce, BitPay, Stripe (Bridge), NOWPayments, and CoinGate. "
                "Use this when a merchant asks how to set up or integrate any of these gateways."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "gateway": {
                        "type": "string",
                        "enum": ["blockonomics", "coinbase", "bitpay", "stripe", "nowpayments", "coingate"],
                        "description": "The payment gateway to get the guide for",
                    },
                    "integration_type": {
                        "type": "string",
                        "enum": ["plugin", "api", "custom"],
                        "description": "plugin = install a ready-made plugin (WooCommerce etc), api = direct REST API integration, custom = build your own UI",
                    },
                },
                "required": ["gateway", "integration_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_payment_gateways",
            "description": "List all supported Bitcoin payment gateways and their available integration types (plugin/api/custom).",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_payment_gateways",
            "description": "Compare all supported Bitcoin payment gateways side by side for a given integration type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "integration_type": {
                        "type": "string",
                        "enum": ["plugin", "api", "custom"],
                        "description": "The integration type to compare across gateways",
                    },
                },
                "required": ["integration_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_gateway_updates",
            "description": (
                "Fetch the latest releases and updates for a specific Bitcoin payment gateway. "
                "Use this when a merchant asks what's new, reports a bug, or wants to know the latest version of "
                "Blockonomics, Coinbase Commerce, BitPay, Stripe, NOWPayments, or CoinGate."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "gateway": {
                        "type": "string",
                        "enum": ["blockonomics", "coinbase", "bitpay", "stripe", "nowpayments", "coingate"],
                        "description": "The payment gateway to fetch updates for",
                    },
                },
                "required": ["gateway"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_all_gateway_updates",
            "description": (
                "Fetch the latest releases and updates for ALL supported Bitcoin payment gateways at once. "
                "Use this when a merchant wants a full overview of what's new across all gateways."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "troubleshoot_gateway_issue",
            "description": (
                "Get a plain-English, step-by-step fix guide for a specific payment gateway issue. "
                "Use this when a merchant reports a problem like 'address not generated', "
                "'payment not detected', 'invalid API key', 'webhook not firing', etc. "
                "Designed for non-technical merchants."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "gateway": {
                        "type": "string",
                        "enum": ["blockonomics", "coinbase", "bitpay", "stripe", "nowpayments", "coingate"],
                        "description": "The payment gateway the merchant is using",
                    },
                    "issue": {
                        "type": "string",
                        "description": (
                            "The issue the merchant is facing. Can be a key like 'address_not_generated', "
                            "'payment_not_detected', 'invalid_api_key', 'webhook_not_firing', "
                            "'wrong_btc_amount', 'invoice_expired', 'test_setup_failed', "
                            "'charge_expired', 'invalid_token', 'currency_not_available', "
                            "'underpayment', 'webhook_failing', 'sandbox_vs_live', 'settlement_not_received', "
                            "or a plain-English description like 'customer paid but order is still pending'"
                        ),
                    },
                },
                "required": ["gateway", "issue"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_gateway_issues",
            "description": "List all known issues and their symptoms for a given payment gateway.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gateway": {
                        "type": "string",
                        "enum": ["blockonomics", "coinbase", "bitpay", "stripe", "nowpayments", "coingate"],
                        "description": "The payment gateway to list known issues for",
                    },
                },
                "required": ["gateway"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "diagnose_payment_issue",
            "description": (
                "Diagnose a payment problem from a plain-English description. "
                "Automatically detects the gateway and issue type, then returns a targeted fix guide. "
                "Use this when the merchant hasn't specified the gateway or issue type clearly."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Free-text description of the problem, e.g. 'My Coinbase order is stuck pending after the customer paid'",
                    },
                },
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify_bitcoin_transaction",
            "description": (
                "Verify a Bitcoin transaction in real time using its txid. "
                "Returns full confirmation status, payment amount, legitimacy verdict, and scam detection signals. "
                "Use this when a customer or merchant wants to check if a specific transaction is real, confirmed, or fake."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "txid": {
                        "type": "string",
                        "description": "Bitcoin transaction ID (64-character hex string)",
                    },
                    "expected_amount_sats": {
                        "type": "integer",
                        "description": "Optional: expected payment amount in satoshis to verify against the on-chain amount",
                    },
                },
                "required": ["txid"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify_address_payment",
            "description": (
                "Check if a Bitcoin address has received a payment. "
                "Shows real-time confirmed balance, all recent transactions, confirmation status, and scam verdict. "
                "Use this when a merchant shares a Bitcoin address and wants to confirm payment was received."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Bitcoin address to check (starts with 1, 3, or bc1)",
                    },
                    "expected_amount_sats": {
                        "type": "integer",
                        "description": "Optional: expected payment amount in satoshis to verify against received amount",
                    },
                },
                "required": ["address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "quick_scam_check",
            "description": (
                "Quick plain-English scam check for a Bitcoin txid or address. "
                "Returns a simple LEGITIMATE / PENDING / SCAM ALERT verdict. "
                "Use this when someone asks 'is this payment real?' or 'did I get scammed?'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "txid_or_address": {
                        "type": "string",
                        "description": "A Bitcoin transaction ID (txid) or Bitcoin address",
                    },
                },
                "required": ["txid_or_address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "explain_bitcoin_fees",
            "description": (
                "Explain what Bitcoin network fees (gas fees) are in plain English. "
                "Includes current live rates, why fees exist, and how they affect merchants and customers. "
                "Use when anyone asks 'what is a Bitcoin fee?', 'why am I paying a fee?', or 'what is gas fee?'"
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fee_impact_for_product",
            "description": (
                "Show how current Bitcoin network fees impact a specific product price. "
                "Returns fee as % of order, risk level, and pricing recommendations. "
                "Use when a merchant asks 'should I include the fee in my price?' or 'are fees worth it for a $X product?'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_price_usd": {
                        "type": "number",
                        "description": "The product price in USD",
                    },
                },
                "required": ["product_price_usd"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fee_adjustment_guide",
            "description": (
                "Give a concrete action plan for how a merchant should adjust pricing and checkout "
                "based on current fee levels. Covers absorb / pass-on / economy / minimum-order strategies. "
                "Use when a merchant asks 'how do I handle fees for my product?' or 'should I raise my price?'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_price_usd": {
                        "type": "number",
                        "description": "The product price in USD",
                    },
                    "confirmation_speed": {
                        "type": "string",
                        "enum": ["fastest", "half_hour", "hour", "economy"],
                        "description": "Desired confirmation speed. Default: hour",
                    },
                },
                "required": ["product_price_usd"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "customer_fee_explainer",
            "description": (
                "Generate a customer-facing plain-English explanation of the Bitcoin network fee. "
                "Includes FAQ and current fee options table. "
                "Use when a customer asks why there is a fee, or a merchant wants copy to display at checkout."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fee_amount_usd": {
                        "type": "number",
                        "description": "Optional: the specific fee amount in USD to reference in the explanation",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_all_fee_rates",
            "description": (
                "Get all current live Bitcoin fee rates (express / standard / economy / minimum) "
                "with USD cost estimates and plain-English context. "
                "Use when anyone asks 'what are the current Bitcoin fees?' or 'how much does it cost to send Bitcoin?'"
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "explain_ucp",
            "description": (
                "Explain what UCP (Universal Commerce Protocol) is, why merchants need it, "
                "and how AI agents use it to pay stores automatically. "
                "Use when a merchant asks 'what is UCP?' or 'what is agentic commerce?'"
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_gateway_ucp_manifest",
            "description": (
                "Generate a UCP JSON-LD manifest for a specific payment gateway so AI agents "
                "can discover and pay the merchant automatically. "
                "Covers Blockonomics, Coinbase, BitPay, Stripe, NOWPayments, CoinGate. "
                "Use when a merchant asks to generate a UCP manifest for their store."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "gateway": {
                        "type": "string",
                        "enum": ["blockonomics", "coinbase", "bitpay", "stripe", "nowpayments", "coingate"],
                        "description": "The payment gateway the merchant uses",
                    },
                    "merchant_name": {
                        "type": "string",
                        "description": "The merchant's store name",
                    },
                    "merchant_url": {
                        "type": "string",
                        "description": "The merchant's website URL (e.g. https://mystore.com)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional short description of the store",
                    },
                    "support_email": {
                        "type": "string",
                        "description": "Optional support email address",
                    },
                    "confirmations_required": {
                        "type": "integer",
                        "description": "Number of Bitcoin confirmations before fulfillment (default varies by gateway)",
                    },
                },
                "required": ["gateway", "merchant_name", "merchant_url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_all_ucp_manifests",
            "description": (
                "Generate UCP manifests for ALL 6 supported payment gateways side by side. "
                "Use when a merchant wants to see manifests for every gateway at once."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "merchant_name": {"type": "string", "description": "The merchant's store name"},
                    "merchant_url":  {"type": "string", "description": "The merchant's website URL"},
                    "description":   {"type": "string", "description": "Optional store description"},
                    "support_email": {"type": "string", "description": "Optional support email"},
                },
                "required": ["merchant_name", "merchant_url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_multi_gateway_ucp_manifest",
            "description": (
                "Generate a single UCP manifest combining multiple payment gateways. "
                "Use when a merchant accepts payments from more than one gateway."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "gateways": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of gateway names, e.g. ['blockonomics', 'coinbase']",
                    },
                    "merchant_name": {"type": "string", "description": "The merchant's store name"},
                    "merchant_url":  {"type": "string", "description": "The merchant's website URL"},
                    "description":   {"type": "string", "description": "Optional store description"},
                    "support_email": {"type": "string", "description": "Optional support email"},
                },
                "required": ["gateways", "merchant_name", "merchant_url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_ucp_manifest",
            "description": (
                "Validate a UCP manifest JSON string for correctness. "
                "Returns plain-English errors and warnings. "
                "Use when a merchant provides a UCP manifest and wants to check it before publishing."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "manifest_json": {
                        "type": "string",
                        "description": "The UCP manifest as a JSON string",
                    },
                },
                "required": ["manifest_json"],
            },
        },
    },

    # ── Architecture MCP tools ────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "list_architecture_topics",
            "description": (
                "List all available architecture topics for Bitcoin payment gateway integration. "
                "Covers database schemas, frontend patterns, backend patterns, plugin architecture, "
                "security, and testing. Use this first to discover what guidance is available."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_db_schema",
            "description": (
                "Get a ready-to-use database schema for Bitcoin payment integration. "
                "Covers MySQL (WooCommerce), PostgreSQL (custom), and SQLite (dev/test). "
                "Includes SQL DDL, ORM models, and best-practice tips. "
                "Use when a developer asks how to structure their database for Bitcoin payments."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "db_type": {
                        "type": "string",
                        "enum": ["mysql_woocommerce", "postgresql_custom", "sqlite_minimal"],
                        "description": (
                            "mysql_woocommerce = MySQL with WooCommerce meta tables, "
                            "postgresql_custom = full PostgreSQL schema for a custom app, "
                            "sqlite_minimal = lightweight SQLite schema for dev/testing"
                        ),
                    },
                },
                "required": ["db_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_frontend_pattern",
            "description": (
                "Get a frontend code pattern for a Bitcoin payment UI. "
                "Covers Vanilla JS, React, Vue 3, and drop-in embed scripts. "
                "Includes QR code display, countdown timer, polling, and copy-address button. "
                "Use when a developer asks how to build the payment page UI."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "framework": {
                        "type": "string",
                        "enum": ["vanilla_js_payment_page", "react_payment_component", "vue_payment_component", "embed_script"],
                        "description": (
                            "vanilla_js_payment_page = pure HTML/JS, "
                            "react_payment_component = React 18 component, "
                            "vue_payment_component = Vue 3 Composition API, "
                            "embed_script = drop-in script tag for any existing page"
                        ),
                    },
                },
                "required": ["framework"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_backend_pattern",
            "description": (
                "Get a backend webhook handler pattern for Bitcoin payment processing. "
                "Covers FastAPI, Flask, Express.js, Laravel, and Django. "
                "Includes HMAC signature verification, idempotency, and async processing. "
                "Use when a developer asks how to handle payment webhooks in their backend."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "framework": {
                        "type": "string",
                        "enum": ["fastapi", "flask", "express", "laravel", "django"],
                        "description": "The backend framework the developer is using",
                    },
                },
                "required": ["framework"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_plugin_architecture",
            "description": (
                "Get the plugin architecture guide for building or understanding a Bitcoin payment plugin. "
                "Covers WooCommerce (PHP hooks/filters/gateway class), PrestaShop (module hooks), "
                "and WHMCS (gateway functions). "
                "Use when a developer wants to build a plugin or understand how existing plugins work."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "platform": {
                        "type": "string",
                        "enum": ["woocommerce", "prestashop", "whmcs"],
                        "description": "The platform to get plugin architecture for",
                    },
                },
                "required": ["platform"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_security_checklist",
            "description": (
                "Get a comprehensive security checklist for Bitcoin payment gateway integration. "
                "Covers HMAC verification, idempotency, replay attack prevention, rate limiting, "
                "XSS/CSRF protection, API key safety, and more. "
                "Use when anyone asks about security best practices for Bitcoin payments."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_testing_guide",
            "description": (
                "Get a testing guide for a Bitcoin payment gateway integration. "
                "Covers sandbox setup, test case checklist, and unit test snippets. "
                "Use when a developer asks how to test their Bitcoin payment integration."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "gateway": {
                        "type": "string",
                        "enum": ["blockonomics", "coinbase", "bitpay", "general"],
                        "description": "The gateway to get the testing guide for, or 'general' for a universal checklist",
                    },
                },
                "required": ["gateway"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_checkout_flow_architecture",
            "description": (
                "Get the full end-to-end checkout flow architecture for Bitcoin payments: "
                "request/response cycle, API endpoint design, HTML page structure, and error paths. "
                "Use when a developer asks 'how does the full payment flow work?' or needs "
                "to design their API and checkout page from scratch."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


def run_tool(name: str, inputs: dict) -> str:
    if name == "get_btc_balance":
        result = blockonomics.get_balance(inputs["address"])
        btc = result["confirmed"] / 1e8
        return f"Confirmed: {result['confirmed']} satoshis ({btc:.8f} BTC), Unconfirmed: {result['unconfirmed']} satoshis"

    elif name == "get_transactions":
        txs = blockonomics.get_transactions(inputs["address"])
        if not txs:
            return "No transactions found."
        lines = []
        for tx in txs:
            btc = tx["value"] / 1e8
            lines.append(f"txid={tx['txid'][:16]}... value={btc:.8f} BTC confirmations={tx['confirmations']}")
        return "\n".join(lines)

    elif name == "get_btc_price":
        result = blockonomics.get_price()
        return f"Current BTC price: ${result['usd']:,.2f} USD"

    elif name == "satoshis_to_btc":
        btc = inputs["satoshis"] / 1e8
        return f"{inputs['satoshis']} satoshis = {btc:.8f} BTC"

    elif name == "btc_to_usd":
        price = blockonomics.get_price()["usd"]
        usd = inputs["btc"] * price
        return f"{inputs['btc']} BTC = ${usd:,.2f} USD (at ${price:,.2f}/BTC)"

    elif name == "get_address_summary":
        balance = blockonomics.get_balance(inputs["address"])
        txs = blockonomics.get_transactions(inputs["address"])
        btc = balance["confirmed"] / 1e8
        return (
            f"Balance: {balance['confirmed']} satoshis ({btc:.8f} BTC)\n"
            f"Unconfirmed: {balance['unconfirmed']} satoshis\n"
            f"Recent transactions: {len(txs)}"
        )

    elif name == "get_fee_rates":
        fees = blockchain.get_recommended_fees()
        mempool = blockchain.get_mempool_stats()
        return (
            f"Fee rates (sat/vByte):\n"
            f"  Next block (~10 min): {fees['fastest_fee']}\n"
            f"  ~30 min:              {fees['half_hour_fee']}\n"
            f"  ~1 hour:              {fees['hour_fee']}\n"
            f"  Economy (hours):      {fees['economy_fee']}\n"
            f"  Minimum relay:        {fees['minimum_fee']}\n"
            f"Mempool: {mempool['congestion']} ({mempool['pending_transactions']:,} pending txs)"
        )

    elif name == "get_transaction_details":
        tx = blockchain.get_transaction(inputs["txid"])
        status = "confirmed" if tx["confirmed"] else "unconfirmed"
        fee_label = blockchain.classify_fee(tx["fee_rate_sat_vbyte"])
        lines = [
            f"txid: {tx['txid'][:32]}...",
            f"status: {status}",
            f"fee: {tx['fee_satoshis']} satoshis ({tx['fee_rate_sat_vbyte']} sat/vB) — {fee_label}",
            f"size: {tx['vsize_vbytes']} vBytes",
            f"inputs: {tx['input_count']}  outputs: {tx['output_count']}",
        ]
        if tx["confirmed"]:
            lines.append(f"block height: {tx['block_height']}")
        return "\n".join(lines)

    elif name == "detect_underpayment":
        result = blockchain.detect_underpayment(
            inputs["received_satoshis"], inputs["expected_satoshis"]
        )
        diff_btc = abs(result["difference_satoshis"]) / 1e8
        lines = [f"Status: {result['status'].replace('_', ' ')}"]
        if result["difference_satoshis"] < 0:
            lines.append(
                f"Short by {abs(result['difference_satoshis'])} satoshis ({diff_btc:.8f} BTC) "
                f"— received {result['received_pct']}% of expected"
            )
        elif result["difference_satoshis"] > 0:
            lines.append(f"Overpaid by {result['difference_satoshis']} satoshis ({diff_btc:.8f} BTC)")
        else:
            lines.append("Payment matches the invoice exactly.")
        return "\n".join(lines)

    elif name == "diagnose_stuck_transaction":
        result = blockchain.diagnose_stuck_tx(inputs["txid"])
        if result["confirmed"]:
            return f"Transaction confirmed at block {result['block_height']}. No issues."
        return (
            f"Diagnosis: {result['diagnosis']}\n"
            f"Recommendation: {result['recommendation']}\n"
            f"Fee rate: {result['fee_rate_sat_vbyte']} sat/vB | "
            f"Network economy: {result['network_economy_fee']} | "
            f"1-hour: {result['network_hour_fee']} | "
            f"Fastest: {result['network_fastest_fee']} sat/vB\n"
            f"Mempool: {result['mempool_congestion']}"
        )

    elif name == "generate_ucp_manifest":
        import json
        manifest = ucp.generate_manifest(
            merchant_name=inputs["merchant_name"],
            merchant_url=inputs["merchant_url"],
            description=inputs.get("description", ""),
            support_email=inputs.get("support_email", ""),
            confirmations_required=inputs.get("confirmations_required", 2),
        )
        errors = ucp.validate_manifest(manifest)
        hard = [e for e in errors if e.severity == "error"]
        result = json.dumps(manifest, indent=2)
        if hard:
            result += f"\n\nValidation issues: {'; '.join(str(e) for e in hard)}"
        else:
            result += "\n\nManifest is valid."
        return result

    elif name == "validate_ucp_manifest":
        # Build a minimal manifest from the provided fields to validate
        manifest = ucp.generate_manifest(
            merchant_name=inputs["merchant_name"],
            merchant_url=inputs["merchant_url"],
        )
        return ucp.validate_summary(manifest)

    elif name == "score_marketing_content":
        report = marketing.score_content(inputs["content"], inputs["campaign_type"])
        return marketing.format_score_report(report)

    elif name == "build_optimization_plan":
        plan = marketing.build_optimization_plan(inputs["content"], inputs["campaign_type"])
        initial = plan.initial_score
        grade = "A" if initial.pct >= 85 else "B" if initial.pct >= 70 else "C" if initial.pct >= 50 else "D"
        return (
            f"Initial score: {initial.total_score}/{initial.max_score} ({initial.pct}%) — Grade {grade}\n"
            f"Priority gaps: {'; '.join(plan.priority_gaps) if plan.priority_gaps else 'none'}\n\n"
            f"Rewrite instructions:\n{plan.rewrite_instructions}\n\n"
            f"Original content:\n{plan.original_content}"
        )

    elif name == "generate_onchain_proof":
        txid = inputs.get("txid", "").strip()
        address = inputs.get("address", "").strip()

        if txid:
            proof = marketing.generate_proof_block(txid)
        elif address:
            sats = inputs.get("confirmed_satoshis", 0)
            count = inputs.get("tx_count", 0)
            proof = marketing.generate_address_proof(address, sats, count)
        else:
            return "Provide either a txid or an address to generate proof."

        return marketing.format_proof_for_agent(proof)

    elif name == "get_latest_releases":
        return fetch_latest_releases()

    elif name == "get_gateway_updates":
        return fetch_gateway_updates(inputs["gateway"])

    elif name == "get_all_gateway_updates":
        return fetch_all_gateway_updates()

    elif name == "get_gateway_onboarding_guide":
        return get_onboarding_guide(inputs["gateway"], inputs["integration_type"])

    elif name == "list_payment_gateways":
        return list_supported_gateways()

    elif name == "compare_payment_gateways":
        return compare_gateways(inputs.get("integration_type", "plugin"))

    elif name == "troubleshoot_gateway_issue":
        return get_issue_guide(inputs["gateway"], inputs["issue"])

    elif name == "list_gateway_issues":
        return list_known_issues(inputs["gateway"])

    elif name == "diagnose_payment_issue":
        return diagnose_issue(inputs["description"])

    elif name == "verify_bitcoin_transaction":
        return verify_transaction(inputs["txid"], inputs.get("expected_amount_sats"))

    elif name == "verify_address_payment":
        return verify_address_payment(inputs["address"], inputs.get("expected_amount_sats"))

    elif name == "quick_scam_check":
        return check_scam_signals(inputs["txid_or_address"])

    elif name == "explain_bitcoin_fees":
        return explain_bitcoin_fees()

    elif name == "fee_impact_for_product":
        return get_fee_impact_by_product(inputs["product_price_usd"])

    elif name == "fee_adjustment_guide":
        return get_fee_adjustment_guide(
            inputs["product_price_usd"],
            inputs.get("confirmation_speed", "hour"),
        )

    elif name == "customer_fee_explainer":
        return get_customer_fee_explainer(inputs.get("fee_amount_usd"))

    elif name == "get_all_fee_rates":
        return get_all_fee_rates()

    elif name == "explain_ucp":
        return explain_ucp()

    elif name == "generate_gateway_ucp_manifest":
        return generate_ucp_manifest(
            gateway=inputs["gateway"],
            merchant_name=inputs["merchant_name"],
            merchant_url=inputs["merchant_url"],
            description=inputs.get("description", ""),
            support_email=inputs.get("support_email", ""),
            confirmations_required=inputs.get("confirmations_required"),
        )

    elif name == "generate_all_ucp_manifests":
        return generate_all_gateway_manifests(
            merchant_name=inputs["merchant_name"],
            merchant_url=inputs["merchant_url"],
            description=inputs.get("description", ""),
            support_email=inputs.get("support_email", ""),
        )

    elif name == "generate_multi_gateway_ucp_manifest":
        return generate_multi_gateway_manifest(
            gateways=inputs["gateways"],
            merchant_name=inputs["merchant_name"],
            merchant_url=inputs["merchant_url"],
            description=inputs.get("description", ""),
            support_email=inputs.get("support_email", ""),
        )

    elif name == "validate_ucp_manifest":
        return validate_ucp_manifest(inputs["manifest_json"])

    # ── Architecture MCP handlers ─────────────────────────────────────────────
    elif name == "list_architecture_topics":
        return list_architecture_topics()

    elif name == "get_db_schema":
        return get_db_schema(inputs["db_type"])

    elif name == "get_frontend_pattern":
        return get_frontend_pattern(inputs["framework"])

    elif name == "get_backend_pattern":
        return get_backend_pattern(inputs["framework"])

    elif name == "get_plugin_architecture":
        return get_plugin_architecture(inputs["platform"])

    elif name == "get_security_checklist":
        return get_security_checklist()

    elif name == "get_testing_guide":
        return get_testing_guide(inputs["gateway"])

    elif name == "get_checkout_flow_architecture":
        return get_checkout_flow_architecture()

    return f"Unknown tool: {name}"
