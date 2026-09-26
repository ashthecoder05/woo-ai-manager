# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-07-27

### Added

- Initial release of the **Woo AI Manager** WordPress plugin — an AI store manager that lives inside WP Admin, powered by WooCommerce data.
- **FastAPI backend** (`main.py`, `agent/`, `services/`) providing LLM-powered chat, Google OAuth sign-in, credit management, and a WooCommerce store-context API.
- WordPress plugin with an admin chat panel and quick-action buttons for querying live store data in plain English.
- Google SSO sign-in flow with 50 free AI queries on first sign-in (no API key or credit card required).
- Live store context endpoint: revenue snapshots (today / 7-day / 30-day), recent orders, top-selling products, and low-stock alerts.
- WP Admin dashboard widget displaying today's revenue and low-stock summary.
- Support for WooCommerce High-Performance Order Storage (HPOS) and legacy post-based order tables.
- Docker Compose setup (`docker-compose.yml`) bundling the FastAPI app, PostgreSQL, and Redis.
- Deployment configuration for Railway (`railway.json`) and Render (`render.yaml`).
- Nginx reverse-proxy configuration (`nginx.conf`) for production deployments.
- MCP server integration (`mcp_server/`) for agent tool calling.
- Optional Telegram bot (`telegram_bot/`) for store Q&A via Telegram.
- Static landing page (`static/`) with plugin download button.
- Environment variable template (`.env.example`) with inline documentation.
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, and `SECURITY.md` for community health.

[Unreleased]: https://github.com/ashthecoder05/woo-ai-manager/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ashthecoder05/woo-ai-manager/releases/tag/v0.1.0
