# WooCommerce AI Store Manager — Product Plan
*Last updated: April 2026*

## The Pivot

**Original product:** Blocko Agent — a Bitcoin payment assistant for merchants across multiple platforms.

**New focus:** A WordPress/WooCommerce plugin that acts as an AI store manager — installed directly in WP Admin, reads the merchant's real store data, and tells them what's happening and what to do next.

**One-line pitch:**
> The AI store manager that lives inside your WordPress admin — knows your orders, customers, and revenue, and tells you what to do next.

**Target merchant:** WooCommerce store doing $10k–$80k/month. Too small to hire a real store manager. Too busy to dig through reports. Wants someone to just tell them what's happening.

---

## What's Already Built (April 2026)

The following is fully working and tested against a local WooCommerce demo store:

### Backend (FastAPI — Python)
| Component | File | Status |
|---|---|---|
| Azure OpenAI client (GPT deployment) | `agent/core.py` | Done |
| Plugin chat endpoint | `main.py → /api/plugin/chat` | Done |
| Plugin signin endpoint (Google SSO) | `main.py → /api/plugin/signin` | Done |
| Plugin config endpoint | `main.py → /api/plugin/config` | Done |
| Merchant DB (SQLite/Postgres) | `services/db.py` | Done |
| Plugin credit tracking (50 free) | `services/db.py` | Done |
| WC webhook receiver | `webhook/handler.py` | Done |
| Merchant auth + session tokens | `main.py` | Done |
| Orders + analytics endpoints | `main.py` | Done |

### WordPress Plugin (`woo-ai-manager/`)
| Component | File | Status |
|---|---|---|
| Plugin entry + menus + AJAX | `woo-ai-manager.php` | Done |
| Live WC data snapshot (PHP) | `includes/wc-data.php` | Done |
| Backend API client | `includes/ai-client.php` | Done |
| Google SSO settings page | `admin/settings-page.php` | Done |
| Chat panel + quick actions | `admin/chat-panel.php` | Done |
| Dashboard widget | `admin/dashboard-widget.php` | Done |
| CSS + JS | `admin/wam-admin.css`, `wam-chat.js` | Done |
| readme.txt | `readme.txt` | Done (needs placeholders filled) |
| LICENSE (GPL-2.0) | `LICENSE` | Done |

### Demo Store
- WordPress 6.9.4 + WooCommerce 10.6.2 running at `http://localhost:8080`
- 18 sample products with stock management enabled
- 30 realistic orders across 8 customers over 60 days
- Admin: `admin` / `admin123`

### What the plugin does today
- Merchant signs in with Google → gets 50 free AI queries
- Plugin pulls live store data (revenue, recent orders, top products, low stock)
- Sends to backend → Azure OpenAI answers in plain English
- Chat panel with 4 quick-action buttons
- Dashboard widget with today's revenue + low stock alerts
- Credits shown and decremented per query
- Upgrade card shown at 0 credits
- Session expiry handled gracefully

---

## Competitive Landscape (Updated 2026)

| Product | What it does | Gap |
|---|---|---|
| **Shopify Sidekick** | Full AI store manager — analytics, coupon creation, product edits, theme changes, proactive Pulse alerts | Shopify-only, no WooCommerce |
| StoreAgent | Customer chatbot + bulk content gen | No merchant analytics |
| StoreRadar ($15/mo) | Analytics with AI Q&A | Reactive only, no actions |
| Metorik ($50/mo) | Deep WC analytics, Slack alerts | Not AI, no chat interface |
| WooCommerce Analytics | Built-in free reporting | No AI, no natural language |

### Shopify Sidekick — What It Does (2026)
Sidekick is the most complete AI store manager available. Understanding it precisely defines our target:

**What it can do:**
- Natural language analytics: "Why are sales down this month?" — cross-references traffic, conversion, inventory, AOV in one answer
- Coupon/discount creation from plain English with preview + confirm
- Product description generation with SEO keyword targets
- Bulk product edits from chat
- Theme visual editing (change button colour, layout) via natural language
- Shopify Flow workflow generation from plain English
- Customer segment queries and saving
- App recommendations + direct install from chat
- Proactive Pulse alerts (live 2026): surfaces issues without being asked
- Voice interface (mobile, 2026)
- Screen sharing for visual guidance

**What it cannot do (confirmed gaps):**
- No scheduled email digest — merchants must go ask it
- No customer-facing / support ticket capability
- No cross-platform integrations (Klaviyo, Zendesk, etc.) without manual setup
- Shopify-only — WooCommerce merchants have nothing equivalent
- Merchant data lives on Shopify's cloud — no data ownership

