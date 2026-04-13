# WooCommerce AI Store Manager — Product Plan

## The Pivot

**Original product:** Blocko Agent — a Bitcoin payment assistant for merchants across multiple platforms.

**New focus:** A WordPress/WooCommerce plugin that acts as an AI store manager — installed directly in WP Admin, reads the merchant's real store data, and tells them what's happening and what to do next.

**One-line pitch:**
> The AI store manager that lives inside your WordPress admin — knows your orders, customers, and revenue, and tells you what to do next.

**Target merchant:** WooCommerce store doing $10k–$80k/month. Too small to hire a real store manager. Too busy to dig through reports. Wants someone to just tell them what's happening.

---

## Competitive Landscape

| Product | What it does | Gap |
|---|---|---|
| StoreAgent | Customer chatbot + bulk content gen | No merchant analytics |
| AI Product Tools | Product content gen + storefront chat | No order/revenue intelligence |
| WoowBot | Customer support chatbot | Customer-facing only |
| StoreRadar ($15/mo) | Analytics with AI Q&A — **closest competitor** | Reactive only, no proactive alerts, no actions |
| Metorik ($50/mo) | Deep WC analytics, Slack alerts | Not AI, no chat interface |
| WooCommerce Analytics | Built-in free reporting | No AI, no natural language |

**The white space:** Proactive + actionable merchant intelligence. Nobody owns "the AI that comes to *you* with insights" inside WP Admin today.

**Risk:** WooCommerce 10.3 (late 2025) shipped native MCP support — Automattic could build this themselves. Opportunity: build on top of MCP instead of webhooks in Phase 3.

---

## Critical Risks to Keep in Mind

1. **API key friction** — requiring merchants to get their own OpenAI key loses ~80% of potential users at setup. Mitigate: give 50 free queries on your key, require signup for more.
2. **Data privacy / GDPR** — sending customer data to OpenAI. Need a clear privacy policy and data processing agreement before marketing to European merchants.
3. **Context window limits** — a store with 2,000+ orders can't be dumped into a prompt. Must be smart about which data to fetch per query.
4. **StoreRadar already exists** — head start, managed API (no key needed). Differentiate on proactive alerts and being inside WP Admin.
5. **"Why not just use ChatGPT with a CSV?"** — your answer must be: faster, no export needed, proactive, always up to date.

---

## The Key Validation Metric

> **Do merchants come back and use it a second time?**

First-use curiosity is easy. Return usage means it's genuinely useful. That's the green light for Phase 3.

---

## Phase 0 — Validate Before Writing Code
**Duration: 1–2 weeks | Cost: $0**

**Goal:** Confirm real demand before building anything.

**Actions:**
- Post in WooCommerce Facebook groups, r/woocommerce, r/Wordpress:
  > *"Would you use an AI assistant inside your WP Admin that answers questions about your orders, customers, and revenue? What would you want to ask it?"*
- Read StoreRadar's negative reviews — that's the product gap
- Search wordpress.org for "AI store manager", "WooCommerce AI" — read support threads
- Create a landing page (Carrd or Notion) with "Notify me when it launches" email capture

**Green light:** 50+ genuine responses OR 30+ email signups with specific use cases mentioned.
**Red light:** Vague enthusiasm with no specific questions they'd want to ask.

---

## Phase 1 — Build the No-Backend MVP Plugin
**Duration: 2–3 weeks | Stack: PHP + vanilla JS + OpenAI API**

Fully self-contained WordPress plugin. No custom backend. Merchant installs it, enters their OpenAI API key in Settings, and immediately gets an AI that knows their WooCommerce store.

### Plugin Structure

```
woo-ai-manager/
  woo-ai-manager.php        ← plugin entry, registers menus + settings
  includes/
    wc-data.php             ← pulls orders, products, customers from WC
    ai-client.php           ← calls OpenAI API directly (configurable endpoint for Phase 3 swap)
    cron.php                ← weekly digest via WP Cron
  admin/
    chat-panel.php          ← the main WP Admin chat UI
    dashboard-widget.php    ← quick insight cards on WP dashboard home
    settings-page.php       ← API key input + configuration
```

### Features

| Feature | Description | Effort |
|---|---|---|
| WP Admin chat | Merchant asks questions, AI answers with real WC data | High |
| Insight cards | One-click: "Summarise this week" / "Stuck orders" / "Top products" | Medium |
| Dashboard widget | Shows today's revenue + 1 AI-generated insight on WP home | Low |
| Stock alerts | Low inventory warnings as WP Admin notices | Low |
| Weekly digest | WP Cron emails a plain-English summary every Monday | Medium |
| Settings page | API key input, model selection, digest opt-in | Low |

