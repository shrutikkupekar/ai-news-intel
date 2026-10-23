from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Article, Source, Story, StoryArticle
from app.schemas import StoryArticleOut, StoryDetailOut, StoryListOut, StorySummaryOut

router = APIRouter(prefix="/api/stories", tags=["stories"])

MAX_LIMIT = 100


def story_summaries(db: Session):
    """
    One row per story with its aggregates, computed from its member articles.

    Topic is the most common topic other than "Uncategorized"; mode() skips
    NULLs, so NULLIF drops "Uncategorized" from the vote.
    """
    article_time = func.coalesce(Article.published_at, Article.created_at)
    article_count = func.count(Article.id)
    latest_article_at = func.max(article_time)
    return (
        db.query(
            Story.id.label("id"),
            Story.title.label("title"),
            article_count.label("article_count"),
            func.count(distinct(Article.source_id)).label("source_count"),
            func.array_agg(distinct(Source.name)).label("source_names"),
            func.min(article_time).label("first_article_at"),
            latest_article_at.label("latest_article_at"),
            func.coalesce(
                func.mode().within_group(func.nullif(Article.topic, "Uncategorized")),
                "Uncategorized",
            ).label("topic"),
        )
        .join(StoryArticle, StoryArticle.story_id == Story.id)
        .join(Article, Article.id == StoryArticle.article_id)
        .join(Source, Source.id == Article.source_id)
        .group_by(Story.id)
    ), article_count, latest_article_at


def to_summary(row) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "article_count": row.article_count,
        "source_count": row.source_count,
        "source_names": list(row.source_names or []),
        "first_article_at": row.first_article_at,
        "latest_article_at": row.latest_article_at,
        "topic": row.topic,
    }


@router.get("", response_model=StoryListOut)
def list_stories(
    limit: int = Query(20, ge=1, description=f"Page size, capped at {MAX_LIMIT}"),
    offset: int = Query(0, ge=0),
    min_articles: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    limit = min(limit, MAX_LIMIT)
    query, article_count, latest_article_at = story_summaries(db)

    # count(*) OVER () gives the total across all pages in the same query
    rows = (
        query.add_columns(func.count().over().label("total"))
        .having(article_count >= min_articles)
        .order_by(latest_article_at.desc(), Story.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    if rows:
        total = rows[0].total
    else:
        # Past the last page the window has no rows to report on
        total = query.having(article_count >= min_articles).count()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [to_summary(row) for row in rows],
    }


@router.get("/{story_id}", response_model=StoryDetailOut)
def get_story(story_id: int, db: Session = Depends(get_db)):
    query, _, _ = story_summaries(db)
    row = query.filter(Story.id == story_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Story {story_id} not found")

    articles = (
        db.query(Article, Source.name, StoryArticle.similarity)
        .join(StoryArticle, StoryArticle.article_id == Article.id)
        .join(Source, Source.id == Article.source_id)
        .filter(StoryArticle.story_id == story_id)
        .order_by(func.coalesce(Article.published_at, Article.created_at), Article.id)
        .all()
    )

    return {
        **to_summary(row),
        "articles": [
            StoryArticleOut(
                id=article.id,
                title=article.title,
                url=article.url,
                source_name=source_name,
                published_at=article.published_at,
                created_at=article.created_at,
                similarity=similarity,
            )
            for article, source_name, similarity in articles
        ],
    }
