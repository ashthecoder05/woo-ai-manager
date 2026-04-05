# Blockonomics on Shopify

## Requirements
- Shopify Basic plan or higher
- Blockonomics account with API key
- Note: Shopify does NOT allow custom payment gateways — use the hosted redirect approach

## Integration Method
Shopify restricts third-party payment processors, so Blockonomics uses a **hosted payment page** redirect.

## Setup Steps
1. In Blockonomics dashboard → **Merchants → Stores → Add Store**
2. Choose **Shopify** as the platform
3. Copy the generated **payment link template**
4. In Shopify admin: **Settings → Checkout → Additional Scripts**
5. Paste the redirect script provided by Blockonomics

## Checkout Flow
1. Customer selects "Bitcoin" at checkout
2. Shopify redirects to `pay.blockonomics.co` with order details
3. Customer pays on the hosted page
4. Blockonomics sends a webhook back to your store
5. Order is marked paid automatically

## Limitations
- Cannot fully customize the payment UI (it's hosted by Blockonomics)
- Refunds must be handled manually (send BTC back to customer's address)
- No direct API access to Shopify orders from within Blockonomics webhooks

## Webhook Callback URL
Set in Blockonomics dashboard:
```
https://yourshopifystore.myshopify.com/apps/blockonomics/callback
```

## Testing
Use Blockonomics' test mode — set a tiny BTC amount (e.g., 1000 satoshis) in a test product and walk through the full checkout flow.
