# Product Description Templates — Bitcoin Commerce

## Checklist for a Good Product Description
- [ ] States the product clearly in the first sentence
- [ ] Mentions Bitcoin/BTC as a payment option
- [ ] Highlights a key benefit (security, privacy, no chargebacks)
- [ ] Includes a call-to-action (Buy with Bitcoin, Pay securely, etc.)
- [ ] 100–400 characters optimal
- [ ] Optional: verifiable on-chain proof link

---

## Template A — Digital Product
```
{Product Name} — {One-line value proposition}.

Pay instantly with Bitcoin (BTC) — no chargebacks, no middlemen, funds go
directly to our wallet. {Key feature or differentiator}.

{CTA}: {URL or button label}

🔗 Payments verified on-chain: {blockchain_explorer_link}
```

### Example (filled in):
```
Premium VPN License (1 Year) — Anonymous browsing, 50+ countries.

Pay instantly with Bitcoin (BTC) — no chargebacks, no middlemen, funds go
directly to our wallet. Activate in seconds after payment confirmation.

Buy with Bitcoin: checkout.example.com

🔗 Payments verified on-chain: mempool.space/address/bc1q...
```

---

## Template B — Physical Product
```
{Product Name} — {Short description, 1-2 sentences}.

Ships worldwide. Pay with Bitcoin for maximum privacy — no credit card
required, no data stored. {Confirmations} blockchain confirmations required.

{Price} USD | {BTC equivalent at checkout}
[Pay with Bitcoin →]
```

### Example (filled in):
```
Hardware Wallet Case (Leather) — Premium leather sleeve for Ledger & Trezor.

Ships worldwide. Pay with Bitcoin for maximum privacy — no credit card
required, no data stored. 2 blockchain confirmations required.

$29 USD | ~0.00045 BTC at checkout
[Pay with Bitcoin →]
```

---

## Template C — Service / Subscription
```
{Service Name} — {Benefit-focused headline}.

{Short description of what you get}. Bitcoin payments are non-custodial —
your payment goes directly to our wallet, not a payment processor.

Plans from {price}. {Low/zero} fees. Cancel anytime.
[Start with Bitcoin]
```

---

## Optimization Tips
- **Lead with the product**, not the payment method
- Add BTC equivalent price at checkout time (fetched fresh from API)
- Link to `mempool.space/address/{your_address}` for on-chain proof of volume
- Avoid mentioning volatile prices in static descriptions — show USD + "BTC amount at checkout"
- For high-value items, state "2 confirmations required (~20 min)" to set expectations
