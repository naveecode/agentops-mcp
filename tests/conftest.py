import pytest

from app import main
from app.store import reset_store


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    """Keep the suite on the deterministic router and the in-memory store."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("MONGO_URL", raising=False)
    monkeypatch.delenv("MONGO_VECTOR_INDEX", raising=False)
    reset_store()
    main._cache.clear()
    yield
    reset_store()
    main._cache.clear()
