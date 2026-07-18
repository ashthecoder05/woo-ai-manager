# HeySarva — Your AI Store Manager, Inside WooCommerce

HeySarva is an open-source AI store manager that lives inside your WordPress/WooCommerce admin. It reads your live store data — orders, revenue, products, stock — and answers questions in plain English, so you know what's happening and what to do next.

> "Summarise this week's sales" · "Which orders are stuck?" · "What's running low on stock?"

[![License: GPL v2](https://img.shields.io/badge/License-GPLv2-blue.svg)](./LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](./CONTRIBUTING.md)

---

## Table of contents

- [What it does](#what-it-does)
- [Architecture](#architecture)
- [Repository layout](#repository-layout)
- [Quick start](#quick-start)
  - [Backend (FastAPI)](#backend-fastapi)
  - [WordPress plugin](#wordpress-plugin)
- [Configuration](#configuration)
- [Contributing](#contributing)
- [Security](#security)
- [License](#license)

---

## What it does

- **Lives in WP Admin** — a chat panel and dashboard widget inside WooCommerce.
- **Knows your store** — pulls live revenue, recent orders, top products, and low-stock alerts.
- **Answers in plain English** — powered by an LLM behind a FastAPI backend.
- **Simple onboarding** — sign in with Google, get free queries to start.

## Architecture

HeySarva has two main parts:

| Part | Tech | Location |
|------|------|----------|
| **WordPress plugin** | PHP (WooCommerce) | [`woo-ai-manager/`](./woo-ai-manager) |
| **Backend API + agent** | Python (FastAPI + LLM) | [`main.py`](./main.py), [`agent/`](./agent), [`services/`](./services) |

The plugin collects store data in WP Admin and sends it to the backend, which calls the LLM and returns an answer. There's also a landing page ([`static/`](./static)) and an optional Telegram bot ([`telegram_bot/`](./telegram_bot)).

## Repository layout

```
.
├── main.py               # FastAPI app entrypoint
├── agent/                # LLM agent core + tools
├── services/             # DB, auth, business logic
├── mcp_server/           # MCP server integration
├── webhook/              # Webhook receivers
├── telegram_bot/         # Optional Telegram bot
├── knowledge/            # Docs/knowledge base used by the agent
├── static/               # Landing page + widget
├── woo-ai-manager/       # WordPress/WooCommerce plugin (PHP)
├── tests/                # Python tests
├── requirements.txt      # Python dependencies
├── docker-compose.yml    # App + Postgres + Redis
└── .env.example          # Environment variable template
```

## Quick start

### Prerequisites

- Python 3.10+
- (Optional) Docker + Docker Compose
- A WordPress site with WooCommerce (for the plugin)
- An LLM provider key (e.g. Azure OpenAI / OpenAI)

### Backend (FastAPI)

```bash
# 1. Clone
git clone https://github.com/ashthecoder05/woo-ai-manager.git
cd woo-ai-manager

# 2. Set up environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# edit .env and fill in your keys

# 4. Run
uvicorn main:app --reload --port 8000
```

The API is now at `http://localhost:8000` (health check: `GET /health`).

**Or with Docker (includes Postgres + Redis):**

```bash
cp .env.example .env   # fill in your values, incl. POSTGRES_PASSWORD
docker compose up --build
```

### WordPress plugin

1. Copy the `woo-ai-manager/` folder into `wp-content/plugins/` on your WordPress site.
2. Activate **Woo AI Manager** from the **Plugins** menu (WooCommerce must be active).
3. Go to **AI Manager → Settings**, point it at your backend URL, and sign in.
4. Open **AI Manager** in the sidebar and start asking questions.

See [`woo-ai-manager/readme.txt`](./woo-ai-manager/readme.txt) for plugin details.

## Configuration

All backend configuration is via environment variables. Copy [`.env.example`](./.env.example) to `.env` and fill in your values. **Never commit `.env`.**

Key variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `AZURE_OPENAI_API_KEY` | Yes | LLM provider key |
| `AZURE_OPENAI_ENDPOINT` | Yes | LLM endpoint URL |
| `ALLOWED_ORIGINS` | Prod | Comma-separated allowed origins |
| `CSRF_SECRET` | Prod | Random 32-byte hex string |
| `GOOGLE_CLIENT_ID` | Recommended | Google OAuth client ID |
| `TELEGRAM_BOT_TOKEN` | Optional | Enables the Telegram bot |

See `.env.example` for the full list with comments.

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](./CONTRIBUTING.md) for how to set up your environment, our branch/PR workflow, and coding conventions. By participating you agree to our [Code of Conduct](./CODE_OF_CONDUCT.md).

Good places to start:
- Improve the landing page in [`static/`](./static)
- Add features or fix bugs in the [WordPress plugin](./woo-ai-manager)
- Extend the Python agent in [`agent/`](./agent)
- Improve docs in [`knowledge/`](./knowledge) or this README

Look for issues labeled **`good first issue`**.

## Security

Found a vulnerability? Please **don't** open a public issue. See [SECURITY.md](./SECURITY.md) for how to report it privately.

## License

This project is licensed under the **GNU General Public License v2.0 or later** — see [LICENSE](./LICENSE). The WordPress plugin is GPL-2.0 to stay compatible with the WordPress.org plugin guidelines.
