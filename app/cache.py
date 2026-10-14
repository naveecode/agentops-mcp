"""Ask-response cache. Redis when REDIS_URL is set, else process memory."""
import os

_memory: dict[str, str] = {}
_client = None
_checked = False


def _redis():
    global _client, _checked
    if not _checked:
        _checked = True
        url = os.getenv("REDIS_URL")
        if url:
            import redis

            _client = redis.from_url(url)
    return _client


def get(key: str):
    client = _redis()
    if client is not None:
        return client.get(key)
    return _memory.get(key)


def set(key: str, value: str, ttl: int = 3600) -> None:
    client = _redis()
    if client is not None:
        client.setex(key, ttl, value)
        return
    _memory[key] = value


def invalidate_prefix(prefix: str) -> None:
    client = _redis()
    if client is not None:
        for key in client.scan_iter(match=f"{prefix}*"):
            client.delete(key)
        return
    for key in [key for key in _memory if key.startswith(prefix)]:
        del _memory[key]


def backend() -> str:
    return "redis" if _redis() else "memory"


def clear() -> None:
    """Drop the in-memory cache and reconnect Redis on the next call."""
    global _client, _checked
    _memory.clear()
    _client = None
    _checked = False
