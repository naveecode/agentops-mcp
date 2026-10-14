from fastapi.testclient import TestClient
from app.main import app
from app.store import MongoStore, reset_store
from tests.test_store import _Database
c=TestClient(app)
def test_calc(): assert c.post("/ask",json={"question":"2*(3+4)"}).json()["answer"]==14
def test_search_and_cache():
    c.post("/docs",json={"id":"d1","text":"refund policy is 30 days"})
    r=c.post("/ask",json={"question":"refund policy"}).json(); assert r["answer"][0]["id"]=="d1"
    assert c.post("/ask",json={"question":"refund policy"}).json()["cached"]
def test_health_reports_store():
    body=c.get("/health").json()
    assert body["ok"] is True and body["store"]=="memory"
def test_ask_records_one_chat_until_the_question_changes():
    c.post("/ask",json={"question":"2*(3+4)"})
    c.post("/ask",json={"question":"2*(3+4)"})
    chats=c.get("/chats").json()["chats"]
    assert len(chats)==1 and chats[0]["answer"]==14 and chats[0]["tool"]=="calculator"
def test_api_writes_through_a_mongo_store():
    store=MongoStore(database=_Database())
    reset_store(store)
    c.post("/docs",json={"id":"d1","text":"refund policy is 30 days"})
    assert store.search("refund policy")[0]["id"]=="d1"
    c.post("/ask",json={"question":"refund policy details"})
    assert store.recent_chats()[0]["tool"]=="search_docs"