**Our differentiators vs Sidekick:**
1. Works on WooCommerce — 6M+ stores with no AI store manager today
2. Weekly digest email — proactive, scheduled, no asking required (Sidekick still can't do this)
3. Merchant owns their data — not locked into a platform
4. No platform risk — Shopify can deprecate Sidekick or change pricing; this is your own plugin

---

## The Architecture Shift: WooCommerce MCP (Critical)

**WooCommerce 10.3 (shipped late 2025) has a native MCP server built in.**

This changes the architecture fundamentally:

### Current approach (static snapshot)
```
Merchant asks question
→ PHP pulls fixed snapshot: revenue totals + 5 orders + 5 products + low stock
→ Dump into system prompt as text
→ AI answers from static context
```
Works fine for simple Q&A. Limitations: fixed data shape, can't answer complex queries, can't take actions.

### MCP approach (dynamic tool calls)
```
Merchant asks question
→ AI decides what data it needs
→ Calls MCP tools: get_orders, get_products, search_customers, create_coupon...
→ Gets exactly the right data on demand
→ Answers with precision, takes actions with confirmation
```

**What WC MCP exposes:**

| Tool | Capability |
|---|---|
| `get_orders` | Query with filters: status, date, customer, amount range |
| `get_order` | Full single order detail |
| `get_products` | Filter by stock, category, status, price |
| `get_customers` | Query with filters: spend, last order date, location |
| `get_reports` | Revenue, top sellers, refunds, coupons |
| `create_coupon` | Create discount codes with full config |
| `update_product` | Edit price, stock, description, status |
| `update_order` | Change status, add order notes |

**Why this matters for the roadmap:**
- Phase 1 (now): Static snapshot → validates the concept, ships fast
- Phase 2: Replace snapshot with MCP tool calls → AI gets exactly what it needs, write actions become possible (coupon creation, product edits, order updates)
- Phase 3: Proactive agents — WP Cron triggers MCP queries → AI analysis → push alerts to WP Admin

The original plan said "build on top of MCP in Phase 3." Given WC MCP is already live in 2026, this moves to **Phase 2**.

---

## Critical Risks

1. **API key friction** — RESOLVED. We use Google SSO + our own Azure OpenAI key. Merchants need nothing.
2. **Data privacy / GDPR** — sending store data to Azure OpenAI. Need privacy policy before marketing to European merchants. Data processing agreement required.
3. **Context window limits** — RESOLVED for now with static snapshot. MCP in Phase 2 solves this properly — AI only fetches what it needs.
4. **"Why not just use ChatGPT with a CSV?"** — answer is: no export needed, always live, proactive, inside WP Admin where the merchant already is.
5. **Sidekick already exists** — but it's Shopify-only. WooCommerce has 6M+ stores and nothing comparable. This is the gap.
6. **WooCommerce MCP deprecation risk** — low. It's a core WC feature following an open standard.

---

## The Key Validation Metric

> **Do merchants come back and use it a second time?**

First-use curiosity is easy. Return usage means it's genuinely useful. That's the green light for Phase 2.

Secondary metric: **What questions do merchants actually type?** This is the product roadmap.

---

## Phase 0 — Validate Before Writing Code ✓
**Status: Should be done or in progress**

- Post in WooCommerce Facebook groups, r/woocommerce, r/Wordpress
- Read StoreRadar's negative reviews for the product gap
- Create a landing page with email capture
- **Green light:** 50+ genuine responses OR 30+ email signups with specific use cases

---

## Phase 1 — Plugin MVP ✓ (Mostly Done)
**Status: Built and working locally**

### What's done
- Google SSO login with 50 free credits
- Live store context: revenue, orders, top products, low stock
- Chat panel with quick actions
- Dashboard widget
- Backend on Azure OpenAI (your key, not merchant's)
- Credit tracking and upgrade prompts
- readme.txt, LICENSE, plugin structure ready for wordpress.org

### Still needed before submission
| Item | What |
|---|---|
| PLACEHOLDER_WP_USERNAME | Your wordpress.org username (for readme.txt) |
| PLACEHOLDER_PLUGIN_URL | Plugin website URL |
| PLACEHOLDER_AUTHOR_URL | Your website URL |
| PLACEHOLDER_UPGRADE_URL | Pricing/upgrade page URL (set in `woo-ai-manager.php`) |
| PLACEHOLDER_SUPPORT_EMAIL | Support email (in settings-page.php error message) |
| PLACEHOLDER_PRIVACY_URL | Privacy policy URL (in readme.txt) |
| 3 screenshots | PNG screenshots of plugin UI for wordpress.org |
| Plugin icon | 128×128 and 256×256 PNG icons |
| Production backend URL | Replace `http://localhost:8000` in `ai-client.php` |

---

## Phase 2 — MCP Integration + Write Actions
**Duration: 3–4 weeks | Only after Phase 1 validates**

### Key changes from Phase 1

**Replace static snapshot with MCP tool calls**
- Remove the fixed `wam_get_store_context()` PHP snapshot
- Connect the backend to WooCommerce's native MCP server
- AI calls tools on demand: fetches exactly the data needed per query
- Enables complex queries: "customers who spent >$500 but haven't ordered in 60 days"

**Add write actions with confirmation**
All actions show a preview card. Merchant confirms before anything changes.

| Action | Plain English example |
|---|---|
| Create coupon | "Create 20% off for orders over $50, expires Friday, max 100 uses" |
| Product price edit | "Put all hoodies on 15% sale until end of month" |
| Bulk stock update | "Mark the Belt as out of stock" |
| Order status update | "Mark order #1234 as completed" |
| Product description | "Write a better description for the Hoodie emphasising warmth" |

**Add proactive Pulse-equivalent alerts**
- WP Cron runs daily — calls MCP tools — AI analyses — surfaces insights in WP Admin notices
- Examples: "3 orders have been pending for 48h", "Hoodie stock will run out at current velocity in 4 days", "Revenue is 30% below last week's pace"

**Add weekly digest email**
- Runs Monday 9am via WP Cron
- Pulls full 7-day picture via MCP
- LLM writes a plain-English summary: what sold, what didn't, what to watch
- This is a confirmed gap in Shopify Sidekick — they can't do scheduled digests

### Phase 2 feature priority
1. MCP integration (foundation for everything else)
2. Coupon creation from chat (highest-value, most-loved Sidekick feature)
3. Weekly digest email (differentiator vs Sidekick)
4. Proactive alerts (parity with Sidekick Pulse)
5. Product edits from chat
6. Customer segment queries

---

## Phase 3 — Launch & Monetise
**Duration: 4 weeks | Only if Phase 2 validates return usage**

### Week 1 — Soft launch
- Submit to wordpress.org plugin directory (free listing, ~5 day review)
- Post in communities validated in Phase 0
- Give to 5–10 people from email list, do a 20-min call with each

### Week 2–3 — Watch the data
- Track: installs, activation rate, how long they stay active
- Log what questions merchants type — this is the roadmap
- Read every wordpress.org support thread

### Week 4 — Decision point

| Signal | What it means |
|---|---|
| 200+ installs, return usage | Build Phase 4 (billing, scale) |
| Installs but churn at sign-in | Fix onboarding |
| Low installs, little engagement | Wrong audience or positioning — pivot |

---

## Phase 4 — Scale (Only if Phase 3 validates)

- Proper billing: Stripe, $9/mo for unlimited + alerts + digest
- Usage analytics dashboard for you (which merchants use what, credit burn rate)
- GDPR data processing agreement and privacy policy
- Multi-site / agency pricing
- Storefront customer chat as a separate add-on (different product, different buyer)

---

## Features to Skip (Now and Possibly Forever)

| Feature | Why |
|---|---|
| Theme editing via chat | WP/WC themes have no programmatic schema API. Structurally impossible without theme-specific work for every theme. |
| Workflow/automation builder | No native equivalent of Shopify Flow in WooCommerce. Would require building an entire automation engine. |
| Traffic/SEO analytics | Not in WC data model. Requires Google Analytics OAuth integration — too complex. |
| Voice interface | Low value until core text chat is validated. |
| Email campaign sending | Requires Klaviyo/Mailchimp API — too many moving parts. Offer "copy this text" workaround. |
| App recommendations/install | WP plugin directory has no install API accessible from within a plugin. |
| Autonomous actions (no approval) | Liability risk. Always require merchant confirmation for writes. |
| Storefront customer chatbot | Completely different product and buyer. Don't conflate. |

---

## Monetisation

**Recommendation:** Free tier (50 queries) → $9/mo unlimited + proactive alerts + digest

| Model | Pros | Cons |
|---|---|---|
| $9/mo SaaS | Predictable revenue, scalable | Harder sell to small merchants |
| One-time $49 | Easy impulse buy, AppSumo-friendly | No recurring revenue |
| Free + $9/mo upgrade | Maximises installs, classic freemium | Need volume to profit |

---

## Timeline Summary

```
Now         Phase 1 complete — fill placeholders, get screenshots, submit to wordpress.org
Week 1–2    Phase 0 — validate demand (if not done). Post in communities.
Week 3      Submit to wordpress.org. Give to early email list.
Week 4–6    Watch installs, usage, feedback. Do user calls.
Week 7–10   Phase 2 — MCP integration + write actions + digest (if validated)
Week 11+    Phase 3/4 — billing, scale (only if validated)
```

---

## Starting Point for Next Session

1. Fill in the 9 placeholder items listed in Phase 1 above
2. Take 3 screenshots of the plugin for wordpress.org
3. Create plugin icon (128×128, 256×256 PNG)
4. Deploy backend to production (Railway/Render — config already in repo)
5. Submit to wordpress.org

Then watch what merchants type. That becomes Phase 2's feature list.
