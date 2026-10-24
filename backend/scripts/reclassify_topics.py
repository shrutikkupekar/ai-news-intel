import argparse
import logging
import random
from collections import Counter

from sqlalchemy import text

from app.database import SessionLocal
from app.models import Article
from app.topics import classify_article_topic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reclassify_topics")

SAMPLE_SIZE = 20
SAMPLE_SEED = 42


def main() -> None:
    parser = argparse.ArgumentParser(description="Reclassify every article's topic")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="read-only: print the before/after table and sample changes without writing",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.dry_run:
            # Guarantee a dry run can't write anything, even by accident
            db.execute(text("SET TRANSACTION READ ONLY"))

        articles = db.query(Article).order_by(Article.id).all()
        logger.info(f"Loaded {len(articles)} articles")

        changes = []
        before, after = Counter(), Counter()
        for article in articles:
            # Same text the entity processor classifies
            new_topic = classify_article_topic(f"{article.title}\n{article.content or ''}")
            before[article.topic or "(none)"] += 1
            after[new_topic] += 1
            if new_topic != article.topic:
                changes.append((article, article.topic, new_topic))
                if not args.dry_run:
                    article.topic = new_topic

        topics = sorted(set(before) | set(after), key=lambda t: (-after[t], t))
        print(f"\n{'topic':<26}  {'before':>6}  {'after':>6}  {'change':>6}")
        for topic in topics:
            print(f"{topic:<26}  {before[topic]:>6}  {after[topic]:>6}  {after[topic] - before[topic]:>+6}")
        print(f"{'total':<26}  {sum(before.values()):>6}  {sum(after.values()):>6}")
        print(f"\nArticles whose topic changed: {len(changes)} of {len(articles)}")

        if args.dry_run:
            sample = random.Random(SAMPLE_SEED).sample(changes, min(SAMPLE_SIZE, len(changes)))
            print(f"\n{len(sample)} random changed articles (seed {SAMPLE_SEED}):\n")
            for article, old_topic, new_topic in sorted(sample, key=lambda c: c[0].id):
                print(f"  {article.id:>5}  {old_topic or '(none)'} -> {new_topic}")
                print(f"         {article.title}")
            logger.info("Dry run: nothing written")
        else:
            db.commit()
            logger.info(f"Updated {len(changes)} articles")
    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
