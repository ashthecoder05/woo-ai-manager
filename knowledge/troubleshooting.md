# Blockonomics Troubleshooting Guide

## Payment Not Detected

**Symptom:** Customer paid but order status didn't update.

**Fixes:**
1. Check that your webhook callback URL is publicly accessible (not localhost)
2. Verify the `secret` parameter in the webhook URL matches what's set in your Blockonomics dashboard
3. Check your server logs — did the webhook GET request arrive?
4. Ensure the address shown to the customer was generated via `/api/new_address`, not reused
5. Confirm the customer sent to the exact address (no typos in QR scan)

---

## "Invalid API Key" Error

**Symptom:** API returns 401 or "Unauthorized".

**Fixes:**
1. Copy the key directly from https://www.blockonomics.co/merchants — no spaces
2. Confirm you're sending `Authorization: Bearer <key>` (not `Token` or `Basic`)
3. Check the key hasn't been regenerated/revoked in the dashboard

---

## Address Generation Fails / Gap Limit

**Symptom:** `/api/new_address` returns an error about gap limit.

**Fixes:**
1. Increase the gap limit in Blockonomics dashboard → Settings → Gap limit (set to 100+)
2. Ensure your xpub is correctly registered
3. Do not generate addresses faster than customers pay (each unused address counts toward the gap)

---

## Webhook Not Firing

**Symptom:** Payment confirmed on-chain but your server never received a callback.

**Fixes:**
1. Your callback URL must be HTTPS and publicly reachable
2. In Blockonomics dashboard, re-save the callback URL to trigger a test ping
3. Check firewall/CDN rules — Blockonomics IPs must not be blocked
4. Use `ngrok` for local testing: `ngrok http 8000` → use the ngrok URL as callback

---

## Wrong BTC Amount

**Symptom:** Customer sent USD amount but BTC amount is off.

**Fixes:**
1. Always fetch the price fresh via `/api/price` at checkout time
2. Add a small buffer (e.g., 1%) for price volatility
3. Use the `value` field in the webhook (in satoshis) as the source of truth, not the generated invoice

---

## Double-Spend / Unconfirmed Risk

**Symptom:** You fulfilled an order on `status=0` (unconfirmed) and the transaction got replaced.

**Fix:**
- For digital goods: wait for `status=1` (1 confirmation)
- For physical goods / high value: wait for `status=2` (2+ confirmations)
- Never fulfill on `status=0` for irreversible goods

---

## WooCommerce Plugin Issues

- Ensure the plugin version matches your WordPress/WooCommerce version
- After updating xpub, go to WooCommerce → Settings → Payments → Blockonomics → Save
- Clear any object-cache plugins after saving settings

---

## Shopify Integration Issues

- Shopify does not support custom payment gateways natively — use Blockonomics' hosted payment page redirect
- Ensure your store's "Additional scripts" field includes the redirect snippet

---

## Common HTTP Status Codes from Blockonomics
| Code | Meaning |
|------|---------|
| 200  | Success |
| 401  | Invalid or missing API key |
| 409  | Gap limit exceeded |
| 500  | Blockonomics server error — retry with backoff |
