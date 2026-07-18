# Contributing to HeySarva

Thanks for your interest in contributing! This project has two main parts — a **Python/FastAPI backend** and a **WordPress plugin** — and contributions to either (plus docs, the landing page, and tests) are all welcome.

By participating, you agree to abide by our [Code of Conduct](./CODE_OF_CONDUCT.md).

## Ways to contribute

- Report bugs and request features (use the issue templates)
- Improve documentation
- Fix bugs or build features (look for the `good first issue` label)
- Improve tests and CI

## Development setup

### Backend (Python)

```bash
git clone https://github.com/ashthecoder05/woo-ai-manager.git
cd woo-ai-manager
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # fill in your own keys
uvicorn main:app --reload --port 8000
```

Run tests:

```bash
pytest
```

### WordPress plugin (PHP)

The plugin lives in [`woo-ai-manager/`](./woo-ai-manager). Copy it into a local WordPress install's `wp-content/plugins/` directory (WooCommerce must be active) and activate it. Point its settings at your local backend (`http://localhost:8000`).

## Branch & PR workflow

1. **Fork** the repo and create a branch from `main`:
   ```bash
   git checkout -b feat/short-description
   ```
   Use prefixes like `feat/`, `fix/`, `docs/`, `test/`, `chore/`.
2. **Make your changes** with clear, focused commits.
3. **Test** — run `pytest` for backend changes; manually verify plugin changes in WP Admin.
4. **Open a Pull Request** against `main`. Fill in the PR template: what changed, why, and how you tested it.
5. Link any related issue (e.g. `Closes #123`).

Keep PRs small and focused — it makes review much faster.

## Coding conventions

- **Python:** Follow PEP 8. Prefer clear names and small functions. Add/adjust tests for behavior changes.
- **PHP:** Follow [WordPress coding standards](https://developer.wordpress.org/coding-standards/wordpress-coding-standards/). Escape output and sanitize input.
- **Commits:** Write clear messages in the imperative mood (e.g. "Add low-stock alert endpoint").
- **No secrets:** Never commit `.env`, API keys, or credentials. Use `.env.example` for new config keys.
- **Comments:** Explain *why*, not *what*. Avoid narrating obvious code.

## Reporting security issues

Do **not** open a public issue for security vulnerabilities. See [SECURITY.md](./SECURITY.md).

## License

By contributing, you agree that your contributions will be licensed under the project's [GPL-2.0-or-later license](./LICENSE).
