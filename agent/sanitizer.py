import re

# xpub / xprv / zpub / zprv style extended keys (51-111 base58 chars)
_XKEY = re.compile(r"\b[xyz](?:pub|prv)[1-9A-HJ-NP-Za-km-z]{50,107}\b")

# WIF private keys (51-52 chars starting with 5, K, or L)
_WIF = re.compile(r"\b[5KL][1-9A-HJ-NP-Za-km-z]{50,51}\b")

# Email addresses
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

# IPv4 addresses (non-loopback)
_IPV4 = re.compile(
    r"\b(?!127\.)(?!0\.)(?!255\.)"
    r"(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
)

_PATTERNS = [_XKEY, _WIF, _EMAIL, _IPV4]


def sanitize(text: str) -> str:
    for pattern in _PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text
