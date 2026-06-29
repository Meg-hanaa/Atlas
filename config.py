"""Environment and subject configuration."""

import os
from functools import lru_cache

# Windows/Anaconda SSL: use system cert store for HTTPS (Hindsight, YouTube, OpenAI, Groq)
try:
    import pip_system_certs.wrapt_requests  # noqa: F401
except ImportError:
    pass

from dotenv import load_dotenv

load_dotenv()

from logging_config import setup_logging

setup_logging()

DEFAULT_SUBJECT = os.getenv("ATLAS_SUBJECT", "ml-notes")
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "atlas.db")


class MissingConfigError(RuntimeError):
    """Raised when a required API key or config value is missing."""


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value or value.startswith("your-"):
        raise MissingConfigError(
            f"Missing or placeholder value for {name}. "
            "Copy .env.example to .env and add your real API keys."
        )
    return value


def get_subject(subject: str | None = None) -> str:
    return subject or DEFAULT_SUBJECT


@lru_cache
def get_hindsight_client():
    from hindsight_client import Hindsight

    return Hindsight(
        base_url=require_env("HINDSIGHT_BASE_URL"),
        api_key=require_env("HINDSIGHT_API_KEY"),
    )


def get_vision_provider() -> tuple[str, str]:
    """Return (provider, api_key) for photo OCR."""
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key and not openai_key.startswith("your-"):
        return "openai", openai_key
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key and not anthropic_key.startswith("your-"):
        return "anthropic", anthropic_key
    raise MissingConfigError(
        "Photo OCR requires OPENAI_API_KEY or ANTHROPIC_API_KEY in .env"
    )


def ensure_groq_key() -> str:
    return require_env("GROQ_API_KEY")
