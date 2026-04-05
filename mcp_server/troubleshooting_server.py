"""
Payment Gateway Troubleshooting MCP Server

Covers: Blockonomics, Coinbase Commerce, BitPay, Stripe, NOWPayments, CoinGate
Designed for non-technical merchants — plain English explanations + step-by-step fixes.

For Python 3.10+ run as MCP:
  python mcp_server/troubleshooting_server.py

For Python 3.8 compatibility this is wired as a regular tool in agent/tools.py
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Issue taxonomy
# Each issue has:
#   symptom     — what the merchant sees (non-technical)
#   what_happened — plain English explanation of the root cause
#   steps       — numbered fix steps (non-technical language)
#   technical   — optional developer-level detail
#   docs_url    — link for more help
# ---------------------------------------------------------------------------

ISSUES: dict[str, dict[str, list[dict]]] = {

    # ── BLOCKONOMICS ────────────────────────────────────────────────────────
    "blockonomics": {
        "address_not_generated": [{
            "symptom": "Cannot generate a Bitcoin address / gap limit error",
            "what_happened": (
                "Your Bitcoin wallet has a safety limit called a 'gap limit'. "
                "Think of it like a row of numbered parking spaces — if too many spaces "
                "are empty (unused addresses), the wallet refuses to hand out more. "
                "This usually happens when you generated addresses but no payments came in."
            ),
            "steps": [
                "Log in to your Blockonomics account at blockonomics.co",
                "Click 'Dashboard' → 'Wallets'",
                "Click the pencil/edit icon next to your wallet",
                "Find the 'Gap Limit' field and change it from 20 to 100",
                "Click Save",
                "Try generating an address again — it should work now",
            ],
            "technical": "POST /api/new_address returns HTTP 409 when gap limit is exceeded. Increasing gap_limit in dashboard resolves this.",
            "docs_url": "https://www.blockonomics.co/views/faq.html#gap-limit",
        }],
        "payment_not_detected": [{
            "symptom": "Customer paid but the order is still showing as unpaid",
            "what_happened": (
                "Your store and Blockonomics talk to each other via a 'webhook' — "
                "a notification sent to your website when a payment arrives. "
                "If your website didn't receive that notification, the order won't update. "
                "The most common reason is the notification was blocked or the URL is wrong."
            ),
            "steps": [
                "Go to Blockonomics Dashboard → Stores → click your store",
                "Check the 'Callback URL' — it should start with https:// and point to your live website (not localhost)",
                "Click 'Test Setup' — it will show green ticks if everything is connected",
                "If a tick is red, hover over it for the specific error message",
                "If you're on shared hosting, contact your host and ask them to whitelist Blockonomics webhook IPs",
                "Check your order again after 10 minutes — if it still shows unpaid, the payment may still be unconfirmed on the Bitcoin network",
            ],
            "technical": "Webhook is a GET request to callback_url?secret=SECRET&addr=ADDR&value=VALUE&txid=TXID&status=STATUS. Status 0=unconfirmed, 1=partial, 2=confirmed.",
            "docs_url": "https://www.blockonomics.co/views/faq.html#webhook",
        }],
        "invalid_api_key": [{
            "symptom": "Getting 'Invalid API Key' or 'Unauthorized' error",
            "what_happened": (
                "Your store is using an old, wrong, or misformatted API key to connect to Blockonomics. "
                "This is like using an expired password — Blockonomics rejects the connection."
            ),
            "steps": [
                "Log in to blockonomics.co",
                "Click Dashboard → Stores → click your store name",
                "Find the 'API Key' field — click the copy button (do NOT manually type it)",
                "Go to your plugin/integration settings and paste it fresh",
                "Make sure there are no extra spaces before or after the key",
                "Save settings and test again",
            ],
            "technical": "API key must be sent as 'Authorization: Bearer <key>' header. HTTP 401 = invalid key.",
            "docs_url": "https://www.blockonomics.co/views/api.html",
        }],
        "wrong_btc_amount": [{
            "symptom": "Customer paid the correct USD amount but Bitcoin amount doesn't match",
            "what_happened": (
                "Bitcoin's price changes every second. If your store calculated the BTC amount "
                "a few minutes before the customer paid, the price may have shifted. "
                "Also, exchange fees can reduce the amount slightly."
            ),
            "steps": [
                "In your store's Blockonomics settings, find the 'Underpayment Slack' or tolerance setting",
                "Set it to 1-2% to accept payments that are slightly under the exact amount",
                "Make sure your store fetches a fresh BTC price at the exact moment of checkout (not cached)",
                "For the current payment: check if it's within 1-2% of the expected amount — if so, manually mark it as paid",
            ],
            "technical": "Always call GET /api/price?currency=USD at checkout time. Cache price for max 60 seconds.",
            "docs_url": "https://www.blockonomics.co/views/faq.html#underpayment",
        }],
        "webhook_not_firing": [{
            "symptom": "Bitcoin was confirmed on blockchain but your server never got notified",
            "what_happened": (
                "Blockonomics tried to send a payment notification to your website but couldn't reach it. "
                "This is usually because your website is blocking the notification or the URL is unreachable."
            ),
            "steps": [
                "Make sure your website is live and accessible from the internet (not a local/development site)",
                "Your callback URL must use HTTPS (not HTTP)",
                "Check if your website has a firewall or security plugin (like Wordfence) — temporarily disable it and test",
                "Ask your hosting provider to whitelist Blockonomics server IPs",
                "For development: use ngrok (ngrok.com) to create a public URL for your local server",
            ],
            "technical": "Blockonomics sends GET requests. Firewall rules blocking outbound GETs from Blockonomics IPs (185.209.160.0/24) are the most common cause.",
            "docs_url": "https://www.blockonomics.co/views/faq.html#callback",
        }],
        "test_setup_failed": [{
            "symptom": "'Test Setup' button shows red X or errors",
            "what_happened": (
                "The Test Setup checks 3 things: your API key, your wallet xpub, and your callback URL. "
                "A red X means one of these three things isn't set up correctly."
            ),
            "steps": [
                "Run Test Setup and note which check is failing (hover over the red X for details)",
                "API Key failing → re-copy your API key from Dashboard → Stores",
                "Wallet/xpub failing → go to Dashboard → Wallets and make sure a wallet is added with a valid xpub",
                "Callback URL failing → ensure the URL is publicly accessible and uses HTTPS",
                "After fixing each issue, click Test Setup again",
                "All green ticks = you are ready to accept payments",
            ],
            "technical": "Test Setup calls /api/merchant?match_callback=1 which validates key, xpub registration, and callback reachability.",
            "docs_url": "https://www.blockonomics.co/views/faq.html#test-setup",
        }],
    },

    # ── COINBASE COMMERCE ────────────────────────────────────────────────────
    "coinbase": {
        "address_not_generated": [{
            "symptom": "Payment page not showing / charge creation failing",
            "what_happened": (
                "Coinbase Commerce couldn't create a payment request. "
                "This usually means your API key is missing, expired, or your account has a restriction."
            ),
            "steps": [
                "Go to commerce.coinbase.com and log in",
                "Click your profile icon → Settings → API Keys",
                "If your key is older than 90 days, create a new one",
                "Copy the new key and paste it into your plugin/integration settings",
                "Make sure your Coinbase Commerce account is fully verified (check for any pending verification banners)",
                "Try creating a test charge from the Coinbase Commerce dashboard to confirm your account is active",
            ],
            "technical": "POST /charges returns 401 if API key invalid, 403 if account restricted.",
            "docs_url": "https://docs.cloud.coinbase.com/commerce/reference/createcharge",
        }],
        "payment_not_detected": [{
            "symptom": "Customer paid but order is still pending",
            "what_happened": (
                "Coinbase Commerce sends a notification to your website when payment is confirmed. "
                "If the notification didn't arrive, your website may have the wrong URL configured, "
                "or the Webhook Shared Secret doesn't match."
            ),
            "steps": [
                "Log in to commerce.coinbase.com → Settings → Webhook subscriptions",
                "Check the webhook URL — it must be your live website URL (not localhost)",
                "Make sure the 'Shared Secret' shown here matches exactly what's in your plugin settings",
                "Click 'Send test notification' and check if your server receives it",
                "In your plugin settings, look for a webhook log or check your server error logs",
                "If still failing, delete the webhook and create a new one with the correct URL",
            ],
            "technical": "Webhook is POST with JSON body. Verified via HMAC-SHA256 of raw body using shared secret, compared to X-CC-Webhook-Signature header.",
            "docs_url": "https://docs.cloud.coinbase.com/commerce/docs/webhooks-notifications",
        }],
        "charge_expired": [{
            "symptom": "Customer sees 'Charge expired' before they could pay",
            "what_happened": (
                "Coinbase Commerce payment requests expire after 60 minutes by default. "
                "If the customer took too long, or the link was shared too early, it expired."
            ),
            "steps": [
                "Ask the customer to go back to checkout and start a new payment",
                "Do not reuse old payment links — always generate a fresh one at checkout",
                "If this keeps happening, check if your store is generating the charge too early (e.g. when adding to cart instead of at checkout)",
                "In your integration, create the charge only when the customer clicks 'Pay Now'",
            ],
            "technical": "Charge expires_at is 60 min from creation. Create charges at the final checkout step, not earlier.",
            "docs_url": "https://docs.cloud.coinbase.com/commerce/docs/charges",
        }],
        "invalid_api_key": [{
            "symptom": "Getting 401 Unauthorized or 'Invalid API key' error",
            "what_happened": (
                "The API key your store is using to connect to Coinbase Commerce is wrong or has been deleted."
            ),
            "steps": [
                "Go to commerce.coinbase.com → Settings → API Keys",
                "Check if your key still exists — if not, create a new one",
                "Click the copy icon next to the key (don't type it manually)",
                "Paste it into your plugin or integration settings and save",
                "Do a test checkout to confirm it works",
            ],
            "technical": "API key sent as X-CC-Api-Key header. Must also send X-CC-Version: 2018-03-22.",
            "docs_url": "https://docs.cloud.coinbase.com/commerce/reference/authentication",
        }],
        "wrong_amount": [{
            "symptom": "Payment amount shown in crypto doesn't match the order total",
            "what_happened": (
                "Coinbase Commerce converts your order's USD price to crypto at the current market rate. "
                "The rate shown to the customer is locked for 15 minutes. "
                "If the customer waits too long, the rate changes and the amounts may differ."
            ),
            "steps": [
                "Ask the customer to refresh the payment page to get a fresh rate",
                "Make sure your order total in USD is correct before creating the charge",
                "Coinbase Commerce handles the conversion automatically — no manual calculation needed",
            ],
            "technical": "Coinbase Commerce uses pricing_type: fixed_price with local_price in fiat. Crypto amount is auto-calculated and updated every 15 min.",
            "docs_url": "https://docs.cloud.coinbase.com/commerce/docs/charges#pricing",
        }],
    },

    # ── BITPAY ───────────────────────────────────────────────────────────────
    "bitpay": {
        "address_not_generated": [{
            "symptom": "Invoice not created / payment page not loading",
            "what_happened": (
                "BitPay couldn't create a payment invoice. "
                "This is usually an API token issue or your BitPay account needs additional verification."
            ),
            "steps": [
                "Log in to bitpay.com (or test.bitpay.com for testing)",
                "Go to Payment Tools → Merchant → API Tokens",
                "Make sure you have a token with 'merchant' facade (not 'pos' or 'payout')",
                "If not, click 'Add New Token', select 'merchant', and approve the pairing",
                "Copy the token and paste it into your plugin settings",
                "Check if your BitPay account has completed identity verification — unverified accounts can't go live",
            ],
            "technical": "POST /invoices returns 403 if token facade is wrong or account not verified. Token must have 'merchant' facade.",
            "docs_url": "https://bitpay.com/docs/api#creating-an-invoice",
        }],
        "payment_not_detected": [{
            "symptom": "Customer paid but order status hasn't updated",
            "what_happened": (
                "BitPay sends an IPN (Instant Payment Notification) to your website when payment is received. "
                "If your website didn't receive it, the order won't update. "
                "This is usually a URL or firewall issue."
            ),
            "steps": [
                "In your BitPay plugin settings, find the 'Notification URL' or 'IPN URL'",
                "Make sure it points to your live website (starts with https://)",
                "Log in to bitpay.com → go to your invoice → check the 'IPN history' tab for delivery attempts",
                "If IPN failed, note the error and check your server firewall isn't blocking BitPay's IPs",
                "You can manually resend the IPN from the BitPay dashboard",
                "For immediate resolution: manually check the invoice status in BitPay dashboard and update your order manually",
            ],
            "technical": "BitPay IPN is POST with JSON. Verify using BitPay's public key from GET /tokens. Invoice status: new → paid → confirmed → complete.",
            "docs_url": "https://bitpay.com/docs/api#instant-payment-notification",
        }],
        "invoice_expired": [{
            "symptom": "Invoice expired before customer paid",
            "what_happened": (
                "BitPay invoices are valid for 15 minutes. "
                "If the customer didn't complete payment in time, the invoice expired."
            ),
            "steps": [
                "Ask the customer to go back to checkout and try again",
                "A new 15-minute invoice will be created automatically",
                "If this happens frequently, check if your checkout page has a session timeout that's shorter than 15 minutes",
                "Do not create the invoice until the customer is ready to pay (i.e. on the final checkout step)",
            ],
            "technical": "Invoice expirationTime is 15 min by default. Expired invoices have status 'expired' and cannot be paid.",
            "docs_url": "https://bitpay.com/docs/api#invoice-states",
        }],
        "invalid_token": [{
            "symptom": "403 Forbidden or 'Unauthorized' error from BitPay",
            "what_happened": (
                "The API token your store is using either has the wrong permissions, "
                "has been deleted, or was created for a different environment (test vs live)."
            ),
            "steps": [
                "Check which environment your plugin is set to: Test or Production",
                "For Test: use tokens from test.bitpay.com — For Live: use tokens from bitpay.com",
                "Go to the correct dashboard → Payment Tools → API Tokens",
                "Create a new token with 'merchant' facade",
                "Copy the new token into your plugin settings",
                "Make sure the environments match (plugin setting and token source must both be test OR both be live)",
            ],
            "technical": "BitPay has separate environments: bitpay.com (prod) and test.bitpay.com (sandbox). Tokens are environment-specific.",
            "docs_url": "https://bitpay.com/docs/api#test-environment",
        }],
    },

    # ── STRIPE (BRIDGE/CRYPTO) ───────────────────────────────────────────────
    "stripe": {
        "address_not_generated": [{
            "symptom": "Crypto payment option not appearing at checkout",
            "what_happened": (
                "Stripe crypto payments require a special feature called 'Stripe Bridge' "
                "to be activated on your account. It's not enabled by default."
            ),
            "steps": [
                "Log in to dashboard.stripe.com",
                "Go to Settings → Payment methods",
                "Search for 'Crypto' or 'USDC' in the payment methods list",
                "Click 'Turn on' and follow the activation steps (may require identity verification)",
                "Once approved, go back to your checkout and the crypto option should appear",
                "If you don't see Crypto in payment methods, your country or business type may not be supported yet — check stripe.com/docs/crypto for availability",
            ],
            "technical": "Stripe Bridge (crypto) must be explicitly enabled per account. Not available in all regions. Use payment_method_types: ['crypto'] in PaymentIntent.",
            "docs_url": "https://stripe.com/docs/payments/crypto",
        }],
        "payment_not_detected": [{
            "symptom": "Payment went through on Stripe but order didn't update",
            "what_happened": (
                "Stripe uses 'webhooks' to notify your store when a payment is completed. "
                "If the webhook isn't set up or the secret doesn't match, your order won't update."
            ),
            "steps": [
                "Log in to dashboard.stripe.com → Developers → Webhooks",
                "Check if there's a webhook endpoint pointing to your website",
                "If not, click 'Add endpoint', enter your site URL + /webhook path, and select 'payment_intent.succeeded' event",
                "Copy the 'Signing secret' shown and paste it into your plugin/integration settings",
                "Click 'Send test webhook' to verify your site receives it",
                "Check 'Recent deliveries' in the webhook page to see if past notifications failed and why",
            ],
            "technical": "Verify webhook via Stripe-Signature header using stripe.Webhook.construct_event(). Listen for payment_intent.succeeded event.",
            "docs_url": "https://stripe.com/docs/webhooks",
        }],
        "invalid_api_key": [{
            "symptom": "Authentication error / 'No such API key' error from Stripe",
            "what_happened": (
                "Your store is using an incorrect or deleted Stripe API key. "
                "Stripe has two sets of keys: test keys (for development) and live keys (for real payments)."
            ),
            "steps": [
                "Log in to dashboard.stripe.com → Developers → API keys",
                "You'll see 'Publishable key' (starts with pk_) and 'Secret key' (starts with sk_)",
                "Test keys start with pk_test_ and sk_test_ — Live keys start with pk_live_ and sk_live_",
                "Make sure you're using live keys on your live store (not test keys)",
                "Click 'Reveal live key' and copy it fresh",
                "Paste it into your plugin settings and save",
            ],
            "technical": "Test mode keys (sk_test_) only work with test card numbers. Live mode keys (sk_live_) process real payments. Never expose sk_ keys client-side.",
            "docs_url": "https://stripe.com/docs/keys",
        }],
        "webhook_failing": [{
            "symptom": "Webhook signature verification failing / 400 error on webhook endpoint",
            "what_happened": (
                "Your server is receiving Stripe's notification but rejecting it because "
                "the security signature doesn't match. "
                "This usually means the webhook signing secret is wrong or the request body was modified."
            ),
            "steps": [
                "Go to Stripe Dashboard → Developers → Webhooks → click your endpoint",
                "Click 'Reveal' next to 'Signing secret' — this is different from your API key",
                "Copy this signing secret and update it in your plugin/integration settings",
                "Make sure your server reads the raw request body (not parsed JSON) when verifying",
                "If using Stripe CLI for local testing: run 'stripe listen --forward-to localhost:8000/webhook' and use the CLI's signing secret (not the dashboard one)",
            ],
            "technical": "stripe.Webhook.construct_event(payload, sig_header, endpoint_secret) — payload must be raw bytes, not parsed. Each endpoint has its own signing secret.",
            "docs_url": "https://stripe.com/docs/webhooks/signatures",
        }],
    },

    # ── NOWPAYMENTS ──────────────────────────────────────────────────────────
    "nowpayments": {
        "address_not_generated": [{
            "symptom": "Payment address not generated / API error on checkout",
            "what_happened": (
                "NOWPayments couldn't create a payment request. "
                "This is usually an API key issue or the selected cryptocurrency is temporarily unavailable."
            ),
            "steps": [
                "Log in to nowpayments.io → Account → Store Settings → API Keys",
                "Check if your API key is still active (not expired or revoked)",
                "Copy a fresh API key and paste it into your plugin settings",
                "Check the NOWPayments status page (nowpayments.io/status) — some coins go offline for maintenance",
                "If a specific coin is offline, temporarily switch to a different accepted currency like USDT or BTC",
                "Make sure your NOWPayments account email is verified",
            ],
            "technical": "POST /v1/payment returns 401 for invalid API key, 500 if coin is temporarily disabled. Check GET /v1/currencies for currently available coins.",
            "docs_url": "https://documenter.getpostman.com/view/7907941/2s93JqTRWN#create-payment",
        }],
        "payment_not_detected": [{
            "symptom": "Customer paid but order is still pending",
            "what_happened": (
                "NOWPayments sends a notification (called IPN) to your website when a payment is confirmed. "
                "If the IPN didn't arrive, your order won't update. "
                "The most common cause is the callback URL not being set or the IPN secret not matching."
            ),
            "steps": [
                "Log in to nowpayments.io → Account → Store Settings",
                "Find the 'IPN callback URL' field — enter your website's webhook URL",
                "Also copy the 'IPN Secret Key' shown on that page",
                "Go to your plugin settings and paste the IPN Secret Key",
                "Save both settings",
                "Make a small test purchase to verify notifications are working",
                "Check nowpayments.io → Payments → click a payment → scroll to 'IPN history' to see if notifications were sent and if any failed",
            ],
            "technical": "IPN is POST with JSON. Signature is HMAC-SHA512 of alphabetically sorted JSON body using IPN Secret. Compared to x-nowpayments-sig header.",
            "docs_url": "https://documenter.getpostman.com/view/7907941/2s93JqTRWN#ipn-callbacks",
        }],
        "currency_not_available": [{
            "symptom": "A specific cryptocurrency is not showing at checkout",
            "what_happened": (
                "NOWPayments supports 300+ cryptocurrencies, but some are temporarily disabled for "
                "maintenance, low liquidity, or network issues."
            ),
            "steps": [
                "Go to nowpayments.io → Account → Currencies",
                "Check which currencies are currently enabled on your account",
                "Visit nowpayments.io/status to see if the coin is temporarily offline",
                "If a coin is offline, it will come back automatically — usually within a few hours",
                "Consider enabling USDT or BTC as backup options since they're almost always available",
                "In your plugin settings, allow customers to choose from multiple currencies",
            ],
            "technical": "GET /v1/currencies returns currently available coins. GET /v1/currencies?fixed_rate=true for fixed-rate supported coins.",
            "docs_url": "https://documenter.getpostman.com/view/7907941/2s93JqTRWN#get-available-currencies",
        }],
        "invalid_api_key": [{
            "symptom": "'Authentication failed' or 401 error",
            "what_happened": (
                "The API key your store is using to connect to NOWPayments is incorrect or has been regenerated."
            ),
            "steps": [
                "Log in to nowpayments.io → Account → Store Settings → API Keys",
                "Click 'Generate new key' if your current key isn't working",
                "Copy the new key immediately (it's only shown once)",
                "Paste it into your plugin settings and save",
                "Note: you also need a separate 'IPN Secret Key' for webhook notifications — these are two different keys",
            ],
            "technical": "API key sent as x-api-key header. IPN Secret is separate and only used for webhook signature verification.",
            "docs_url": "https://documenter.getpostman.com/view/7907941/2s93JqTRWN#authentication",
        }],
        "underpayment": [{
            "symptom": "Customer paid slightly less than required / payment marked as underpaid",
            "what_happened": (
                "The customer's wallet may have deducted a small network fee from the payment amount, "
                "or the Bitcoin price changed slightly between when the invoice was created and when payment was sent."
            ),
            "steps": [
                "Log in to nowpayments.io → Account → Store Settings",
                "Find 'Underpayment threshold' — set it to 1% or 2% to accept payments that are slightly under",
                "For the current order: go to Payments, find the payment, and check if it's within 1-2% of the expected amount",
                "If within tolerance, you can manually mark the order as paid in your store admin",
                "Ask the customer to send the remaining amount if it's a significant shortfall",
            ],
            "technical": "NOWPayments payment status 'partially_paid' indicates underpayment. Configure underpayment_amount in account settings.",
            "docs_url": "https://documenter.getpostman.com/view/7907941/2s93JqTRWN#payment-statuses",
        }],
    },

    # ── COINGATE ─────────────────────────────────────────────────────────────
    "coingate": {
        "address_not_generated": [{
            "symptom": "Order/payment page not loading / 'Failed to create order' error",
            "what_happened": (
                "CoinGate couldn't create a payment order. "
                "This usually means the auth token is wrong or you're mixing up test and live environments."
            ),
            "steps": [
                "Log in to coingate.com (or sandbox.coingate.com for testing)",
                "Go to Account → API → Apps",
                "Check that your app has 'order' permissions checked",
                "Click the app name, then 'Show token' and copy it fresh",
                "Paste it into your plugin settings",
                "IMPORTANT: If testing, use sandbox.coingate.com token with plugin set to 'Sandbox mode'. For live, use coingate.com token with plugin set to 'Live mode'",
            ],
            "technical": "POST /v2/orders returns 401 for invalid token. Sandbox and live are completely separate environments with separate tokens.",
            "docs_url": "https://developer.coingate.com/reference/create-order",
        }],
        "payment_not_detected": [{
            "symptom": "Customer paid but order status is still 'pending'",
            "what_happened": (
                "CoinGate sends a callback to your website when payment is confirmed. "
                "If the callback didn't arrive or was rejected, the order won't update."
            ),
            "steps": [
                "Log in to coingate.com → Orders → click the specific order",
                "Scroll to 'Callbacks' section to see if CoinGate attempted to notify your site and what happened",
                "If it shows an error, note the HTTP status code — 404 means wrong URL, 500 means your server errored",
                "Go to your plugin settings and verify the callback URL is correct",
                "You can click 'Resend callback' from the order page to try again",
                "Make sure your server accepts POST requests to the callback URL without authentication",
            ],
            "technical": "CoinGate sends POST with JSON or form-encoded body. Verify by calling GET /v2/orders/{id} server-side — don't trust callback body alone.",
            "docs_url": "https://developer.coingate.com/docs/order-callbacks",
        }],
        "sandbox_vs_live": [{
            "symptom": "Payments working in test but failing on live site / 'App not found' error",
            "what_happened": (
                "CoinGate has two completely separate environments: Sandbox (for testing) and Live (for real payments). "
                "If you're using a sandbox token on your live store, every payment will fail."
            ),
            "steps": [
                "Check your plugin settings — is it set to 'Sandbox' or 'Live' mode?",
                "For a live store taking real payments: set it to 'Live' mode",
                "For live mode: log in to coingate.com (NOT sandbox.coingate.com) → Account → API → Apps → copy your token",
                "Paste the live token into your plugin settings",
                "Save and test with a small real payment to confirm",
            ],
            "technical": "Live API: api.coingate.com. Sandbox API: api-sandbox.coingate.com. Tokens are not interchangeable between environments.",
            "docs_url": "https://developer.coingate.com/docs/test-environment",
        }],
        "settlement_not_received": [{
            "symptom": "Payment confirmed but funds not received in bank/wallet",
            "what_happened": (
                "CoinGate holds funds briefly before settling to your bank account or crypto wallet. "
                "Settlement timing depends on your account settings and verification level."
            ),
            "steps": [
                "Log in to coingate.com → Account → Settlement",
                "Check your settlement method is set up (bank account or crypto address)",
                "Check the settlement schedule — daily settlements go out each business day",
                "Look for any pending verification requirements on your account (KYB/KYC)",
                "If settlement is overdue by more than 5 business days, contact CoinGate support with the order ID",
            ],
            "technical": "Settlement is separate from payment confirmation. Confirmed orders are batched and settled per account schedule.",
            "docs_url": "https://support.coingate.com/en/articles/settlement",
        }],
        "invalid_token": [{
            "symptom": "401 Unauthorized from CoinGate API",
            "what_happened": (
                "The token your store is using to connect to CoinGate is invalid, expired, or doesn't have the right permissions."
            ),
            "steps": [
                "Log in to coingate.com → Account → API → Apps",
                "Find your app and check it has 'order' permission enabled",
                "Click your app name → 'Show token' → copy the token",
                "Paste it into your plugin settings (replace the old one completely)",
                "If in doubt, create a new app with 'order' permission and use that token",
            ],
            "technical": "Token sent as 'Authorization: Token <token>' header. Token requires 'order' scope for creating/reading orders.",
            "docs_url": "https://developer.coingate.com/docs/authentication",
        }],
    },
}

# Issue aliases — map natural language to issue keys
ISSUE_ALIASES: dict[str, str] = {
    # address generation
    "address not generated": "address_not_generated",
    "cannot generate address": "address_not_generated",
    "gap limit": "address_not_generated",
    "payment page not loading": "address_not_generated",
    "invoice not created": "address_not_generated",
    "charge creation failing": "address_not_generated",
    "order not created": "address_not_generated",
    # payment not detected
    "payment not detected": "payment_not_detected",
    "order not updating": "payment_not_detected",
    "order still pending": "payment_not_detected",
    "paid but not updated": "payment_not_detected",
    "webhook not working": "payment_not_detected",
    "webhook not firing": "webhook_not_firing",
    "ipn not working": "payment_not_detected",
    "callback not received": "payment_not_detected",
    # api key
    "invalid api key": "invalid_api_key",
    "unauthorized": "invalid_api_key",
    "401 error": "invalid_api_key",
    "authentication error": "invalid_api_key",
    "invalid token": "invalid_token",
    # amounts
    "wrong amount": "wrong_btc_amount",
    "underpayment": "underpayment",
    "wrong btc amount": "wrong_btc_amount",
    # expiry
    "expired": "invoice_expired",
    "charge expired": "charge_expired",
    "invoice expired": "invoice_expired",
    # other
    "test setup failed": "test_setup_failed",
    "webhook signature": "webhook_failing",
    "crypto not showing": "address_not_generated",
    "stripe bridge": "address_not_generated",
    "sandbox vs live": "sandbox_vs_live",
    "currency not available": "currency_not_available",
    "settlement": "settlement_not_received",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

SUPPORTED_GATEWAYS = list(ISSUES.keys())


def get_issue_guide(gateway: str, issue: str) -> str:
    """
    Get a plain-English troubleshooting guide for a specific issue on a gateway.
    gateway: blockonomics | coinbase | bitpay | stripe | nowpayments | coingate
    issue: free-text description or exact issue key
    """
    gateway = gateway.lower().strip()
    issue_query = issue.lower().strip()

    if gateway not in ISSUES:
        available = ", ".join(SUPPORTED_GATEWAYS)
        return f"Unknown gateway '{gateway}'. Supported: {available}"

    gateway_issues = ISSUES[gateway]

    # Try exact key match first
    if issue_query in gateway_issues:
        issue_key = issue_query
    else:
        # Try alias lookup
        issue_key = ISSUE_ALIASES.get(issue_query)
        # Try partial match
        if not issue_key:
            for alias, key in ISSUE_ALIASES.items():
                if alias in issue_query or issue_query in alias:
                    issue_key = key
                    break
        # Try partial match on issue keys directly
        if not issue_key:
            for key in gateway_issues:
                if key in issue_query or issue_query in key:
                    issue_key = key
                    break

    if not issue_key or issue_key not in gateway_issues:
        available = ", ".join(gateway_issues.keys())
        return (
            f"Couldn't find a specific guide for '{issue}' on {gateway}. "
            f"Available issues: {available}\n\n"
            f"Try asking about one of these, or describe your problem and I'll help."
        )

    guide = gateway_issues[issue_key][0]
    lines = [
        f"## {gateway.capitalize()} — {guide['symptom']}\n",
        f"**What's happening?**\n{guide['what_happened']}\n",
        f"**How to fix it — step by step:**",
    ]
    for i, step in enumerate(guide["steps"], 1):
        lines.append(f"  {i}. {step}")

    if guide.get("technical"):
        lines.append(f"\n**Technical detail:** {guide['technical']}")

    if guide.get("docs_url"):
        lines.append(f"\n**More help:** {guide['docs_url']}")

    return "\n".join(lines)


def list_known_issues(gateway: str) -> str:
    """List all known issues for a given gateway."""
    gateway = gateway.lower().strip()
    if gateway not in ISSUES:
        available = ", ".join(SUPPORTED_GATEWAYS)
        return f"Unknown gateway '{gateway}'. Supported: {available}"

    lines = [f"**Known issues for {gateway.capitalize()}:**\n"]
    for key, guides in ISSUES[gateway].items():
        symptom = guides[0]["symptom"]
        lines.append(f"  - `{key}` — {symptom}")

    lines.append(f"\nAsk me about any of these and I'll walk you through the fix.")
    return "\n".join(lines)


def diagnose_issue(description: str) -> str:
    """
    Given a free-text problem description, identify the likely gateway and issue
    and return a targeted troubleshooting guide.
    """
    description_lower = description.lower()

    # Detect gateway from description
    gateway_keywords = {
        "blockonomics": ["blockonomics", "blocko", "xpub", "gap limit"],
        "coinbase":     ["coinbase", "coinbase commerce", "cb commerce"],
        "bitpay":       ["bitpay", "bit pay"],
        "stripe":       ["stripe", "stripe bridge", "stripe crypto"],
        "nowpayments":  ["nowpayments", "now payments", "nowpay"],
        "coingate":     ["coingate", "coin gate"],
    }

    detected_gateway = None
    for gw, keywords in gateway_keywords.items():
        if any(kw in description_lower for kw in keywords):
            detected_gateway = gw
            break

    # Detect issue from description
    detected_issue = None
    for alias, key in ISSUE_ALIASES.items():
        if alias in description_lower:
            detected_issue = key
            break

    if not detected_gateway and not detected_issue:
        return (
            "I couldn't automatically identify which gateway or issue you're referring to. "
            "Please tell me:\n"
            "1. Which payment gateway are you using? (Blockonomics / Coinbase / BitPay / Stripe / NOWPayments / CoinGate)\n"
            "2. What exactly is happening? (e.g. 'address not generated', 'payment not detected', 'wrong amount')"
        )

    if detected_gateway and detected_issue:
        return get_issue_guide(detected_gateway, detected_issue)

    if detected_gateway and not detected_issue:
        return list_known_issues(detected_gateway)

    # Issue detected but no gateway
    lines = [f"It sounds like you have a **{detected_issue.replace('_', ' ')}** issue. Which gateway are you using?\n"]
    for gw in SUPPORTED_GATEWAYS:
        if detected_issue in ISSUES[gw]:
            lines.append(f"  - {gw.capitalize()}")
    lines.append("\nTell me which one and I'll give you the exact fix steps.")
    return "\n".join(lines)


# ── MCP server entry point (Python 3.10+ only) ──────────────────────────────
# Uncomment when mcp package is available:
#
# from mcp.server.fastmcp import FastMCP
# mcp = FastMCP("payment-gateway-troubleshooting")
#
# @mcp.tool()
# def troubleshoot_gateway_issue(gateway: str, issue: str) -> str:
#     """
#     Get a plain-English troubleshooting guide for a payment gateway issue.
#     gateway: blockonomics | coinbase | bitpay | stripe | nowpayments | coingate
#     issue: address_not_generated | payment_not_detected | invalid_api_key | etc.
#     """
#     return get_issue_guide(gateway, issue)
#
# @mcp.tool()
# def list_gateway_issues(gateway: str) -> str:
#     """List all known issues for a given payment gateway."""
#     return list_known_issues(gateway)
#
# @mcp.tool()
# def diagnose_payment_issue(description: str) -> str:
#     """
#     Describe your problem in plain English and get a targeted fix guide.
#     E.g. 'My Coinbase order is stuck pending after customer paid'
#     """
#     return diagnose_issue(description)
#
# if __name__ == "__main__":
#     mcp.run()
