import argparse
import logging

from sqlalchemy import func

from app.clustering import STORY_SIMILARITY_THRESHOLD, assign_to_story
from app.database import SessionLocal
from app.models import Article, Source, Story, StoryArticle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backfill_stories")


def load_articles(db):
    """All embedded articles in time order, using created_at when published_at is missing."""
    return (
        db.query(Article)
        .filter(Article.embedding.isnot(None))
        .order_by(func.coalesce(Article.published_at, Article.created_at), Article.id)
        .all()
    )


def assign_all(db, articles, commit: bool) -> dict:
    counts = {"joined": 0, "created": 0, "existing": 0}
    for article in articles:
        assignment = assign_to_story(db, article)
        counts[assignment.status] += 1
        if commit:
            db.commit()
    return counts


def print_report(db) -> None:
    sizes = [count for (count,) in db.query(Story.article_count).all()]
    singles = sum(1 for size in sizes if size == 1)
    print(f"\n{'threshold':>9}  {'stories':>7}  {'size 1':>6}  {'size 2+':>7}  {'largest':>7}")
    print(
        f"{STORY_SIMILARITY_THRESHOLD:>9.2f}  {len(sizes):>7}  {singles:>6}  "
        f"{len(sizes) - singles:>7}  {max(sizes, default=0):>7}"
    )

    multi = (
        db.query(Story)
        .filter(Story.article_count >= 2)
        .order_by(Story.article_count.desc(), Story.id)
        .all()
    )
    print(f"\nThreshold {STORY_SIMILARITY_THRESHOLD}: {len(multi)} stories with 2+ articles\n")
    for rank, story in enumerate(multi, start=1):
        members = (
            db.query(StoryArticle, Article, Source)
            .join(Article, Article.id == StoryArticle.article_id)
            .join(Source, Source.id == Article.source_id)
            .filter(StoryArticle.story_id == story.id)
            .order_by(StoryArticle.id)
            .all()
        )
        print(f"#{rank}  ({story.article_count} articles)")
        for story_article, article, source in members:
            sim = story_article.similarity
            sim_text = "  seed" if sim is None else f"{sim:.3f}"
            print(f"  {sim_text}  [{source.name}] {article.title}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Assign every embedded article to a story")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="run everything in one transaction, print the result, then roll back",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        articles = load_articles(db)
        logger.info(f"Loaded {len(articles)} articles with embeddings")

        counts = assign_all(db, articles, commit=not args.dry_run)
        logger.info(
            "Joined %d, created %d, already assigned %d",
            counts["joined"],
            counts["created"],
            counts["existing"],
        )

        if args.dry_run:
            db.flush()
            print_report(db)
            logger.info("Dry run: rolling back")
    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
