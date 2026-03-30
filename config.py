"""
config.py
---------
Central configuration module. All settings are read from environment variables.

Local development: values are loaded from a .env file via python-dotenv.
Production (Railway): variables are set directly in the Railway dashboard.

Environment reference:
  ENVIRONMENT        "development" or "production" (default: "development")
  DATABASE_URL       PostgreSQL URL. If not set, falls back to SQLite locally.
  DEBUG              Enable verbose logging. (default: true in dev, false in prod)
  ALLOWED_ORIGINS    Comma-separated list of allowed CORS origins.
                     (default: * in dev, must be set explicitly in prod)
  APP_NAME           Display name for the API (default: "Expenses API")
  DOLLAR_CACHE_TTL   Seconds to cache the exchange rate (default: 300)
"""

import os
from pathlib import Path

# Load .env file if it exists (only relevant locally — Railway sets vars natively)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass  # python-dotenv not installed — that's fine in production


# ── Core ──────────────────────────────────────────────────────────────────────

ENVIRONMENT:  str = os.getenv("ENVIRONMENT", "development")
IS_PROD:      bool = ENVIRONMENT == "production"
IS_DEV:       bool = not IS_PROD

# ── Database ──────────────────────────────────────────────────────────────────

DATABASE_URL: str | None = os.getenv("DATABASE_URL")
USE_POSTGRES: bool = DATABASE_URL is not None

# ── API behavior ──────────────────────────────────────────────────────────────

APP_NAME: str = os.getenv("APP_NAME", "Expenses API")

DEBUG: bool = os.getenv("DEBUG", "true" if IS_DEV else "false").lower() == "true"

# Cache duration for the USD/UYU exchange rate
DOLLAR_CACHE_TTL: int = int(os.getenv("DOLLAR_CACHE_TTL", "300"))  # seconds

# ── CORS ──────────────────────────────────────────────────────────────────────

def _parse_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "")
    if raw.strip():
        return [o.strip() for o in raw.split(",")]
    # Dev default: allow everything
    # Prod default: restrictive — forces you to set ALLOWED_ORIGINS explicitly
    return ["*"] if IS_DEV else []

ALLOWED_ORIGINS: list[str] = _parse_origins()

# ── Validation ────────────────────────────────────────────────────────────────

def validate():
    """
    Validates that all required production settings are present.
    Called at startup — raises an error early rather than failing at runtime.
    """
    errors = []

    if IS_PROD and not DATABASE_URL:
        errors.append("DATABASE_URL is required in production.")

    if IS_PROD and not ALLOWED_ORIGINS:
        errors.append(
            "ALLOWED_ORIGINS is required in production. "
            "Set it to your app's URL, e.g. 'https://myapp.com'"
        )

    if errors:
        raise EnvironmentError(
            "Invalid configuration for production environment:\n" +
            "\n".join(f"  - {e}" for e in errors)
        )

# ── Debug summary ─────────────────────────────────────────────────────────────

def print_config():
    """Prints the current configuration at startup (only in dev mode)."""
    if not DEBUG:
        return
    db_info = DATABASE_URL[:30] + "..." if DATABASE_URL else "SQLite (local)"
    print(f"""
┌─ Config ({'PRODUCTION' if IS_PROD else 'DEVELOPMENT'}) {'─' * 30}
│  App name      : {APP_NAME}
│  Debug         : {DEBUG}
│  Database      : {db_info}
│  CORS origins  : {ALLOWED_ORIGINS}
│  Rate cache TTL: {DOLLAR_CACHE_TTL}s
└{'─' * 50}
""")
