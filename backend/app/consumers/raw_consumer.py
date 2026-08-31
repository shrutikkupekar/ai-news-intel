import json
import logging
import os
from datetime import datetime

from confluent_kafka import Consumer, KafkaError
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import Article, Source

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("raw_consumer")

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")


def get_or_create_source(db, name: str, url: str) -> Source:
    source = db.query(Source).filter(Source.url == url).first()
    if source:
        return source
    source = Source(name=name, url=url)
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def parse_published_at(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def consume_messages():
    consumer = Consumer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "group.id": "raw-consumer-group",
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
        }
    )
    consumer.subscribe(["news.raw"])

    logger.info("Subscribed to news.raw with bootstrap servers %s", KAFKA_BOOTSTRAP_SERVERS)

    try:
        while True:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                logger.error("Kafka consumer error: %s", msg.error())
                continue

            db = SessionLocal()
            try:
                payload = json.loads(msg.value().decode("utf-8"))
                source_name = payload.get("source")
                title = payload.get("title")
                url = payload.get("url")
                content = payload.get("content")
                published_at = parse_published_at(payload.get("published_at"))

                if not source_name or not title or not url:
                    logger.warning("Skipping invalid payload for news.raw: %s", payload)
                    continue

                source = get_or_create_source(db, source_name, url)
                article = Article(
                    source_id=source.id,
                    title=title.strip(),
                    content=content,
                    url=url.strip(),
                    published_at=published_at,
                )
                db.add(article)
                db.commit()
                consumer.commit(message=msg, asynchronous=False)
                logger.info(
                    "Inserted article from source=%s title=%s url=%s",
                    source_name,
                    title,
                    url,
                )
            except IntegrityError:
                db.rollback()
                consumer.commit(message=msg, asynchronous=False)
                logger.info("Skipped duplicate article for url=%s", payload.get("url") if "payload" in locals() else "unknown")
            except Exception as exc:
                db.rollback()
                logger.exception("Failed to process message from news.raw: %s", exc)
            finally:
                db.close()
    finally:
        consumer.close()


if __name__ == "__main__":
    consume_messages()
