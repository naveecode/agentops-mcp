"""Ingest queue.

Without RABBITMQ_URL, documents are chunked and stored inline so the API and
tests stay synchronous. With a broker, POST /docs publishes to `ingest`.
The worker attempts each message MAX_RETRIES times, then publishes it to
`ingest.dlq`. The ingest queue is also dead-lettered by the broker, so a
rejected delivery lands on the same queue instead of being dropped.
"""
import json
import os

import pika

from .cache import invalidate_prefix
from .ingest import ingest_document

INGEST_QUEUE = "ingest"
DEAD_LETTER_QUEUE = "ingest.dlq"
DEAD_LETTER_EXCHANGE = "ingest.dlx"
MAX_RETRIES = 3


def uses_broker() -> bool:
    return bool(os.getenv("RABBITMQ_URL"))


def broker_parameters(url: str, *, attempts: int = 8) -> pika.URLParameters:
    """Retry long enough for RabbitMQ to finish starting in Compose or kind."""
    params = pika.URLParameters(url)
    params.connection_attempts = attempts
    params.retry_delay = 2
    return params


def declare(channel) -> None:
    channel.exchange_declare(exchange=DEAD_LETTER_EXCHANGE, exchange_type="direct", durable=True)
    channel.queue_declare(queue=DEAD_LETTER_QUEUE, durable=True)
    channel.queue_bind(
        queue=DEAD_LETTER_QUEUE,
        exchange=DEAD_LETTER_EXCHANGE,
        routing_key=INGEST_QUEUE,
    )
    channel.queue_declare(
        queue=INGEST_QUEUE,
        durable=True,
        arguments={
            "x-dead-letter-exchange": DEAD_LETTER_EXCHANGE,
            "x-dead-letter-routing-key": INGEST_QUEUE,
        },
    )


def failure_action(retries: int, max_retries: int = MAX_RETRIES) -> str:
    """Decide what to do after a failure. `retries` is how many have already been recorded."""
    if retries + 1 >= max_retries:
        return "dlq"
    return "retry"


def handle_delivery(
    body: bytes,
    headers: dict | None = None,
    *,
    max_retries: int = MAX_RETRIES,
    ingest=ingest_document,
) -> dict:
    headers = dict(headers or {})
    try:
        payload = json.loads(body)
        doc_id = payload["id"]
        text = payload["text"]
        if not isinstance(doc_id, str) or not isinstance(text, str):
            raise ValueError("id and text must be strings")
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raw = body if isinstance(body, (bytes, bytearray)) else str(body).encode()
        return {"action": "dlq", "body": raw, "headers": {**headers, "x-error": str(exc)}}
    try:
        ingest(doc_id, text)
    except Exception as exc:
        retries = int(headers.get("x-retries", 0) or 0)
        return {
            "action": failure_action(retries, max_retries),
            "body": body,
            "headers": {**headers, "x-retries": retries + 1, "x-error": str(exc)},
        }
    invalidate_prefix("ask:")
    return {"action": "ack"}


def enqueue(doc_id: str, text: str) -> dict:
    url = os.getenv("RABBITMQ_URL")
    if not url:
        ingest_document(doc_id, text)
        invalidate_prefix("ask:")
        return {"id": doc_id, "status": "stored"}
    body = json.dumps({"id": doc_id, "text": text}).encode()
    connection = pika.BlockingConnection(broker_parameters(url))
    try:
        channel = connection.channel()
        declare(channel)
        channel.basic_publish(
            exchange="",
            routing_key=INGEST_QUEUE,
            body=body,
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
        )
    finally:
        connection.close()
    return {"id": doc_id, "status": "queued"}
