import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

import numpy as np
from sqlalchemy import func

from app.models import Article, Story, StoryArticle, utcnow

logger = logging.getLogger("clustering")

STORY_SIMILARITY_THRESHOLD = 0.6
STORY_WINDOW_HOURS = 24


@dataclass
class StoryAssignment:
    story_id: int
    similarity: Optional[float]
    status: str  # "joined", "created" or "existing"


def assign_to_story(db, article) -> StoryAssignment:
    """
    Put an article into the most similar recent story, or start a new one.

    Candidates are stories whose newest article is within STORY_WINDOW_HOURS
    of this article. The article joins the candidate whose centroid is most
    similar if that similarity is at least STORY_SIMILARITY_THRESHOLD.

    Idempotent: an article that already belongs to a story is left alone, so
    Kafka redeliveries and republished articles don't move or double-count it.
    Does not commit; the caller owns the transaction.
    """
    existing = db.query(StoryArticle).filter(StoryArticle.article_id == article.id).first()
    if existing is not None:
        return StoryAssignment(existing.story_id, existing.similarity, "existing")

    if article.embedding is None:
        raise ValueError(f"Article id={article.id} has no embedding")

    # Normalize so the stored centroid is a mean of unit vectors, which keeps
    # every article's vote equal regardless of its embedding's length
    embedding = np.asarray(article.embedding, dtype=np.float64)
    norm = np.linalg.norm(embedding)
    if norm == 0:
        raise ValueError(f"Article id={article.id} has a zero embedding")
    embedding = embedding / norm

    article_time = article.published_at or article.created_at
    window = timedelta(hours=STORY_WINDOW_HOURS)

    # Newest article time per story, computed from members so the stories
    # table doesn't need its own column for it
    newest = (
        db.query(
            StoryArticle.story_id.label("story_id"),
            func.max(func.coalesce(Article.published_at, Article.created_at)).label("newest_at"),
        )
        .join(Article, Article.id == StoryArticle.article_id)
        .group_by(StoryArticle.story_id)
        .subquery()
    )

    # Cosine distance ignores vector length, so comparing against the
    # unnormalized mean is the same as comparing against its normalized form
    distance = Story.centroid.cosine_distance(embedding.tolist())
    best = (
        db.query(Story, distance.label("distance"))
        .join(newest, newest.c.story_id == Story.id)
        .filter(Story.centroid.isnot(None))
        .filter(newest.c.newest_at >= article_time - window)
        .filter(newest.c.newest_at <= article_time + window)
        .order_by(distance, Story.id)
        .first()
    )

    if best is not None and 1.0 - best.distance >= STORY_SIMILARITY_THRESHOLD:
        story, similarity = best.Story, 1.0 - float(best.distance)
        count = story.article_count
        old_mean = np.asarray(story.centroid, dtype=np.float64)
        story.centroid = ((old_mean * count + embedding) / (count + 1)).tolist()
        story.article_count = count + 1
        story.updated_at = utcnow()
        db.add(StoryArticle(story_id=story.id, article_id=article.id, similarity=similarity))
        db.flush()
        return StoryAssignment(story.id, similarity, "joined")

    story = Story(title=article.title, centroid=embedding.tolist(), article_count=1)
    db.add(story)
    db.flush()
    db.add(StoryArticle(story_id=story.id, article_id=article.id, similarity=None))
    db.flush()
    return StoryAssignment(story.id, None, "created")
