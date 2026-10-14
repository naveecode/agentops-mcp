import pytest


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    """Keep the suite on the deterministic router unless a test opts into the LLM."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
