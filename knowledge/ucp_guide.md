# UCP — Universal Commerce Protocol

## What is UCP?
UCP (Universal Commerce Protocol) is a standard that lets AI agents discover and interact with online merchants automatically. Instead of a human reading a website, an AI can fetch `/.well-known/ucp` and instantly understand:
- What the merchant sells
- How to pay (payment methods, APIs)
- What confirmations are required
- Where to send webhooks

Manifest format: **JSON-LD** using **Schema.org** vocabulary, served at `/.well-known/ucp`.

---

## Why Use UCP for Bitcoin?
- AI shopping agents can autonomously pay with BTC without human input
- Standardized — any compliant agent can integrate without custom code
- No custodial risk — BTC goes directly to merchant's wallet
- Machine-readable instructions for address generation and payment flow

---

## Minimal Valid Manifest
```json
{
  "@context": ["https://schema.org", {"ucp": "https://ucp.dev/vocab#"}],
  "@type": ["Organization", "ucp:Merchant"],
  "name": "My Store",
  "url": "https://mystore.com",
  "ucp:apiVersion": "1.0",
  "ucp:capabilities": ["bitcoin-payment", "webhook-notification"],
  "ucp:paymentMethods": [
    {
      "@type": "PaymentMethod",
      "name": "Bitcoin (BTC)",
      "identifier": "bitcoin",
      "provider": "Blockonomics",
      "currency": "BTC",
      "confirmationsRequired": 2,
      "addressEndpoint": "https://mystore.com/api/btc/new-address",
      "webhookEndpoint": "https://mystore.com/webhook/blockonomics"
    }
  ],
  "ucp:agentInstructions": "POST to /api/btc/new-address for a payment address. Send exact BTC. Payment confirmed after 2 blocks."
}
```

---

## Schema.org Validation Rules
- `@context` must include `https://schema.org`
- `@type` must include `Organization`
- `name` and `url` are required
- `url` must be a valid https URL
- `ucp:paymentMethods` must be a non-empty array
- Each payment method must have `@type: PaymentMethod`
- `addressEndpoint` and `webhookEndpoint` must be valid URLs
- `confirmationsRequired` must be a non-negative integer

---

## Common Mistakes
| Error | Fix |
|-------|-----|
| Missing `@context` | Add `"@context": ["https://schema.org", ...]` |
| `url` is HTTP not HTTPS | Use HTTPS in production |
| `ucp:paymentMethods` is empty | Add at least one payment method |
| `addressEndpoint` is localhost | Use your public domain URL |
| Missing `ucp:agentInstructions` | Add a plain-English description of how to pay |

---

## How an AI Agent Uses Your Manifest
1. Agent fetches `GET /.well-known/ucp`
2. Reads `ucp:paymentMethods` to find Bitcoin support
3. POSTs to `addressEndpoint` to get a fresh BTC address
4. Sends payment to that address
5. Your server receives the webhook at `webhookEndpoint`
6. Order is fulfilled after `confirmationsRequired` blocks
