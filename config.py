from dotenv import load_dotenv
import os
import secrets

load_dotenv()

AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "https://sarvascope-oa.cognitiveservices.azure.com/")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5-chat")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
BLOCKONOMICS_API_KEY = os.getenv("BLOCKONOMICS_API_KEY", "")
BLOCKONOMICS_BASE_URL = "https://www.blockonomics.co/api"
CACHE_TTL_SECONDS = 60
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# ── Database ───────────────────────────────────────────────────────────────────
# Set DATABASE_URL to a PostgreSQL connection string in production.
# Example: postgresql://user:pass@host:5432/dbname
# Leave unset to use SQLite (local dev only).
DATABASE_URL = os.getenv("DATABASE_URL", "")
# Railway/Heroku use postgres:// — normalise to postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# ── Redis ──────────────────────────────────────────────────────────────────────
# Set REDIS_URL for production multi-worker rate limiting and CSRF token storage.
# Example: redis://default:password@host:6379/0
# Leave unset to use in-memory fallback (single-worker dev only).
REDIS_URL = os.getenv("REDIS_URL", "")

# ── Session tokens ─────────────────────────────────────────────────────────────
# MUST be set to a fixed secret in production — do not use the random default.
# Generate one with: python -c "import secrets; print(secrets.token_hex(32))"
_ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
_csrf_secret_env = os.getenv("CSRF_SECRET", "")
if not _csrf_secret_env and _ENVIRONMENT == "production":
    raise RuntimeError(
        "CSRF_SECRET environment variable must be set in production. "
        "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
CSRF_SECRET: str = _csrf_secret_env or secrets.token_hex(32)

# Session tokens expire after this many seconds (default 24 hours)
SESSION_TTL: int = int(os.getenv("SESSION_TTL", str(24 * 3600)))
