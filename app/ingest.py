"""Split a document into chunks and store embeddings."""
from .embeddings import chunk_text, embed
from .store import get_store


def ingest_document(doc_id: str, text: str, size: int = 500, overlap: int = 50) -> dict:
    pieces = chunk_text(text, size=size, overlap=overlap)
    chunks = [
        {
            "doc_id": doc_id,
            "chunk_id": f"{doc_id}:{index}",
            "text": piece,
            "embedding": embed(piece),
        }
        for index, piece in enumerate(pieces)
    ]
    get_store().replace_doc(doc_id, chunks)
    return {"id": doc_id, "chunks": len(chunks)}
