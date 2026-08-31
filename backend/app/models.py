from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Source(Base):
    """A feed we pull articles from. One row per RSS feed / API source."""

    __tablename__ = "sources"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    url = Column(String(1024), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    articles = relationship("Article", back_populates="source")


class Article(Base):
    """
    A single ingested article.

    `url` is unique so re-fetching the same feed doesn't create duplicates —
    this is our first (crude) line of defense; Phase 4 adds title-similarity
    and semantic dedup on top of this.
    """

    __tablename__ = "articles"

    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    title = Column(String(1024), nullable=False)
    content = Column(Text, nullable=True)
    url = Column(String(2048), nullable=False, unique=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    # embedding column intentionally omitted until Phase 4 (pgvector arrives then)

    source = relationship("Source", back_populates="articles")

    __table_args__ = (
        Index("ix_articles_published_at", "published_at"),
        Index("ix_articles_source_id", "source_id"),
    )
