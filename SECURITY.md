# Security Policy

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability, please **do not open a public issue**.

Instead, report it privately using GitHub's [private vulnerability reporting](https://github.com/ashthecoder05/AgentHackathon/security/advisories/new), or contact the maintainers directly.

Please include:

- A description of the vulnerability and its impact
- Steps to reproduce (proof of concept if possible)
- Any suggested remediation

We will acknowledge your report as soon as possible and keep you updated on the fix.

## Supported Versions

As an early-stage project, security fixes are applied to the latest `main` branch. Please make sure you're running the most recent version before reporting.

## Handling Secrets

- Never commit `.env` files, API keys, tokens, or credentials.
- Use `.env.example` as the template for required configuration.
- If you accidentally commit a secret, rotate it immediately and notify the maintainers.
