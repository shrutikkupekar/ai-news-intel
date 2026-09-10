import json
import logging
import os
from datetime import datetime, timedelta

from confluent_kafka import Consumer, KafkaError, Producer
from rapidfuzz import fuzz
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import Article, Source

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("raw_consumer")

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
kafka_producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})


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


def check_for_duplicate(db, title: str, published_at: datetime, time_window_hours: int = 6) -> tuple[int | None, float]:
    """
    Check if an article with the given title and published_at is a duplicate of an existing article.
    
    Returns:
        A tuple of (duplicate_article_id, similarity_score) if a duplicate is found (score >= 55),
        otherwise (None, 0.0)
    """
    if not published_at:
        return None, 0.0
    
    # Query for articles published within the time window
    time_window_start = published_at - timedelta(hours=time_window_hours)
    time_window_end = published_at + timedelta(hours=time_window_hours)
    
    existing_articles = db.query(Article).filter(
        Article.published_at.isnot(None),
        Article.published_at >= time_window_start,
        Article.published_at <= time_window_end,
    ).all()
    
    best_match_id = None
    best_score = 0.0
    
    for existing in existing_articles:
        score = fuzz.token_sort_ratio(title, existing.title, score_cutoff=0)
        if score >= 55 and score > best_score:
            best_match_id = existing.id
            best_score = score
    
    if best_match_id is not None:
        return best_match_id, best_score
    
    return None, 0.0


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
                
                # Check for duplicates before inserting
                duplicate_of_id, similarity_score = check_for_duplicate(db, title, published_at)
                
                article = Article(
                    source_id=source.id,
                    title=title.strip(),
                    content=content,
                    url=url.strip(),
                    published_at=published_at,
                    duplicate_of_id=duplicate_of_id,
                )
                db.add(article)
                db.commit()
                consumer.commit(message=msg, asynchronous=False)
                
                # Only publish to news.processed if it's a new article, not a duplicate
                if duplicate_of_id is None:
                    kafka_producer.produce(
                        topic="news.processed",
                        key=article.url,
                        value=json.dumps({"id": article.id, "url": article.url}),
                    )
                    kafka_producer.flush()
                    logger.info(
                        "Inserted new article from source=%s title=%s url=%s",
                        source_name,
                        title,
                        url,
                    )
                else:
                    logger.info(
                        "Inserted duplicate of article %d, score=%.1f from source=%s title=%s url=%s",
                        duplicate_of_id,
                        similarity_score,
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
