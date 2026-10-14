"""Chunking and a deterministic local embedding.

The vector is a hashed bag of words. It is stable across processes, so tests
and the offline demo can rank documents without an embedding API. Production
semantic search uses MongoDB Atlas when MONGO_VECTOR_INDEX is set.
"""
import hashlib
import math
import re

DIM = 256
_TOKEN = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


def embed(text: str, dim: int = DIM) -> list[float]:
    vector = [0.0] * dim
    found = _TOKEN.findall(text.lower())
    if not found:
        return vector
    for token in found:
        digest = hashlib.sha256(token.encode()).digest()
        bucket = int.from_bytes(digest[:8], "big") % dim
        sign = 1.0 if digest[8] % 2 == 0 else -1.0
        vector[bucket] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def chunk_text(text: str, size: int = 500, overlap: int = 50) -> list[str]:
    body = text.strip()
    if not body:
        return []
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must be smaller than size")
    if len(body) <= size:
        return [body]
    chunks = []
    start = 0
    while start < len(body):
        end = min(len(body), start + size)
        chunks.append(body[start:end])
        if end == len(body):
            break
        start = end - overlap
    return chunks
