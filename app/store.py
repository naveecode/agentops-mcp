"""Document chunks and chat turns.

MongoDB when MONGO_URL is set, otherwise memory. Both backends rank chunks
with the same function: a chunk must share a query token, and cosine
similarity over the stored embedding breaks ties. Set MONGO_VECTOR_INDEX to
query an Atlas vector index first.
"""
import os
import threading
from datetime import datetime, timezone

from pymongo import MongoClient

from .embeddings import cosine, embed, tokens

_store = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def rank_chunks(query: str, chunks: list[dict], k: int = 3) -> list[dict]:
    query_tokens = tokens(query)
    if not query_tokens:
        return []
    query_vector = embed(query)
    scored = []
    for chunk in chunks:
        overlap = len(query_tokens & tokens(chunk["text"]))
        if overlap <= 0:
            continue
        keyword = overlap / len(query_tokens)
        vector = max(cosine(query_vector, chunk["embedding"]), 0.0)
        scored.append((keyword + 0.25 * vector, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    hits = []
    seen = set()
    for score, chunk in scored:
        doc_id = chunk["doc_id"]
        if doc_id in seen:
            continue
        seen.add(doc_id)
        hits.append({"id": doc_id, "text": chunk["text"][:300], "score": round(score, 4)})
        if len(hits) >= k:
            break
    return hits


class MemoryStore:
    backend = "memory"

    def __init__(self):
        self._chunks: list[dict] = []
        self._chats: list[dict] = []
        self._lock = threading.Lock()

    def replace_doc(self, doc_id: str, chunks: list[dict]) -> None:
        with self._lock:
            self._chunks = [chunk for chunk in self._chunks if chunk["doc_id"] != doc_id]
            self._chunks.extend(chunks)

    def all_chunks(self) -> list[dict]:
        with self._lock:
            return list(self._chunks)

    def search(self, query: str, k: int = 3) -> list[dict]:
        return rank_chunks(query, self.all_chunks(), k)

    def add_chat(self, turn: dict) -> dict:
        stored = {**turn, "created_at": _now()}
        with self._lock:
            self._chats.append(stored)
        return stored

    def recent_chats(self, limit: int = 20) -> list[dict]:
        with self._lock:
            return list(reversed(self._chats[-limit:]))


class MongoStore:
    backend = "mongo"

    def __init__(self, url: str | None = None, database=None):
        if database is None:
            if not url:
                raise ValueError("MONGO_URL is required")
            client = MongoClient(url, serverSelectionTimeoutMS=3000)
            client.admin.command("ping")
            database = client[os.getenv("MONGO_DB", "agentops")]
        self.chunks = database.chunks
        self.chats = database.chats
        self.chunks.create_index("doc_id")
        self.chats.create_index("created_at")

    def replace_doc(self, doc_id: str, chunks: list[dict]) -> None:
        self.chunks.delete_many({"doc_id": doc_id})
        if chunks:
            self.chunks.insert_many(chunks)

    def search(self, query: str, k: int = 3) -> list[dict]:
        vector_hits = self._vector_search(embed(query), k)
        if vector_hits:
            return vector_hits
        stored = list(self.chunks.find({}, {"_id": 0}))
        return rank_chunks(query, stored, k)

    def _vector_search(self, vector: list[float], k: int) -> list[dict] | None:
        index = os.getenv("MONGO_VECTOR_INDEX")
        if not index:
            return None
        pipeline = [
            {
                "$vectorSearch": {
                    "index": index,
                    "path": "embedding",
                    "queryVector": vector,
                    "numCandidates": max(k * 20, 40),
                    "limit": k,
                }
            },
            {"$project": {"doc_id": 1, "text": 1, "score": {"$meta": "vectorSearchScore"}}},
        ]
        try:
            rows = list(self.chunks.aggregate(pipeline))
        except Exception:
            return None
        if not rows:
            return None
        return [
            {
                "id": row["doc_id"],
                "text": str(row.get("text", ""))[:300],
                "score": round(float(row.get("score", 0.0)), 4),
            }
            for row in rows
        ]

    def add_chat(self, turn: dict) -> dict:
        stored = {**turn, "created_at": _now()}
        self.chats.insert_one(dict(stored))
        return stored

    def recent_chats(self, limit: int = 20) -> list[dict]:
        rows = self.chats.find({}, {"_id": 0}).sort("created_at", -1).limit(limit)
        return list(rows)


def get_store():
    global _store
    if _store is None:
        url = os.getenv("MONGO_URL")
        _store = MongoStore(url) if url else MemoryStore()
    return _store


def reset_store(store=None) -> None:
    global _store
    _store = store
