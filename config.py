"""Central settings for the TeaTrail support app.

Every setting is resolved in the same order:
    1. Streamlit secrets (``.streamlit/secrets.toml`` locally, or the Secrets
       panel on Streamlit Community Cloud)
    2. Environment variables (a local ``.env`` file is loaded automatically)
    3. A safe built-in default
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent
load_dotenv(APP_DIR / ".env")

DEFAULT_MODELS = {
    "anthropic": "claude-opus-5-5",
    "openai": "gpt-5-mini",
    "gemini": "gemini-2.5-flash-lite",
}

PROVIDER_LABELS = {
    "anthropic": "Claude",
    "openai": "OpenAI",
    "gemini": "Gemini",
    "offline": "Offline FAQ mode",
}


def _secrets_available() -> bool:
    """True when a secrets.toml exists, so touching st.secrets won't warn."""
    candidates = [
        APP_DIR / ".streamlit" / "secrets.toml",
        Path.cwd() / ".streamlit" / "secrets.toml",
        Path.home() / ".streamlit" / "secrets.toml",
    ]
    return any(p.is_file() for p in candidates)


def get_setting(name: str, default: str = "") -> str:
    """Read a setting from st.secrets, then the environment, then ``default``."""
    if _secrets_available():
        try:
            import streamlit as st

            if name in st.secrets:
                value = st.secrets[name]
                if value is not None and str(value).strip() != "":
                    return str(value).strip()
        except Exception:  # secrets file malformed or Streamlit not running
            pass
    value = os.getenv(name)
    if value is not None and value.strip() != "":
        return value.strip()
    return default


# --------------------------------------------------------------------------
# Passcode
# --------------------------------------------------------------------------
def passcode_sha256() -> str:
    """Expected SHA-256 hex digest of the app passcode, or "" if none is configured.

    The passcode is never stored in the repository: set APP_PASSCODE (plain
    text) or APP_PASSCODE_SHA256 in Streamlit secrets or a local .env file.
    """
    plain = get_setting("APP_PASSCODE")
    if plain:
        return hashlib.sha256(plain.encode("utf-8")).hexdigest()
    hashed = get_setting("APP_PASSCODE_SHA256")
    if hashed:
        return hashed.lower()
    return ""


# --------------------------------------------------------------------------
# Knowledge base
# --------------------------------------------------------------------------
DEFAULT_FAQ_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/1bf4cNECDbar3tUeJn2-F64gahDJ001sGDtcDrv8V7Hc/edit"
)


def faq_sheet_url() -> str:
    """The FAQ sheet to load. Set FAQ_SHEET_CSV_URL to "sample" to use only the built-in FAQs."""
    url = get_setting("FAQ_SHEET_CSV_URL", DEFAULT_FAQ_SHEET_URL)
    return "" if url.lower() in {"sample", "none", "off"} else url


def data_dir() -> Path:
    path = Path(get_setting("DATA_DIR", str(APP_DIR / "data")))
    path.mkdir(parents=True, exist_ok=True)
    return path


# --------------------------------------------------------------------------
# LLM provider
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class LLMSettings:
    provider: str  # anthropic | openai | gemini | offline
    model: str
    api_key: str
    anthropic_fallbacks: bool = True

    @property
    def label(self) -> str:
        return PROVIDER_LABELS.get(self.provider, self.provider)


def _key_for(provider: str) -> str:
    if provider == "anthropic":
        return get_setting("ANTHROPIC_API_KEY")
    if provider == "openai":
        return get_setting("OPENAI_API_KEY")
    if provider == "gemini":
        return get_setting("GEMINI_API_KEY") or get_setting("GOOGLE_API_KEY")
    return ""


def llm_settings() -> LLMSettings:
    """Pick the provider from LLM_PROVIDER, auto-detecting from API keys.

    ``auto`` (the default) uses the first key it finds in the order
    Anthropic -> OpenAI -> Gemini. With no key at all, Tara runs in
    offline FAQ mode so the demo still works.
    """
    requested = get_setting("LLM_PROVIDER", "auto").lower()
    fallbacks = get_setting("ANTHROPIC_FALLBACKS", "on").lower() not in {"off", "false", "0", "no"}

    if requested in DEFAULT_MODELS:
        order = [requested]
    elif requested == "offline":
        order = []
    else:
        order = ["anthropic", "openai", "gemini"]

    for provider in order:
        key = _key_for(provider)
        if key:
            model = get_setting("LLM_MODEL", DEFAULT_MODELS[provider])
            return LLMSettings(provider, model, key, fallbacks)
    return LLMSettings("offline", "keyword retrieval", "", fallbacks)