### What to deliberately skip in Phase 1
- Customer-facing storefront widget
- Any backend / auth system
- Billing or usage limits
- Multi-language support
- Actions (the AI only reads, doesn't write)

### Design decision for Phase 3 readiness
`ai-client.php` must have a configurable endpoint. In Phase 1 it points to OpenAI directly. In Phase 3, changing one config value points it to your own backend. No rewrite needed.

### What to reuse from the existing codebase
- `agent/system_prompt.py` — port the WooCommerce knowledge, tone rules, and honesty rules into the PHP system prompt
- `webhook/handler.py` — reference for which WC order fields to parse and the status code map
- `merchant_demo/` — use as a test store while building the plugin

---

## Phase 2 — Launch & Validate Demand
**Duration: 4 weeks**

### Week 1 — Soft launch
- Submit to wordpress.org plugin directory (free listing, ~5 day review)
- Post in communities you already validated in Phase 0
- Give to 5–10 people from your email list, do a 20-min call with each

### Week 2–3 — Watch the data
- Track: installs, activation rate, how long they keep it active
- Log what questions merchants actually type — this is your product roadmap
- Read every wordpress.org support thread

### Week 4 — Decision point

| Signal | What it means |
|---|---|
| 200+ installs, return usage | Build Phase 3 |
| Installs but churn at API key setup | Fix onboarding or move to managed API |
| Low installs, little engagement | Wrong audience or positioning — pivot |

---

## Phase 3 — Add Backend, Remove Friction, Monetise
**Duration: 4–6 weeks | Only if Phase 2 validates**

### Key changes
- **Remove "bring your own API key"** — 50 free queries on your key, signup for more. You control cost and collect emails.
- **Managed auth** — plugin calls your backend instead of OpenAI directly. One config change in `ai-client.php`.
- **Proactive alerts** — server-side jobs detect low stock, stuck orders, revenue drops, push to WP Admin
- **Email digest** — proper transactional emails from backend, not WP Cron
- **Pricing:** Free tier (50 queries/month) → $9/mo for unlimited + alerts + digest

### What's already built in the existing codebase for Phase 3

| Component | File | Status |
|---|---|---|
| WC webhook receiver | `webhook/handler.py` | Done |
| Merchant DB (upsert, get, analytics) | `services/db.py` | Done |
| Chat API endpoint | `main.py` → `/api/chat` | Done |
| Merchant auth + session tokens | `main.py` | Done |
| Orders + analytics endpoints | `main.py` → `/api/orders`, `/api/analytics` | Done |
| System prompt (WC knowledge) | `agent/system_prompt.py` | Done — extend for store manager persona |
| WordPress plugin (PHP) | — | Build in Phase 1 |
| WP Admin chat panel (JS) | — | Build in Phase 1 |
| Proactive alert scheduler | — | Build in Phase 3 |

The plugin in Phase 3 is just a thin WP client that calls the existing backend. Almost no backend work needed.

---

## Timeline Summary

```
Week 1–2    Phase 0 — Validate. Post in communities, collect emails.
Week 3–5    Phase 1 — Build the plugin. PHP + OpenAI. No backend.
Week 6      Submit to wordpress.org. Give to early list.
Week 7–10   Phase 2 — Watch installs, usage, feedback. Do user calls.
Week 11+    Phase 3 — Only if validated. Managed API, billing, alerts.
```

---

## Monetisation Options (Phase 3)

| Model | Pros | Cons |
|---|---|---|
| $9/mo SaaS | Predictable revenue, scalable | Harder sell to small merchants |
| One-time $49 (BYOK) | Easy impulse buy, AppSumo-friendly | No recurring revenue |
| Free + $9/mo upgrade | Maximises installs, classic freemium | Need volume to profit |

**Recommendation:** Free tier (50 queries) → $9/mo for unlimited + proactive alerts.

---

## Starting Point for Next Session

1. Check Phase 0 results — did you post and collect responses?
2. If green light → start with `woo-ai-manager.php` (plugin skeleton + settings page)
3. Then `includes/wc-data.php` (fetch orders, products, customers from WC)
4. Then `includes/ai-client.php` (call OpenAI, build system prompt from existing `agent/system_prompt.py` knowledge)
5. Then `admin/chat-panel.php` (the WP Admin UI)
