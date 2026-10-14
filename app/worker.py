"""Consume ingest messages. Run with: python -m app.worker"""
import os

import pika

from .queue import DEAD_LETTER_QUEUE, INGEST_QUEUE, declare, handle_delivery


def _publish(channel, queue: str, body: bytes, headers: dict) -> None:
    channel.basic_publish(
        exchange="",
        routing_key=queue,
        body=body,
        properties=pika.BasicProperties(
            content_type="application/json",
            delivery_mode=2,
            headers=headers,
        ),
    )


def on_message(channel, method, properties, body) -> None:
    headers = dict(properties.headers or {}) if properties else {}
    result = handle_delivery(body, headers)
    if result["action"] == "retry":
        _publish(channel, INGEST_QUEUE, result["body"], result["headers"])
    elif result["action"] == "dlq":
        _publish(channel, DEAD_LETTER_QUEUE, result["body"], result["headers"])
    channel.basic_ack(method.delivery_tag)


def run_worker(url: str | None = None) -> None:
    url = url or os.environ["RABBITMQ_URL"]
    connection = pika.BlockingConnection(pika.URLParameters(url))
    channel = connection.channel()
    declare(channel)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=INGEST_QUEUE, on_message_callback=on_message)
    print(f"consuming {INGEST_QUEUE}; failures dead-letter to {DEAD_LETTER_QUEUE}", flush=True)
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
        connection.close()


def main() -> None:
    if not os.getenv("RABBITMQ_URL"):
        raise SystemExit("RABBITMQ_URL is required to run the worker")
    run_worker()


if __name__ == "__main__":
    main()
