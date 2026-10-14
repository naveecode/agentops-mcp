from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app)
def test_calc(): assert c.post("/ask",json={"question":"2*(3+4)"}).json()["answer"]==14
def test_search_and_cache():
    c.post("/docs",json={"id":"d1","text":"refund policy is 30 days"})
    r=c.post("/ask",json={"question":"refund policy"}).json(); assert r["answer"][0]["id"]=="d1"
    assert c.post("/ask",json={"question":"refund policy"}).json()["cached"]
