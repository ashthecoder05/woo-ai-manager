from __future__ import annotations
"""
UCP (Universal Commerce Protocol) manifest generator and Schema.org validator.

Generates a /.well-known/ucp JSON-LD document that lets AI agents discover
a merchant's Bitcoin payment capabilities, API endpoints, and policies.

Spec reference: https://ucp.dev / Schema.org vocabulary
"""

import re
from typing import Any
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Manifest Generator
# ---------------------------------------------------------------------------

def generate_manifest(
    *,
    merchant_name: str,
    merchant_url: str,
    description: str = "",
    webhook_url: str = "",
    new_address_endpoint: str = "",
    support_email: str = "",
    currency: str = "BTC",
    confirmations_required: int = 2,
    extra_payment_methods: list[str] | None = None,
) -> dict[str, Any]:
    """
    Generate a UCP-compliant JSON-LD manifest for a Bitcoin merchant.

    Returns a dict ready to be served as application/ld+json at /.well-known/ucp
    """
    base_url = merchant_url.rstrip("/")

    payment_methods = [
        {
            "@type": "PaymentMethod",
            "identifier": "bitcoin",
            "name": "Bitcoin (BTC)",
            "description": "Direct on-chain Bitcoin payment via Blockonomics",
            "provider": "Blockonomics",
            "currency": currency,
            "confirmationsRequired": confirmations_required,
            "addressEndpoint": new_address_endpoint or f"{base_url}/api/btc/new-address",
            "webhookEndpoint": webhook_url or f"{base_url}/webhook/blockonomics",
        }
    ]

    for method in (extra_payment_methods or []):
        payment_methods.append({"@type": "PaymentMethod", "name": method})

    manifest: dict[str, Any] = {
        "@context": [
            "https://schema.org",
            {"ucp": "https://ucp.dev/vocab#"},
        ],
        "@type": ["Organization", "ucp:Merchant"],
        "name": merchant_name,
        "url": merchant_url,
        "ucp:apiVersion": "1.0",
        "ucp:capabilities": [
            "bitcoin-payment",
            "webhook-notification",
            "address-generation",
        ],
        "ucp:paymentMethods": payment_methods,
        "ucp:agentInstructions": (
            f"To pay with Bitcoin: POST to {new_address_endpoint or base_url + '/api/btc/new-address'} "
            f"to get a fresh payment address. Send the exact BTC amount to that address. "
            f"Payment is confirmed after {confirmations_required} block confirmation(s)."
        ),
    }

    if description:
        manifest["description"] = description

    if support_email:
        manifest["contactPoint"] = {
            "@type": "ContactPoint",
            "email": support_email,
            "contactType": "customer support",
        }

    return manifest


# ---------------------------------------------------------------------------
# Schema.org / UCP Validator
# ---------------------------------------------------------------------------

class ValidationError:
    def __init__(self, field: str, message: str, severity: str = "error"):
        self.field = field
        self.message = message
        self.severity = severity  # "error" | "warning"

    def __repr__(self) -> str:
        return f"[{self.severity.upper()}] {self.field}: {self.message}"


def validate_manifest(manifest: dict[str, Any]) -> list[ValidationError]:
    """
    Validate a UCP manifest for Schema.org correctness and UCP completeness.
    Returns a list of ValidationError objects (empty = valid).
    """
    errors: list[ValidationError] = []

    # --- @context ---
    ctx = manifest.get("@context")
    if not ctx:
        errors.append(ValidationError("@context", "Missing @context — must include 'https://schema.org'"))
    elif isinstance(ctx, str) and "schema.org" not in ctx:
        errors.append(ValidationError("@context", "Context should reference 'https://schema.org'"))
    elif isinstance(ctx, list) and not any("schema.org" in str(c) for c in ctx):
        errors.append(ValidationError("@context", "Context list must include 'https://schema.org'"))

    # --- @type ---
    typ = manifest.get("@type")
    if not typ:
        errors.append(ValidationError("@type", "Missing @type — expected 'Organization' or ['Organization', 'ucp:Merchant']"))
    else:
        types = typ if isinstance(typ, list) else [typ]
        if "Organization" not in types:
            errors.append(ValidationError("@type", "Expected @type to include 'Organization' (Schema.org)", "warning"))

    # --- name ---
    name = manifest.get("name", "")
    if not name:
        errors.append(ValidationError("name", "Merchant name is required"))
    elif len(name) > 200:
        errors.append(ValidationError("name", "name is too long (max 200 chars)", "warning"))

    # --- url ---
    url = manifest.get("url", "")
    if not url:
        errors.append(ValidationError("url", "Merchant URL is required"))
    else:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            errors.append(ValidationError("url", "URL must use http or https scheme"))
        if not parsed.netloc:
            errors.append(ValidationError("url", "URL must include a valid domain"))

    # --- ucp:paymentMethods ---
    methods = manifest.get("ucp:paymentMethods", [])
    if not methods:
        errors.append(ValidationError("ucp:paymentMethods", "At least one payment method is required"))
    else:
        for i, method in enumerate(methods):
            prefix = f"ucp:paymentMethods[{i}]"
            if method.get("@type") != "PaymentMethod":
                errors.append(ValidationError(prefix, "@type must be 'PaymentMethod'", "warning"))

            addr_ep = method.get("addressEndpoint", "")
            if addr_ep:
                p = urlparse(addr_ep)
                if p.scheme not in ("http", "https"):
                    errors.append(ValidationError(f"{prefix}.addressEndpoint", "addressEndpoint must be a valid https URL"))

            webhook_ep = method.get("webhookEndpoint", "")
            if webhook_ep:
                p = urlparse(webhook_ep)
                if p.scheme not in ("http", "https"):
                    errors.append(ValidationError(f"{prefix}.webhookEndpoint", "webhookEndpoint must be a valid https URL"))

            confs = method.get("confirmationsRequired")
            if confs is not None and (not isinstance(confs, int) or confs < 0):
                errors.append(ValidationError(f"{prefix}.confirmationsRequired", "Must be a non-negative integer"))

    # --- ucp:agentInstructions ---
    if not manifest.get("ucp:agentInstructions"):
        errors.append(ValidationError("ucp:agentInstructions", "Missing agent instructions — helps AI agents know how to pay", "warning"))

    # --- contactPoint (optional but recommended) ---
    contact = manifest.get("contactPoint", {})
    if contact:
        email = contact.get("email", "")
        if email and not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            errors.append(ValidationError("contactPoint.email", f"'{email}' does not look like a valid email"))

    return errors


def validate_summary(manifest: dict[str, Any]) -> str:
    """Return a human-readable validation summary string."""
    errors = validate_manifest(manifest)
    if not errors:
        return "Manifest is valid. No errors found."

    hard = [e for e in errors if e.severity == "error"]
    warnings = [e for e in errors if e.severity == "warning"]
    lines = []
    if hard:
        lines.append(f"{len(hard)} error(s):")
        lines.extend(f"  {e}" for e in hard)
    if warnings:
        lines.append(f"{len(warnings)} warning(s):")
        lines.extend(f"  {e}" for e in warnings)
    return "\n".join(lines)
