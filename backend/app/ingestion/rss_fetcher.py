"""
Phase 1 ingestion: pull articles from a fixed list of RSS feeds on a timer.

Deliberately simple — no Kafka yet. The point of this phase is to learn:
  - talking to external, unreliable sources (timeouts, retries)
  - normalizing messy external data into a clean schema
  - avoiding duplicate writes
Phase 2 replaces the direct "fetch -> write to Postgres" path with
"fetch -> publish to Kafka -> consumer writes to Postgres" without changing
this file's fetching logic much at all.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import httpx
from bs4 import BeautifulSoup
from confluent_kafka import Producer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Source, Article

logger = logging.getLogger("ingestion")

# Small, deliberately diverse seed list. Add more once the pipeline is proven.
SEED_SOURCES = [
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
    {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index"},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml"},
    {"name": "Reuters Technology", "url": "https://www.reutersagency.com/feed/?best-topics=tech"},
    {"name": "Hacker News (Front Page)", "url": "https://hnrss.org/frontpage"},
]

MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2
REQUEST_TIMEOUT = 10.0
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")

kafka_producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})


def fetch_feed_bytes(url: str) -> bytes | None:
    """Fetch a feed URL with basic retry + exponential backoff."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = httpx.get(
                url,
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": "ai-news-intel/0.1 (learning project)"},
                follow_redirects=True,
            )
            resp.raise_for_status()
            return resp.content
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            logger.warning(
                "fetch failed for %s (attempt %d/%d): %s", url, attempt, MAX_RETRIES, e
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    logger.error("giving up on %s after %d attempts", url, MAX_RETRIES)
    return None


def _parse_published(entry) -> datetime | None:
    """feedparser gives inconsistent date formats across feeds — normalize to UTC."""
    for field in ("published", "updated"):
        raw = getattr(entry, field, None)
        if raw:
            try:
                dt = parsedate_to_datetime(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except (TypeError, ValueError):
                continue
    return None


def _validate_entry(entry) -> bool:
    """Skip entries missing the fields we require. Basic data validation."""
    return bool(getattr(entry, "title", None) and getattr(entry, "link", None))


def get_or_create_source(db: Session, name: str, url: str) -> Source:
    source = db.query(Source).filter(Source.url == url).first()
    if source:
        return source
    source = Source(name=name, url=url)
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def ingest_source(db: Session, name: str, feed_url: str) -> dict:
    """Fetch one feed and write new articles. Returns a small stats dict."""
    stats = {"source": name, "fetched": 0, "inserted": 0, "skipped_duplicate": 0, "skipped_invalid": 0}

    raw = fetch_feed_bytes(feed_url)
    if raw is None:
        stats["error"] = "fetch_failed"
        return stats

    parsed = feedparser.parse(raw)
    source = get_or_create_source(db, name, feed_url)

    for entry in parsed.entries:
        stats["fetched"] += 1

        if not _validate_entry(entry):
            stats["skipped_invalid"] += 1
            continue

        url = entry.link.strip()
        published_at = _parse_published(entry)
        content = BeautifulSoup(getattr(entry, "summary", None) or "", "html.parser").get_text()
        payload = {
            "source": name,
            "title": entry.title.strip(),
            "url": url,
            "published_at": published_at.isoformat() if published_at else None,
            "content": content,
        }
        kafka_producer.produce(
            topic="news.raw",
            key=url,
            value=json.dumps(payload, default=str),
        )
        kafka_producer.flush()
        stats["inserted"] += 1

    return stats


def ingest_all(db: Session) -> list[dict]:
    results = []
    for src in SEED_SOURCES:
        result = ingest_source(db, src["name"], src["url"])
        logger.info("ingest result: %s", result)
        results.append(result)
    return results
