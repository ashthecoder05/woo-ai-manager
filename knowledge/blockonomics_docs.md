# Blockonomics API Reference

## Overview
Blockonomics is a Bitcoin payment processing service. It lets merchants accept BTC payments via a simple API without custody — funds go directly to the merchant's wallet.

---

## Authentication
All API calls require an API key sent as a Bearer token:
```
Authorization: Bearer <YOUR_API_KEY>
```
Get your key at: https://www.blockonomics.co/merchants

---

## Core Endpoints

### GET /api/balance
Check the balance of one or more Bitcoin addresses.
```
GET https://www.blockonomics.co/api/balance?addr=<address>
```
**Response:**
```json
{
  "response": [
    { "addr": "1A1zP...", "confirmed": 5000000, "unconfirmed": 0 }
  ]
}
```
- Values are in **satoshis** (1 BTC = 100,000,000 satoshis)

---

### GET /api/price
Get the current BTC price in a given fiat currency.
```
GET https://www.blockonomics.co/api/price?currency=USD
```
**Response:**
```json
{ "price": 65000.00 }
```

---

### GET /api/searchhistory
Get transaction history for a Bitcoin address.
```
GET https://www.blockonomics.co/api/searchhistory?addr=<address>
```
**Response:**
```json
{
  "history": [
    {
      "txid": "abc123...",
      "value": 100000,
      "time": 1710000000,
      "confirmations": 3
    }
  ]
}
```

---

### POST /api/new_address
Generate a new Bitcoin payment address linked to your wallet.
```
POST https://www.blockonomics.co/api/new_address
Authorization: Bearer <key>
Content-Type: application/json
{ "reset": 0 }
```
**Response:**
```json
{ "address": "bc1q...", "response": 200 }
```

---

## Payment Flow
1. Customer clicks "Pay with Bitcoin"
2. Merchant calls `/api/new_address` to get a fresh BTC address
3. Merchant shows address + QR code to customer
4. Customer sends BTC
5. Blockonomics fires a **webhook** to your callback URL
6. Merchant checks `status` in webhook payload to confirm payment

---

## Webhook Payload
Blockonomics sends a GET request to your callback URL:
```
GET https://yoursite.com/webhook?secret=<secret>&addr=<address>&value=<satoshis>&txid=<txid>&status=<status>
```
Status codes:
- `0` = Unconfirmed (seen in mempool)
- `1` = Partially confirmed (< 2 blocks)
- `2` = Confirmed (2+ blocks)

---

## Rate Limits
- Balance/price: ~100 req/min per API key
- Address generation: limited to wallet gap limit (default 20 unused addresses)

---

## Key Concepts
- **xpub**: Extended public key — lets Blockonomics generate addresses without holding private keys. Never share your xprv.
- **Gap limit**: Maximum number of consecutive unused addresses (default 20). Increase in dashboard if needed.
- **Satoshi**: Smallest BTC unit. 1 BTC = 100,000,000 satoshis.
