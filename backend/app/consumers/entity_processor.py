import json
import logging
import os

import spacy
from confluent_kafka import Consumer, KafkaError
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import Article, ArticleEntity, Entity

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("entity_processor")

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
nlp = spacy.load("en_core_web_sm")

TOPIC_TAXONOMY = {
    "Artificial Intelligence": [
        "ai",
        "chatgpt",
        "llm",
        "machine learning",
        "openai",
        "anthropic",
        "claude",
    ],
    "Robotics": [
        "robot",
        "robotics",
        "automation",
        "drone",
        "humanoid",
    ],
    "Space": [
        "nasa",
        "spacex",
        "satellite",
        "rocket",
        "orbit",
        "astronaut",
    ],
    "Business & Finance": [
        "funding",
        "valuation",
        "ipo",
        "acquisition",
        "investor",
        "startup",
    ],
    "Policy & Regulation": [
        "regulation",
        "lawsuit",
        "congress",
        "senate",
        "ftc",
        "antitrust",
    ],
    "Gaming & Entertainment": [
        "game",
        "gaming",
        "movie",
        "streaming",
        "netflix",
    ],
    "Cybersecurity": [
        "hack",
        "breach",
        "vulnerability",
        "malware",
        "exploit",
    ],
}


def classify_article_topic(text: str) -> str:
    """
    Classify article text into a topic based on keyword matching.
    
    Returns the topic name with the most matches, or "Uncategorized" if
    there's a tie or zero matches.
    """
    text_lower = text.lower()
    topic_scores = {}
    
    for topic, keywords in TOPIC_TAXONOMY.items():
        score = sum(1 for keyword in keywords if keyword in text_lower)
        topic_scores[topic] = score
    
    max_score = max(topic_scores.values())
    if max_score == 0:
        return "Uncategorized"
    
    # Count how many topics have the max score
    topics_with_max = [t for t, s in topic_scores.items() if s == max_score]
    
    if len(topics_with_max) > 1:
        # Tie: return "Uncategorized"
        return "Uncategorized"
    
    return topics_with_max[0]


def process_article(article_id: int, db) -> int:
    article = db.get(Article, article_id)
    if article is None:
        raise ValueError(f"Article not found for id={article_id}")

    text = f"{article.title}\n{article.content or ''}"
    
    # Classify topic
    topic = classify_article_topic(text)
    article.topic = topic
    
    # Extract entities
    entities_found = nlp(text).ents

    for entity_span in entities_found:
        entity = (
            db.query(Entity)
            .filter(
                func.lower(Entity.name) == entity_span.text.lower(),
                Entity.type == entity_span.label_,
            )
            .first()
        )
        if entity is None:
            entity = Entity(name=entity_span.text, type=entity_span.label_)
            db.add(entity)
            db.flush()

        try:
            with db.begin_nested():
                article_entity = (
                    db.query(ArticleEntity)
                    .filter(
                        ArticleEntity.article_id == article.id,
                        ArticleEntity.entity_id == entity.id,
                    )
                    .first()
                )
                if article_entity is None:
                    db.add(ArticleEntity(article_id=article.id, entity_id=entity.id))
                    db.flush()
        except IntegrityError:
            logger.info(
                "Skipped duplicate entity link for article_id=%s entity=%s type=%s",
                article.id,
                entity.name,
                entity.type,
            )

    db.commit()
    logger.info(
        "Processed article_id=%s: found %d entities, classified topic=%s",
        article.id,
        len(entities_found),
        article.topic,
    )
    return len(entities_found)


def consume_messages():
    consumer = Consumer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "group.id": "entity-processor-group",
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
        }
    )
    consumer.subscribe(["news.processed"])

    logger.info(
        "Subscribed to news.processed with bootstrap servers %s",
        KAFKA_BOOTSTRAP_SERVERS,
    )

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
                process_article(int(payload["id"]), db)
                consumer.commit(message=msg, asynchronous=False)
            except Exception as exc:
                db.rollback()
                logger.exception("Failed to process news.processed message: %s", exc)
            finally:
                db.close()
    finally:
        consumer.close()


if __name__ == "__main__":
    consume_messages()