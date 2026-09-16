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
from pgvector.sqlalchemy import Vector

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
    topic = Column(String(255), nullable=True)
    duplicate_of_id = Column(Integer, ForeignKey("articles.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    embedding = Column(Vector(384), nullable=True)

    source = relationship("Source", back_populates="articles")
    article_entities = relationship("ArticleEntity", back_populates="article")

    __table_args__ = (
        Index("ix_articles_published_at", "published_at"),
        Index("ix_articles_source_id", "source_id"),
    )


class Entity(Base):
    __tablename__ = "entities"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    type = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    article_entities = relationship("ArticleEntity", back_populates="entity")


class ArticleEntity(Base):
    __tablename__ = "article_entities"

    id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    entity_id = Column(Integer, ForeignKey("entities.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    article = relationship("Article", back_populates="article_entities")
    entity = relationship("Entity", back_populates="article_entities")

    __table_args__ = (
        UniqueConstraint("article_id", "entity_id", name="uq_article_entity"),
    )
