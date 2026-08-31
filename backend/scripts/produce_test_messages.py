import json
import os
import sys

from confluent_kafka import Producer

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")


def publish_test_messages(count: int) -> None:
    producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})

    for i in range(count):
        payload = {
            "source": "Ticket4Test",
            "title": f"Test article {i}",
            "url": f"test://ticket4/{i}",
            "published_at": None,
            "content": f"synthetic test message {i}",
        }
        producer.produce(
            topic="news.raw",
            key=payload["url"],
            value=json.dumps(payload, default=str),
        )

    producer.flush()
    print(f"Published {count} synthetic messages to news.raw via {KAFKA_BOOTSTRAP_SERVERS}")


if __name__ == "__main__":
    try:
        count = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    except ValueError:
        print("Usage: python produce_test_messages.py [count]", file=sys.stderr)
        raise SystemExit(1)

    if count < 0:
        print("Count must be non-negative.", file=sys.stderr)
        raise SystemExit(1)

    publish_test_messages(count)
