"""Memory and Mongo stores share ranking, chunk replacement, and chat history."""
from app.ingest import ingest_document
from app.store import MongoStore, get_store, reset_store
from app.tools import search_docs


class _Cursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, key, direction):
        self._docs.sort(key=lambda doc: doc.get(key, ""), reverse=direction < 0)
        return self

    def limit(self, count):
        self._docs = self._docs[:count]
        return self

    def __iter__(self):
        return iter(self._docs)


class _Collection:
    def __init__(self):
        self.docs = []
        self.aggregate_result = None
        self.aggregate_error = None

    def create_index(self, *args, **kwargs):
        return "index"

    def delete_many(self, filt):
        self.docs = [doc for doc in self.docs if not _matches(doc, filt)]

    def insert_many(self, docs):
        self.docs.extend(dict(doc) for doc in docs)

    def insert_one(self, doc):
        self.docs.append(dict(doc))

    def find(self, filt=None, projection=None):
        rows = []
        for doc in self.docs:
            if _matches(doc, filt or {}):
                row = dict(doc)
                if projection and projection.get("_id") == 0:
                    row.pop("_id", None)
                rows.append(row)
        return _Cursor(rows)

    def aggregate(self, pipeline):
        if self.aggregate_error:
            raise self.aggregate_error
        if self.aggregate_result is None:
            raise RuntimeError("vector index missing")
        return list(self.aggregate_result)


class _Database:
    def __init__(self):
        self.chunks = _Collection()
        self.chats = _Collection()


def _matches(doc, filt):
    return all(doc.get(key) == value for key, value in filt.items())


def test_search_prefers_the_document_that_shares_tokens():
    ingest_document("d1", "refund policy is 30 days")
    ingest_document("d2", "shipping takes five business days")
    assert search_docs("refund policy")[0]["id"] == "d1"
    assert search_docs("shipping days")[0]["id"] == "d2"


def test_replacing_a_document_drops_stale_chunks():
    ingest_document("d1", "refund policy is 30 days")
    ingest_document("d1", "shipping takes five business days")
    assert search_docs("refund policy") == []
    assert search_docs("shipping")[0]["id"] == "d1"


def test_long_document_is_chunked_and_still_searchable():
    text = ("alpha " * 80) + "unique refund policy marker " + ("beta " * 80)
    stored = ingest_document("long", text, size=120, overlap=20)
    assert stored["chunks"] > 1
    hit = search_docs("unique refund policy marker")[0]
    assert hit["id"] == "long"
    assert "refund policy" in hit["text"]


def test_chat_history_is_newest_first():
    store = get_store()
    store.add_chat({"question": "first", "answer": 1, "mode": "router", "tool": "calculator"})
    store.add_chat({"question": "second", "answer": [], "mode": "router", "tool": "search_docs"})
    assert [turn["question"] for turn in store.recent_chats()] == ["second", "first"]


def test_mongo_store_searches_and_records_chats():
    store = MongoStore(database=_Database())
    reset_store(store)
    assert ingest_document("d1", "refund policy is 30 days")["chunks"] == 1
    assert store.search("refund policy")[0]["id"] == "d1"
    store.add_chat({"question": "refund policy", "answer": [], "mode": "router"})
    assert store.recent_chats(1)[0]["question"] == "refund policy"


def test_mongo_uses_atlas_vector_search_when_configured(monkeypatch):
    monkeypatch.setenv("MONGO_VECTOR_INDEX", "chunks_vector")
    database = _Database()
    database.chunks.aggregate_result = [{"doc_id": "d9", "text": "from atlas", "score": 0.91}]
    hits = MongoStore(database=database).search("anything at all")
    assert hits == [{"id": "d9", "text": "from atlas", "score": 0.91}]


def test_mongo_falls_back_when_vector_search_is_unavailable(monkeypatch):
    monkeypatch.setenv("MONGO_VECTOR_INDEX", "chunks_vector")
    database = _Database()
    database.chunks.aggregate_error = RuntimeError("index missing")
    store = MongoStore(database=database)
    reset_store(store)
    ingest_document("d1", "refund policy is 30 days")
    assert store.search("refund policy")[0]["id"] == "d1"
