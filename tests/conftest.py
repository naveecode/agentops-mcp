import pytest

from app.cache import clear
from app.store import reset_store


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    """Keep the suite offline: router, memory store, inline ingest."""
    for name in ("OPENAI_API_KEY", "MONGO_URL", "MONGO_VECTOR_INDEX", "RABBITMQ_URL", "REDIS_URL"):
        monkeypatch.delenv(name, raising=False)
    reset_store()
    clear()
    yield
    reset_store()
    clear()
