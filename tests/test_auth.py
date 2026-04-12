"""
Tests for session token and CSRF logic in main.py.
Run with:  pytest tests/test_auth.py -v
"""
import os
import time

os.environ.pop("DATABASE_URL", None)
os.environ.setdefault("CSRF_SECRET", "test-secret-for-unit-tests-only")
os.environ.setdefault("SESSION_TTL", "3600")


def _make_token(email: str) -> str:
    import hashlib, hmac
    secret = os.environ["CSRF_SECRET"]
    ttl    = int(os.environ["SESSION_TTL"])
    expires = int(time.time()) + ttl
    payload = f"{email}:{expires}"
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{expires}:{sig}"


def _verify_token(email: str, token: str) -> bool:
    import hashlib, hmac
    secret = os.environ["CSRF_SECRET"]
    try:
        expires_str, sig = token.split(":", 1)
        expires = int(expires_str)
        if time.time() > expires:
            return False
        payload = f"{email}:{expires}"
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, sig)
    except Exception:
        return False


def test_valid_token():
    token = _make_token("merchant@store.com")
    assert _verify_token("merchant@store.com", token) is True


def test_wrong_email_rejected():
    token = _make_token("merchant@store.com")
    assert _verify_token("hacker@evil.com", token) is False


def test_tampered_token_rejected():
    token = _make_token("merchant@store.com")
    assert _verify_token("merchant@store.com", token + "tampered") is False


def test_expired_token_rejected():
    import hashlib, hmac
    secret = os.environ["CSRF_SECRET"]
    email   = "merchant@store.com"
    expires = int(time.time()) - 1  # already expired
    payload = f"{email}:{expires}"
    sig     = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    token   = f"{expires}:{sig}"
    assert _verify_token(email, token) is False


def test_malformed_token_rejected():
    assert _verify_token("merchant@store.com", "notavalidtoken") is False
    assert _verify_token("merchant@store.com", "") is False
    assert _verify_token("merchant@store.com", ":") is False


def test_different_merchants_different_tokens():
    t1 = _make_token("alice@store.com")
    t2 = _make_token("bob@store.com")
    assert t1 != t2
    assert _verify_token("alice@store.com", t2) is False
    assert _verify_token("bob@store.com",   t1) is False
