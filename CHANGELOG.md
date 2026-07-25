# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- CI workflow (pytest + PHP lint) and README badges.

## [0.1.0] - 2026-07-25

First public release of HeySarva — an open-source AI store manager for WooCommerce.

### Added

- **WordPress plugin** (`woo-ai-manager/`): chat panel and dashboard widget inside WP Admin that answers questions about a store's orders, revenue, products, and stock.
- **FastAPI backend** (`main.py`, `agent/`, `services/`): LLM agent, Google sign-in, credit tracking, and WooCommerce data endpoints.
- Google SSO sign-in with 50 free AI queries to start.
- Live store context: revenue snapshot (today, 7 days, 30 days), recent orders summary, top selling products, and low-stock alerts.
- Dashboard widget showing today's revenue at a glance.
- Support for WooCommerce High-Performance Order Storage (HPOS), with automatic detection of legacy post-based order storage.
- Optional Telegram bot (`telegram_bot/`) and MCP server integration (`mcp_server/`).
- Landing page (`static/`) and Docker Compose setup (app + Postgres + Redis).

[Unreleased]: https://github.com/ashthecoder05/woo-ai-manager/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ashthecoder05/woo-ai-manager/releases/tag/v0.1.0
