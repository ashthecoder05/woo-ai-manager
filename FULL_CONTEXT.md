# HeySarva — Full Context & Operations Guide

> **Product**: HeySarva — AI store manager that lives inside WooCommerce  
> **Domain**: heysarva.com  
> **Created**: April 17, 2026  
> **Author**: Aishwarya Adyanthaya

---

## Table of Contents

1. [Product Overview](#1-product-overview)
2. [Architecture](#2-architecture)
3. [Infrastructure Setup](#3-infrastructure-setup)
4. [Domain & DNS (Namecheap + Cloudflare)](#4-domain--dns-namecheap--cloudflare)
5. [VPS Setup (Hostinger)](#5-vps-setup-hostinger)
6. [SSL/TLS Configuration](#6-ssltls-configuration)
7. [Nginx Configuration](#7-nginx-configuration)
8. [Backend Deployment (Docker)](#8-backend-deployment-docker)
9. [Landing Page](#9-landing-page)
10. [WordPress Plugin](#10-wordpress-plugin)
11. [Google OAuth Setup](#11-google-oauth-setup)
12. [Database](#12-database)
13. [Security](#13-security)
14. [Backups](#14-backups)
15. [Environment Variables](#15-environment-variables)
16. [Useful Commands](#16-useful-commands)
17. [Deployment Workflow](#17-deployment-workflow)
18. [Troubleshooting](#18-troubleshooting)
19. [FAQs](#19-faqs)
20. [Cost Breakdown](#20-cost-breakdown)

---

## 1. Product Overview

### What is HeySarva?

HeySarva is a WordPress/WooCommerce plugin that adds an AI-powered store manager to the WP Admin. Store owners can ask questions in plain English about their revenue, orders, inventory, and customers — and get instant, data-driven answers.

### How it works

1. Store owner installs the WordPress plugin
2. Signs in with Google (gets 50 free AI queries)
3. Opens the HeySarva chat panel in WP Admin
4. Asks questions like "What's my revenue today?" or "Which products are low on stock?"
5. The plugin extracts live store data (orders, products, revenue) from WooCommerce
6. Sends the data + question to the HeySarva backend (FastAPI)
7. Backend uses Azure OpenAI to generate an intelligent response
8. Response is streamed back to the chat panel

### Key Features

- **Revenue Insights**: Daily/weekly/monthly revenue breakdowns
- **Order Management**: Search, filter, and check order status
- **Stock Alerts**: Low stock warnings and restock recommendations
- **Customer Intelligence**: Top customers, repeat buyers, spending patterns
- **Dashboard Widget**: At-a-glance stats on the WP Dashboard
- **Privacy First**: No customer emails/names stored beyond the request

### Credit System

- **Free tier**: 50 AI queries per merchant
- **Tracking**: `merchants.plugin_credits` column in PostgreSQL
- **Deduction**: 1 credit per `/api/plugin/chat` request
- **At zero**: Query blocked, "Upgrade" card shown in chat panel

---

## 2. Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│  WooCommerce Store (WordPress)                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  HeySarva Plugin (PHP)                                │  │
│  │  - Chat Panel (admin/chat-panel.php + wam-chat.js)    │  │
│  │  - Settings Page (admin/settings-page.php)            │  │
│  │  - Dashboard Widget (admin/dashboard-widget.php)      │  │
│  │  - Store Data Extractor (includes/wc-data.php)        │  │
│  │  - Backend Client (includes/ai-client.php)            │  │
│  └───────────────────────┬───────────────────────────────┘  │
│                          │ HTTPS                             │
└──────────────────────────┼──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Cloudflare (CDN + SSL + DDoS Protection)                   │
│  - DNS: heysarva.com → VPS IP (proxied)                     │
│  - SSL: Full (Strict) with Origin Certificate               │
│  - Free plan                                                │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  VPS — Hostinger KVM 1 (2.24.209.83)                        │
│  Ubuntu 22.04 LTS | 1 vCPU | 4GB RAM | 50GB NVMe           │
│                                                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Nginx (reverse proxy + static files)                  │ │
│  │  - Port 80  → redirect to 443                          │ │
│  │  - Port 443 → SSL termination                          │ │
│  │  - /         → /var/www/heysarva (landing page)        │ │
│  │  - /api/*    → proxy to localhost:8000 (FastAPI)        │ │
│  │  - /webhook/* → proxy to localhost:8000                 │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌─── Docker Compose ────────────────────────────────────┐  │
│  │                                                       │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  │  │
│  │  │  FastAPI     │  │  PostgreSQL  │  │  Redis      │  │  │
│  │  │  (app)       │  │  (db)        │  │             │  │  │
│  │  │  port 8000   │  │  port 5432   │  │  port 6379  │  │  │
│  │  │  2 workers   │  │  v16-alpine  │  │  v7-alpine  │  │  │
│  │  └─────────────┘  └──────────────┘  └─────────────┘  │  │
│  │                                                       │  │
│  │  Volumes: pgdata, redisdata, appdata                   │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  Firewall (UFW): only ports 22, 80, 443 open               │
└─────────────────────────────────────────────────────────────┘
```

### Request Flow (Chat Query)

```
1. User types "What's my revenue today?" in WP Admin
2. wam-chat.js sends AJAX to WordPress (admin-ajax.php)
3. WordPress handler (wam_ajax_chat) calls wc-data.php
4. wc-data.php extracts live store context from WooCommerce:
   - Today's revenue, 7-day revenue, 30-day revenue
   - Recent orders (status, totals, customer names)
   - Top products by revenue
   - Low stock items
5. ai-client.php sends { store_context + question + session_token }
   to https://heysarva.com/api/plugin/chat
6. FastAPI backend:
   a. Validates session token
   b. Checks credit balance (decrement if allowed)
   c. Sends store context + question to Azure OpenAI
   d. OpenAI agent uses tools (get_revenue, get_orders, etc.)
   e. Returns AI response
7. Response streamed back to wam-chat.js
8. Displayed in the chat panel
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| **Plugin** | PHP 7.4+, vanilla JavaScript, CSS |
| **Backend** | Python 3.11, FastAPI 0.115.0, Uvicorn |
| **AI** | Azure OpenAI (GPT-5-chat deployment) |
| **Database** | PostgreSQL 16 (Docker) |
| **Cache** | Redis 7 (Docker) |
| **Web Server** | Nginx |
| **SSL** | Cloudflare Origin Certificate |
| **CDN/Security** | Cloudflare (free plan) |
| **Hosting** | Hostinger KVM 1 VPS |
| **DNS** | Cloudflare (nameservers) |
| **Domain** | Namecheap (heysarva.com) |
| **Auth** | Google OAuth 2.0 |
| **Containerization** | Docker + Docker Compose |

---

## 3. Infrastructure Setup

### What We Bought

| Item | Provider | Payment | Cost |
|------|----------|---------|------|
| Domain (heysarva.com) | Namecheap | Bitcoin | ~$10/yr |
| VPS (KVM 1) | Hostinger | Bitcoin (via BitPay) | £4.99/mo |
| Cloudflare | Cloudflare | Free | $0 |
| SSL Certificate | Cloudflare Origin CA | Free | $0 |
| Google OAuth | Google Cloud | Free | $0 |
| Azure OpenAI | Microsoft Azure | Existing account | Usage-based |

### Why These Choices

- **Namecheap**: Supports BTC payments, cheap domains
- **Hostinger KVM 1**: BTC via BitPay, 4GB RAM is plenty for launch, one-click Ubuntu
- **Cloudflare**: Free SSL, CDN, DDoS protection, hides server IP
- **Self-hosted PostgreSQL + Redis**: No extra cost, data stays on your server

---

## 4. Domain & DNS (Namecheap + Cloudflare)

### What We Did

1. **Bought heysarva.com** on Namecheap with Bitcoin
2. **Created Cloudflare account** (free plan)
3. **Added heysarva.com** to Cloudflare → "Connect a domain"
4. **Changed nameservers** in Namecheap from:
   ```
   dns1.namecheaphosting.com
   dns2.namecheaphosting.com
   ```
   to:
   ```
   josephine.ns.cloudflare.com
   rustam.ns.cloudflare.com
   ```
5. **Set DNS A record**: `heysarva.com` → `2.24.209.83` (Proxied)
6. **CNAME www** → `heysarva.com` (Proxied)

### Why Cloudflare?

- **Free SSL**: No need to buy/manage certificates
- **CDN**: Landing page loads fast globally
- **DDoS protection**: Blocks attacks before they reach VPS
- **Hides VPS IP**: Attackers can't find your real server
- **DNS management**: Easy A record changes

### DNS Record Cleanup

Namecheap auto-created many records (cpanel, webmail, ftp, etc.) pointing to their servers. These are unnecessary and can be deleted:
- `A autoconfig`, `A autodiscover`, `A cpanel`, `A cpcalendars`, `A cpcontacts`
- `A ftp`, `A mail`, `A webdisk`, `A webmail`, `A whm`
- All `SRV` records
- Old `TXT` records (except `_dmarc` and `default._domainkey` if using email)

**Deleting these has no impact** — they point to Namecheap's empty server.

### DNS Propagation

- Nameserver changes can take **1-24 hours** to propagate globally
- A record changes through Cloudflare propagate in **2-5 minutes**
- You can check propagation: `dig heysarva.com NS +short`

---

## 5. VPS Setup (Hostinger)

### Server Details

| Property | Value |
|----------|-------|
| **Provider** | Hostinger |
| **Plan** | KVM 1 |
| **IP** | 2.24.209.83 |
| **OS** | Ubuntu 22.04 LTS |
| **CPU** | 1 vCPU |
| **RAM** | 4 GB |
| **Disk** | 50 GB NVMe |
| **Bandwidth** | 4 TB |
| **Location** | United States - Boston 2 |
| **SSH** | `ssh root@2.24.209.83` |

### What We Installed

1. **System update**: `apt-get update && apt-get upgrade`
2. **Nginx**: Reverse proxy + static file serving
3. **Docker + Docker Compose**: Container runtime
4. **UFW Firewall**: Ports 22/80/443 only

### RAM Usage

| Service | Approximate RAM |
|---------|----------------|
| FastAPI (2 workers) | ~400 MB |
| PostgreSQL | ~200 MB |
| Redis | ~50 MB |
| Nginx | ~20 MB |
| OS + system | ~300 MB |
| **Total** | **~970 MB** |
| **Free** | **~3 GB** |

### When to Upgrade

- 100+ active merchants sending concurrent queries
- Database grows beyond 10GB
- Need more workers for faster AI responses
- Upgrade to KVM 2 (2 vCPU, 8GB RAM) in Hostinger hPanel — no data loss

---

## 6. SSL/TLS Configuration

### Setup: Cloudflare Origin Certificate

We use **Cloudflare Origin Certificate** for SSL between Cloudflare and the VPS. This is different from Let's Encrypt — it's only valid for Cloudflare-proxied traffic (which is all our traffic).

**Why not Let's Encrypt?**
- Let's Encrypt requires HTTP-01 challenge, which Cloudflare intercepts
- Origin Certificate is simpler and lasts 15 years
- Only works with Cloudflare proxy enabled (which we always want)

### How We Set It Up

1. **Cloudflare** → SSL/TLS → Origin Server → Create Certificate
2. Selected RSA 2048, 15 years, covers `heysarva.com` and `*.heysarva.com`
3. Saved certificate and private key
4. On VPS:
   ```bash
   mkdir -p /etc/ssl/heysarva
   # Pasted cert into /etc/ssl/heysarva/cert.pem
   # Pasted key into /etc/ssl/heysarva/key.pem
   ```
5. Configured Nginx to use them (see Nginx section)

### SSL Modes Explained

| Mode | Visitor → Cloudflare | Cloudflare → VPS | Security |
|------|---------------------|-------------------|----------|
| **Off** | HTTP | HTTP | None |
| **Flexible** | HTTPS | HTTP | Partial |
| **Full** | HTTPS | HTTPS (any cert) | Good |
| **Full (Strict)** | HTTPS | HTTPS (valid cert) | Best |

**We use Full (Strict)** — end-to-end encryption with certificate validation.

### Certificate Files

| File | Location on VPS | Purpose |
|------|----------------|---------|
| `cert.pem` | `/etc/ssl/heysarva/cert.pem` | Origin Certificate (public) |
| `key.pem` | `/etc/ssl/heysarva/key.pem` | Private Key (never share) |

---

## 7. Nginx Configuration

### File Location

`/etc/nginx/sites-available/heysarva` (symlinked to `/etc/nginx/sites-enabled/`)

### Current Configuration

```nginx
server {
    listen 80;
    server_name heysarva.com www.heysarva.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name heysarva.com www.heysarva.com;

    ssl_certificate     /etc/ssl/heysarva/cert.pem;
    ssl_certificate_key /etc/ssl/heysarva/key.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;

    root /var/www/heysarva;
    index index.html;

    # Landing page
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Backend API proxy
    location ~ ^/(api|webhook|health|widget|embed\.js|\.well-known) {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_buffering    off;
        proxy_cache        off;
        proxy_read_timeout 120s;
    }
}
```

### What It Does

| URL | Serves |
|-----|--------|
| `heysarva.com` | Landing page from `/var/www/heysarva/index.html` |
| `heysarva.com/api/*` | Proxied to FastAPI on port 8000 |
| `heysarva.com/webhook/*` | Proxied to FastAPI |
| `heysarva.com/health` | Proxied to FastAPI health check |
| `heysarva.com/widget` | Proxied to FastAPI |
| HTTP (port 80) | Redirected to HTTPS (port 443) |

### Landing Page Location

`/var/www/heysarva/index.html` — static HTML file served directly by Nginx (fast, no backend involved).

---

## 8. Backend Deployment (Docker)

### Docker Compose

File: `/app/docker-compose.yml` on VPS

```yaml
services:
  app:
    build: .
    restart: always
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    volumes:
      - appdata:/app/data

  db:
    image: postgres:16-alpine
    restart: always
    environment:
      POSTGRES_DB: sarva
      POSTGRES_USER: sarva
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U sarva -d sarva"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    restart: always
    volumes:
      - redisdata:/data

volumes:
  pgdata:
  redisdata:
  appdata:
```

### Dockerfile

```dockerfile
FROM python:3.11-slim
RUN addgroup --system app && adduser --system --ingroup app app
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=app:app . .
RUN rm -f .env
RUN mkdir -p data && chown app:app data
USER app
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

### Container Details

| Container | Image | Port | Purpose |
|-----------|-------|------|---------|
| `app-app-1` | Built from Dockerfile | 8000 | FastAPI backend |
| `app-db-1` | postgres:16-alpine | 5432 (internal) | PostgreSQL database |
| `app-redis-1` | redis:7-alpine | 6379 (internal) | Rate limiting + CSRF |

### Data Persistence

Docker volumes survive container restarts and rebuilds:

| Volume | Purpose | Location |
|--------|---------|----------|
| `pgdata` | PostgreSQL data | `/var/lib/docker/volumes/app_pgdata/` |
| `redisdata` | Redis data | `/var/lib/docker/volumes/app_redisdata/` |
| `appdata` | App data (SQLite fallback) | `/var/lib/docker/volumes/app_appdata/` |

**Data is only lost if you explicitly run `docker volume rm`.**

---

## 9. Landing Page

### Location

- **Source**: `/static/index.html` in the repo
- **Deployed**: `/var/www/heysarva/index.html` on VPS

### Sections

| Section | Content |
|---------|---------|
| **Nav** | HeySarva logo, Features/How it works/Pricing links, CTA |
| **Hero** | Tagline, subtitle, "Try HeySarva Free" → WordPress.org |
| **Stats Bar** | 50 free queries, 30s install, 0 API keys |
| **Live Preview** | WP Admin mockup with chat conversation |
| **Features** | 6 cards (Revenue, Orders, Stock, AI, Widget, Privacy) |
| **Comparison** | Without HeySarva (30-60 min) vs With HeySarva (30s) |
| **How it works** | 3 steps (Install, Sign in, Ask) |
| **Use cases** | Scrolling animated tags with example questions |
| **Pricing** | Free tier card with feature list |
| **Final CTA** | "Stop digging through dashboards. Just ask." |

### Design

- **Theme**: Dark (#0a0a0a background)
- **Accent**: Orange (#f7931a)
- **Font**: system-ui
- **Tech**: Pure HTML/CSS/JS (no build step, no frameworks)
- **Responsive**: Mobile-friendly with media queries

### Updating the Landing Page

1. Edit `static/index.html` locally
2. Upload: `scp static/index.html root@2.24.209.83:/var/www/heysarva/index.html`
3. Purge Cloudflare cache: Dashboard → Caching → Purge Everything
4. Hard refresh browser: `Cmd+Shift+R`

---

## 10. WordPress Plugin

### Plugin Details

| Property | Value |
|----------|-------|
| **Name** | Woo AI Manager |
| **Slug** | woo-ai-manager |
| **Version** | 0.1.0 |
| **Text Domain** | woo-ai-manager |
| **Requires WP** | 6.0+ |
| **Requires PHP** | 7.4+ |
| **Requires WC** | 7.0+ |
| **License** | GPL-2.0-or-later |

### File Structure

```
woo-ai-manager/
├── woo-ai-manager.php          # Plugin entry, hooks, AJAX handlers
├── includes/
│   ├── ai-client.php           # Backend API client + AES encryption
│   └── wc-data.php             # Live store data extraction
├── admin/
│   ├── settings-page.php       # Google OAuth sign-in UI
│   ├── chat-panel.php          # Chat interface
│   ├── dashboard-widget.php    # WP Dashboard widget
│   ├── wam-admin.css           # Admin styles
│   └── wam-chat.js             # Chat JavaScript (AJAX, streaming)
├── readme.txt                  # WordPress plugin readme
└── LICENSE                     # GPL-2.0
```

### Key Configuration

| Setting | Value | File |
|---------|-------|------|
| Backend URL | `https://heysarva.com` | `includes/ai-client.php` |
| Plugin URI | `https://heysarva.com` | `woo-ai-manager.php` |
| Author URI | `https://heysarva.com` | `woo-ai-manager.php` |
| Upgrade URL | `https://heysarva.com/#pricing` | `woo-ai-manager.php` |
| Support Email | `hello@heysarva.com` | `admin/settings-page.php` |

### How the Plugin Gets Config

1. Plugin calls `GET https://heysarva.com/api/plugin/config`
2. Backend returns `{ "google_client_id": "925326..." }`
3. Plugin caches this in a WordPress transient (1 hour TTL)
4. Google Sign-In button uses this client ID

### Installing the Plugin

```bash
# Build zip from repo
cd /path/to/AgentHackathon
zip -r woo-ai-manager.zip woo-ai-manager/

# In WP Admin: Plugins → Add New → Upload Plugin → upload zip → Activate
```

---

## 11. Google OAuth Setup

### Google Cloud Console Configuration

| Setting | Value |
|---------|-------|
| **Client ID** | `925326144634-nipnhqbi6ss76av8ttlqr9fnku62t1rt.apps.googleusercontent.com` |
| **Type** | Web application |
| **Console URL** | console.cloud.google.com → APIs & Services → Credentials |

### Authorized JavaScript Origins

```
http://localhost:3000
http://localhost:8000
http://localhost:8080
https://heysarva.com
```

### Authorized Redirect URIs

```
https://heysarva.com/api/plugin/signin
https://heysarva.com/api/signin
```

### How Google Sign-In Works in HeySarva

```
1. User clicks "Sign in with Google" in WP Admin
2. Google popup → user approves → returns JWT credential
3. Plugin AJAX sends JWT to WordPress (admin-ajax.php)
4. WordPress PHP sends JWT to backend: POST /api/plugin/signin
5. Backend verifies JWT with Google (using google-auth library + requests)
6. Backend creates/updates merchant in PostgreSQL
7. Backend returns: { email, name, session_token, credits_remaining }
8. Plugin stores session_token encrypted in wp_options
9. User is signed in, chat panel becomes active
```

### Common Issues

- **"Origin not allowed"**: Add the exact origin (including port) to Authorized JavaScript Origins
- **"Invalid Google token"**: The `requests` library must be installed alongside `google-auth` (we fixed this — added to requirements.txt)
- **Changes take 5 min**: Google propagates OAuth config changes slowly

---

## 12. Database

### Connection

| Property | Value |
|----------|-------|
| **Engine** | PostgreSQL 16 |
| **Host** | `db` (Docker internal) |
| **Port** | 5432 |
| **Database** | sarva |
| **User** | sarva |
| **Connection URL** | `postgresql://sarva:<password>@db:5432/sarva` |

### Tables

| Table | Primary Key | Purpose |
|-------|-------------|---------|
| `merchants` | email | Merchant profiles + credits |
| `merchant_wc_credentials` | id | Encrypted WC API keys per store |
| `chat_stats` | id | Chat query analytics |
| `payment_events` | id | Bitcoin payment history |
| `orders` | id | Order tracking |

### Key Operations

```sql
-- Check merchant credits
SELECT email, plugin_credits FROM merchants WHERE email = 'user@example.com';

-- See all merchants
SELECT email, name, plugin_credits, created_at FROM merchants ORDER BY created_at DESC;

-- Reset credits for a merchant
UPDATE merchants SET plugin_credits = 50 WHERE email = 'user@example.com';
```

### Accessing the Database

```bash
# From VPS
cd /app
docker compose exec db psql -U sarva -d sarva

# Run a query
docker compose exec db psql -U sarva -d sarva -c "SELECT * FROM merchants;"
```

---

## 13. Security

### Firewall (UFW)

```
Status: active
To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       Anywhere
80/tcp                     ALLOW       Anywhere
443/tcp                    ALLOW       Anywhere
```

All other ports are blocked. PostgreSQL (5432) and Redis (6379) are only accessible within Docker's internal network.

### SSL/TLS

- **Cloudflare → VPS**: Full (Strict) with Origin Certificate
- **Visitor → Cloudflare**: TLS 1.3
- **Certificate validity**: 15 years (Cloudflare Origin CA)

### Application Security

| Feature | Implementation |
|---------|---------------|
| **Session tokens** | Cryptographically signed, TTL 24h |
| **CSRF tokens** | Per-email, Redis-stored |
| **Rate limiting** | Redis-backed, per-IP |
| **Token encryption** | AES-256-CBC in WordPress (uses WP salts) |
| **CORS** | Restricted to `heysarva.com` origins |
| **Content Security Policy** | Headers set in FastAPI |
| **HSTS** | Enabled via Cloudflare |
| **Non-root Docker** | App runs as `app` user inside container |
| **No secrets in image** | `.env` removed during Docker build |

### .env File Protection

```bash
chmod 600 /app/.env     # Only root can read
chown root:root /app/.env
```

### Cloudflare Security

- **Bot Fight Mode**: Enabled (blocks scrapers/bots)
- **DDoS Protection**: Automatic (free tier)
- **Proxied DNS**: VPS IP hidden from public
- **AI Training Bots**: Blocked on all pages

---

## 14. Backups

### Automated Daily Backup

**File**: `/etc/cron.daily/backup-heysarva`

```bash
#!/bin/bash
docker exec app-db-1 pg_dump -U sarva sarva | gzip > /root/backups/sarva-$(date +%Y%m%d).sql.gz
find /root/backups -name "*.sql.gz" -mtime +7 -delete
```

- **Runs**: Daily (via cron.daily)
- **Retention**: 7 days
- **Location**: `/root/backups/`
- **Size**: Very small (currently ~370 bytes)

### Manual Backup

```bash
cd /app
docker compose exec db pg_dump -U sarva sarva > /root/backups/manual-backup.sql
```

### Restore from Backup

```bash
# Stop the app first
cd /app && docker compose stop app

# Restore
gunzip -c /root/backups/sarva-20260417.sql.gz | docker compose exec -T db psql -U sarva -d sarva

# Restart
docker compose start app
```

---

## 15. Environment Variables

### Production (.env on VPS at /app/.env)

| Variable | Purpose | Example |
|----------|---------|---------|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI API endpoint | `https://sarvascope-oa.cognitiveservices.azure.com/` |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key | `C1cRm...` |
| `AZURE_OPENAI_DEPLOYMENT` | Model deployment name | `gpt-5-chat` |
| `AZURE_OPENAI_API_VERSION` | API version | `2025-01-01-preview` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://sarva:<pw>@db:5432/sarva` |
| `POSTGRES_PASSWORD` | PostgreSQL password (used by docker-compose) | `JaYVFd...` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379/0` |
| `MERCHANT_URL` | Public domain URL | `https://heysarva.com` |
| `ALLOWED_ORIGINS` | CORS allowed origins | `https://heysarva.com,https://www.heysarva.com` |
| `ENVIRONMENT` | Environment flag | `production` |
| `CSRF_SECRET` | CSRF token signing secret (32-byte hex) | `39224f...` |
| `TRUSTED_PROXIES` | IPs allowed to set X-Forwarded-For | `127.0.0.1,::1` |
| `SESSION_TTL` | Session token lifetime (seconds) | `86400` |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID | `925326...apps.googleusercontent.com` |
| `SUPPORT_EMAIL` | Support email shown in plugin | `hello@heysarva.com` |
| `MERCHANT_NAME` | Brand name | `HeySarva` |

### Generating Secrets

```bash
# CSRF Secret
python3 -c "import secrets; print(secrets.token_hex(32))"

# Strong password
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```

---

## 16. Useful Commands

### SSH into VPS

```bash
ssh root@2.24.209.83
```

### Docker Commands (run from /app on VPS)

```bash
# Check container status
cd /app && docker compose ps

# View logs (last 50 lines)
docker compose logs app --tail 50

# View logs in real-time
docker compose logs -f app

# Restart all containers
docker compose restart

# Rebuild and restart (after code changes)
docker compose up -d --build

# Stop everything
docker compose down

# Stop everything AND delete data (DANGEROUS)
docker compose down -v
```

### Nginx Commands

```bash
# Test config
nginx -t

# Restart
systemctl restart nginx

# View error logs
tail -50 /var/log/nginx/error.log

# View access logs
tail -50 /var/log/nginx/access.log
```

### Database Commands

```bash
# Connect to PostgreSQL
cd /app && docker compose exec db psql -U sarva -d sarva

# Run a query directly
docker compose exec db psql -U sarva -d sarva -c "SELECT email, plugin_credits FROM merchants;"

# Manual backup
docker compose exec db pg_dump -U sarva sarva > /root/backups/manual.sql
```

### Firewall Commands

```bash
# Check status
ufw status

# Allow a port
ufw allow 8080/tcp

# Block a port
ufw deny 8080/tcp
```

### Upload Files to VPS

```bash
# Single file
scp localfile.txt root@2.24.209.83:/path/on/vps/

# Entire directory
rsync -avz --exclude='.git' --exclude='__pycache__' . root@2.24.209.83:/app/

# Landing page update
scp static/index.html root@2.24.209.83:/var/www/heysarva/index.html
```

### DNS Check

```bash
# Check what IP the domain resolves to
dig heysarva.com A +short

# Check nameservers
dig heysarva.com NS +short

# Check from Cloudflare's nameserver
dig @josephine.ns.cloudflare.com heysarva.com A +short

# Check HTTP headers
curl -sI https://heysarva.com | head -20
```

---

## 17. Deployment Workflow

### Deploying Code Changes

```bash
# 1. Make changes locally
# 2. Test locally
# 3. Upload to VPS
rsync -avz --exclude='.git' --exclude='node_modules' --exclude='.env' --exclude='data/' --exclude='__pycache__' --exclude='.claude' . root@2.24.209.83:/app/

# 4. Rebuild on VPS
ssh root@2.24.209.83 "cd /app && docker compose up -d --build"
```

### Deploying Landing Page Changes

```bash
# 1. Edit static/index.html locally
# 2. Upload
scp static/index.html root@2.24.209.83:/var/www/heysarva/index.html
# 3. Purge Cloudflare cache (Dashboard → Caching → Purge Everything)
# 4. Hard refresh browser (Cmd+Shift+R)
```

### Deploying Nginx Changes

```bash
# 1. Edit nginx.conf locally
# 2. Upload
scp nginx.conf root@2.24.209.83:/etc/nginx/sites-available/heysarva
# 3. Test and restart
ssh root@2.24.209.83 "nginx -t && systemctl restart nginx"
```

---

## 18. Troubleshooting

### Problem: Site shows Namecheap parking page

**Cause**: DNS hasn't propagated to Cloudflare nameservers yet.  
**Check**: `dig heysarva.com NS +short` — should show Cloudflare nameservers, not Namecheap.  
**Fix**: Wait 1-24 hours for nameserver propagation. Verify nameservers are set correctly in Namecheap → Domain List → Manage → Custom DNS.

### Problem: Error 522 (Connection timed out)

**Cause**: Cloudflare can't reach your VPS.  
**Check**:
1. Is Nginx running? `systemctl status nginx`
2. Is the firewall blocking? `ufw status` (ports 80/443 must be open)
3. Is Nginx listening on the right port? With "Full (Strict)" SSL, Nginx must listen on 443.  
**Fix**: Ensure Nginx has SSL configured and listens on port 443.

### Problem: "Invalid Google token" on sign-in

**Cause**: Backend can't verify the Google JWT.  
**Check**: `cd /app && docker compose logs app --tail 20`  
**Common causes**:
- Missing `requests` library: Add `requests>=2.31.0` to requirements.txt, rebuild
- Wrong `GOOGLE_CLIENT_ID` in .env
- Google OAuth origins not configured correctly  
**Fix**: Ensure `requests` is in requirements.txt and rebuild Docker image.

### Problem: "Origin not allowed for client ID"

**Cause**: Google OAuth doesn't recognize the browser's origin.  
**Check**: Google Cloud Console → Credentials → Authorized JavaScript Origins  
**Fix**: Add the exact origin (e.g., `http://localhost:8080`, `https://heysarva.com`) — no trailing slashes.

### Problem: 401 on admin-ajax.php

**Cause**: WordPress nonce expired or session invalid.  
**Fix**: Hard refresh the page (Cmd+Shift+R) to get a fresh nonce. If persistent, deactivate and reactivate the plugin.

### Problem: Docker containers won't start

**Check**: `cd /app && docker compose logs`  
**Common causes**:
- Bad `.env` file (missing variables, wrong format)
- Port 8000 already in use: `lsof -i :8000`
- PostgreSQL health check failing (wrong password)  
**Fix**: Check logs, fix `.env`, restart: `docker compose down && docker compose up -d`

### Problem: Landing page not updating after changes

**Cause**: Cloudflare caching.  
**Fix**:
1. Cloudflare Dashboard → Caching → Configuration → Purge Everything
2. Hard refresh browser: Cmd+Shift+R
3. Or test in incognito window

### Problem: Can't SSH into VPS

**Check**: Is the VPS running in Hostinger hPanel?  
**Fix**: Try rebooting from hPanel. Check if your IP is blocked by the firewall.

### Problem: Database connection error

**Check**: `docker compose ps` — is the `db` container healthy?  
**Fix**: Check `POSTGRES_PASSWORD` matches in both `.env` variables (`POSTGRES_PASSWORD` and inside `DATABASE_URL`).

### Problem: Redis connection error

**Impact**: Low — app falls back to in-memory storage.  
**Check**: `docker compose ps` — is the `redis` container running?  
**Fix**: `docker compose restart redis`

---

## 19. FAQs

### General

**Q: What happens if my VPS goes down?**  
A: Your site goes offline until the VPS restarts. Docker containers have `restart: always` so they auto-start. Data is safe in Docker volumes. Hostinger provides basic uptime monitoring.

**Q: What happens if I run out of disk space?**  
A: Docker images and logs can accumulate. Clean up: `docker system prune -a` (removes unused images). Check disk: `df -h`.

**Q: Can I move to a different server later?**  
A: Yes. Backup the database, copy the code and `.env`, set up Docker on the new server, restore the database, update the Cloudflare A record to the new IP. Downtime: ~15 minutes.

**Q: How many merchants can KVM 1 handle?**  
A: Comfortably 100-500 merchants with normal usage. AI queries are the bottleneck (Azure OpenAI, not your server). The VPS mostly just proxies requests.

### Domain & DNS

**Q: Can I use a subdomain like app.heysarva.com?**  
A: Yes. Add a CNAME record in Cloudflare: `app` → `heysarva.com`. Update Nginx `server_name` to include it.

**Q: Do I need to renew the SSL certificate?**  
A: Cloudflare Origin Certificate lasts 15 years. No renewal needed.

**Q: What if Cloudflare goes down?**  
A: Extremely rare (99.99% uptime). If it happens, your site is temporarily unreachable but your VPS and data are fine.

### Plugin

**Q: How do I update the plugin on live stores?**  
A: Rebuild the zip, upload via WP Admin, or (when on WordPress.org) push an update through SVN.

**Q: Can the plugin work without the backend?**  
A: The settings page loads, but sign-in and chat won't work. The plugin is fully dependent on the backend for AI features.

**Q: How are WooCommerce API keys stored?**  
A: Encrypted with AES-256-CBC using WordPress's AUTH_KEY salt, stored in wp_options. The backend also stores them encrypted in PostgreSQL.

### Security

**Q: Can someone access my database from the internet?**  
A: No. PostgreSQL only listens inside Docker's internal network. Port 5432 is not exposed to the host, and UFW blocks all ports except 22/80/443.

**Q: What if my .env file is compromised?**  
A: Rotate all secrets immediately: generate new CSRF_SECRET, change POSTGRES_PASSWORD (update both places in .env), rotate Azure OpenAI key in Azure portal, create new Google OAuth credentials.

**Q: Is customer data safe?**  
A: Yes. The plugin sends order totals, product names, and stock levels to the backend. Customer emails and payment details are never sent. The backend doesn't store query data beyond the request (except anonymized chat_stats).

### Costs

**Q: What are the ongoing costs?**  
A: VPS (£4.99/mo) + Domain (~$10/yr) + Azure OpenAI (usage-based, ~$10-50/mo depending on queries). Everything else is free.

**Q: What's the most expensive part?**  
A: Azure OpenAI API calls. Each chat query costs ~$0.01-0.05 depending on context size and response length. At 50 free queries per merchant, your cost is $0.50-2.50 per merchant for the free tier.

---

## 20. Cost Breakdown

### Monthly Costs

| Item | Cost | Notes |
|------|------|-------|
| Hostinger VPS (KVM 1) | £4.99/mo | 1 vCPU, 4GB RAM, 50GB |
| Domain (heysarva.com) | ~$0.83/mo | $10/yr amortized |
| Cloudflare | $0 | Free plan |
| SSL Certificate | $0 | Cloudflare Origin CA |
| PostgreSQL | $0 | Self-hosted on VPS |
| Redis | $0 | Self-hosted on VPS |
| Google OAuth | $0 | Free |
| Azure OpenAI | ~$10-50/mo | Usage-based |
| **Total** | **~$16-56/mo** | |

### When to Expect Cost Increases

| Milestone | Action | Added Cost |
|-----------|--------|-----------|
| 100+ merchants | Upgrade to KVM 2 | +£2/mo |
| Email (hello@heysarva.com) | Proton Mail or similar | ~$4/mo |
| External backups | Storj or B2 storage | ~$1/mo |
| High AI usage | Azure OpenAI scales | Variable |
| 1000+ merchants | Managed DB (Neon/Supabase) | ~$25/mo |

---

## Appendix: Access Credentials

> **IMPORTANT**: Never commit actual credentials. This section lists WHERE to find them.

| Credential | Location |
|------------|----------|
| VPS SSH | Hostinger hPanel → VPS → Overview |
| VPS Root Password | Hostinger hPanel (or password manager) |
| PostgreSQL Password | `/app/.env` on VPS (`POSTGRES_PASSWORD`) |
| Azure OpenAI Key | `/app/.env` on VPS (`AZURE_OPENAI_API_KEY`) |
| Google OAuth Client ID | Google Cloud Console → APIs & Services → Credentials |
| CSRF Secret | `/app/.env` on VPS (`CSRF_SECRET`) |
| Cloudflare Account | cloudflare.com (your account) |
| Namecheap Account | namecheap.com (your account) |
| Origin Certificate Key | `/etc/ssl/heysarva/key.pem` on VPS |

---

*Last updated: April 17, 2026*
