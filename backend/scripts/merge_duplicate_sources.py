import argparse
import logging

from sqlalchemy import func

from app.database import SessionLocal
from app.ingestion.rss_fetcher import SEED_SOURCES
from app.models import Article, Source

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("merge_duplicate_sources")


def counts_by_name(db) -> dict:
    """Map each source name to (source rows, articles)."""
    rows = (
        db.query(
            Source.name,
            func.count(func.distinct(Source.id)),
            func.count(Article.id),
        )
        .outerjoin(Article, Article.source_id == Source.id)
        .group_by(Source.name)
        .all()
    )
    return {name: (source_rows, articles) for name, source_rows, articles in rows}


def merge_sources(db) -> None:
    """
    Collapse each source name onto its lowest-id row.

    Articles are repointed to the kept row, the other rows are deleted, and
    the kept row's url is set to the feed URL for seed sources. Sources left
    with no articles at all are then deleted.
    """
    feed_urls = {src["name"]: src["url"] for src in SEED_SOURCES}
    names = [name for (name,) in db.query(Source.name).distinct().order_by(Source.name)]

    for name in names:
        ids = [id_ for (id_,) in db.query(Source.id).filter(Source.name == name).order_by(Source.id)]
        keep_id, other_ids = ids[0], ids[1:]

        if other_ids:
            moved = (
                db.query(Article)
                .filter(Article.source_id.in_(other_ids))
                .update({Article.source_id: keep_id}, synchronize_session=False)
            )
            db.query(Source).filter(Source.id.in_(other_ids)).delete(synchronize_session=False)
            logger.info(
                "%s: kept source id=%d, moved %d articles, deleted %d rows",
                name, keep_id, moved, len(other_ids),
            )

        # Deleting the other rows first means the feed URL can't collide with
        # one of them on the unique url column
        if name in feed_urls:
            db.query(Source).filter(Source.id == keep_id).update(
                {Source.url: feed_urls[name]}, synchronize_session=False
            )

    has_articles = db.query(Article.source_id).filter(Article.source_id.isnot(None)).distinct()
    deleted = (
        db.query(Source)
        .filter(Source.id.notin_(has_articles))
        .delete(synchronize_session=False)
    )
    logger.info("Deleted %d sources with no articles", deleted)


def print_counts(before: dict, after: dict, total_before: int, total_after: int) -> None:
    print(f"\n{'name':<26}  {'rows before':>11}  {'rows after':>10}  {'articles before':>15}  {'articles after':>14}")
    for name in sorted(set(before) | set(after)):
        rows_before, articles_before = before.get(name, (0, 0))
        rows_after, articles_after = after.get(name, (0, 0))
        print(
            f"{name:<26}  {rows_before:>11}  {rows_after:>10}  "
            f"{articles_before:>15}  {articles_after:>14}"
        )
    print(f"\nTotal articles: {total_before} before, {total_after} after")


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge duplicate source rows by name")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="run everything in one transaction, print before/after counts, then roll back",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        before = counts_by_name(db)
        total_before = db.query(Article).count()

        merge_sources(db)
        db.flush()

        after = counts_by_name(db)
        total_after = db.query(Article).count()
        print_counts(before, after, total_before, total_after)

        if args.dry_run:
            print("\nKept rows:")
            for source in db.query(Source).order_by(Source.id):
                print(f"  id={source.id}  {source.name}  {source.url}")
            logger.info("Dry run: rolling back")
            db.rollback()
        else:
            db.commit()
    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
