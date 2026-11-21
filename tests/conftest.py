import sys
from pathlib import Path

import pytest

TEST_PASSCODE = "test-passcode"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Each test gets its own data dir and no real API keys or sheet URL."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    for var in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
                "APP_PASSCODE", "APP_PASSCODE_SHA256", "LLM_MODEL"]:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "auto")
    monkeypatch.setenv("FAQ_SHEET_CSV_URL", "sample")
    monkeypatch.setenv("APP_PASSCODE", TEST_PASSCODE)
    yield
