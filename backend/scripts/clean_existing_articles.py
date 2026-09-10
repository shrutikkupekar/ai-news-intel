import json
import logging
import os

from bs4 import BeautifulSoup
from confluent_kafka import Producer

from app.database import SessionLocal
from app.models import Article

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("clean_existing_articles")

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")


def clean_existing_articles() -> None:
    producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})
    db = SessionLocal()
    try:
        articles = db.query(Article).all()
        for article in articles:
            article.content = BeautifulSoup(
                article.content or "", "html.parser"
            ).get_text()
            db.commit()

            producer.produce(
                topic="news.processed",
                key=article.url,
                value=json.dumps({"id": article.id, "url": article.url}),
            )
            producer.flush()
            logger.info("Cleaned article_id=%s and republished for processing", article.id)
    finally:
        db.close()


if __name__ == "__main__":
    clean_existing_articles()