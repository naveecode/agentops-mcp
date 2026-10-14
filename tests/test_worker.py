"""Retries, the dead-letter queue, and inline ingest without a broker."""
import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.queue import enqueue, failure_action, handle_delivery
from app.tools import search_docs
from app.worker import on_message

client = TestClient(app)


class _Channel:
    def __init__(self):
        self.acked = []
        self.published = []

    def basic_ack(self, tag):
        self.acked.append(tag)

    def basic_publish(self, exchange, routing_key, body, properties):
        self.published.append((routing_key, body, properties.headers))


def test_three_failures_end_on_the_dead_letter_queue():
    assert [failure_action(n) for n in range(3)] == ["retry", "retry", "dlq"]

    def boom(doc_id, text):
        raise RuntimeError("embed down")

    body = json.dumps({"id": "d1", "text": "hello"}).encode()
    headers = {}
    actions = []
    for _ in range(3):
        result = handle_delivery(body, headers, ingest=boom)
        actions.append(result["action"])
        headers = result["headers"]
    assert actions == ["retry", "retry", "dlq"]
    assert headers["x-retries"] == 3
    assert "embed down" in headers["x-error"]


def test_invalid_payloads_skip_retries():
    result = handle_delivery(b"not-json", {})
    assert result["action"] == "dlq"
    assert "x-retries" not in result["headers"]
    missing = handle_delivery(json.dumps({"id": "d1"}).encode(), {})
    assert missing["action"] == "dlq"


def test_successful_delivery_stores_and_acks():
    body = json.dumps({"id": "d1", "text": "refund policy is 30 days"}).encode()
    assert handle_delivery(body, {})["action"] == "ack"
    assert search_docs("refund policy")[0]["id"] == "d1"


def test_worker_publishes_retries_and_dead_letters(monkeypatch):
    calls = {"n": 0}

    def flaky(body, headers):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"action": "retry", "body": body, "headers": {"x-retries": 1}}
        return {"action": "dlq", "body": body, "headers": {"x-retries": 3, "x-error": "nope"}}

    monkeypatch.setattr("app.worker.handle_delivery", flaky)
    channel = _Channel()
    delivery = SimpleNamespace(delivery_tag=7)
    on_message(channel, delivery, SimpleNamespace(headers={}), b"{}")
    on_message(channel, delivery, SimpleNamespace(headers={}), b"{}")
    assert channel.acked == [7, 7]
    assert [item[0] for item in channel.published] == ["ingest", "ingest.dlq"]


def test_enqueue_publishes_when_a_broker_is_configured(monkeypatch):
    published = {}

    class Channel:
        def exchange_declare(self, **kwargs):
            pass

        def queue_declare(self, **kwargs):
            pass

        def queue_bind(self, **kwargs):
            pass

        def basic_publish(self, **kwargs):
            published.update(kwargs)

    class Connection:
        def channel(self):
            return Channel()

        def close(self):
            pass

    monkeypatch.setenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    monkeypatch.setattr("app.queue.pika.BlockingConnection", lambda params: Connection())
    monkeypatch.setattr("app.queue.pika.URLParameters", lambda url: url)
    assert enqueue("d1", "hello") == {"id": "d1", "status": "queued"}
    assert published["routing_key"] == "ingest"
    assert json.loads(published["body"]) == {"id": "d1", "text": "hello"}


def test_inline_ingest_replaces_a_cached_miss():
    assert client.post("/ask", json={"question": "refund policy"}).json()["answer"] == []
    stored = client.post("/docs", json={"id": "d1", "text": "refund policy is 30 days"}).json()
    assert stored == {"id": "d1", "status": "stored"}
    again = client.post("/ask", json={"question": "refund policy"}).json()
    assert again["cached"] is False
    assert again["answer"][0]["id"] == "d1"


def test_health_reports_inline_queue_without_a_broker():
    body = client.get("/health").json()
    assert body["queue"] == "inline"
    assert body["cache"] == "memory"


def test_worker_refuses_to_start_without_a_broker(monkeypatch):
    monkeypatch.delenv("RABBITMQ_URL", raising=False)
    from app.worker import main

    try:
        main()
    except SystemExit as exc:
        assert "RABBITMQ_URL" in str(exc)
    else:
        raise AssertionError("worker should exit when RABBITMQ_URL is unset")
