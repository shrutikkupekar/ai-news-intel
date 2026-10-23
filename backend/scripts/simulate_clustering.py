import argparse
import logging
from datetime import timedelta

import numpy as np
from sqlalchemy import text

from app.database import SessionLocal
from app.models import Article, Source

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("simulate_clustering")

DEFAULT_THRESHOLDS = [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8]
STORY_WINDOW_HOURS = 24


def load_articles():
    """Load embedded, dated articles in publish order, with L2-normalized embeddings."""
    db = SessionLocal()
    try:
        # Guarantee this script can't write anything, even by accident
        db.execute(text("SET TRANSACTION READ ONLY"))

        rows = (
            db.query(Article, Source)
            .join(Source, Article.source_id == Source.id)
            .filter(Article.published_at.isnot(None))
            .filter(Article.embedding.isnot(None))
            .order_by(Article.published_at, Article.id)
            .all()
        )
        articles = [
            {
                "id": article.id,
                "title": article.title,
                "source": source.name,
                "published_at": article.published_at,
            }
            for article, source in rows
        ]
        embeddings = np.array(
            [np.asarray(article.embedding, dtype=np.float32) for article, _ in rows]
        ).reshape(len(rows), -1)
    finally:
        db.rollback()
        db.close()

    # L2-normalize so a dot product is the cosine similarity
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return articles, embeddings / norms


def simulate(articles, embeddings, threshold, max_age_hours=None):
    """
    Incrementally cluster articles in publish order.

    Each article is compared to the centroid of every story whose latest
    article is at most 24 hours older than it; it joins the best match at or
    above the threshold, otherwise it starts a new story. With max_age_hours,
    a story also stops accepting articles once its newest article is more
    than that many hours after its first.
    """
    window = timedelta(hours=STORY_WINDOW_HOURS)
    max_age = None if max_age_hours is None else timedelta(hours=max_age_hours)
    stories = []

    for i, article in enumerate(articles):
        best_story, best_sim = None, -1.0
        for story in stories:
            if article["published_at"] - story["latest"] > window:
                continue
            if max_age is not None and story["latest"] - story["first"] > max_age:
                continue
            centroid = story["sum"] / np.linalg.norm(story["sum"])
            sim = float(centroid @ embeddings[i])
            if sim > best_sim:
                best_story, best_sim = story, sim

        if best_story is not None and best_sim >= threshold:
            best_story["members"].append((article, best_sim))
            best_story["sum"] = best_story["sum"] + embeddings[i]
            best_story["latest"] = article["published_at"]
        else:
            stories.append(
                {
                    "id": len(stories),
                    "members": [(article, None)],
                    "sum": embeddings[i].copy(),
                    "first": article["published_at"],
                    "latest": article["published_at"],
                }
            )

    return stories


def format_sim(sim) -> str:
    return "  seed" if sim is None else f"{sim:.3f}"


def print_summary(articles, embeddings, thresholds, max_age_hours=None) -> None:
    if max_age_hours is not None:
        print(f"\nMax story age: {max_age_hours} hours")
    print(f"\n{'threshold':>9}  {'stories':>7}  {'size 1':>6}  {'size 2+':>7}  {'largest':>7}")
    for threshold in thresholds:
        stories = simulate(articles, embeddings, threshold, max_age_hours)
        sizes = [len(story["members"]) for story in stories]
        singles = sum(1 for size in sizes if size == 1)
        print(
            f"{threshold:>9.2f}  {len(stories):>7}  {singles:>6}  "
            f"{len(stories) - singles:>7}  {max(sizes, default=0):>7}"
        )


def print_stories(articles, embeddings, threshold, max_age_hours=None, min_size=2) -> None:
    stories = simulate(articles, embeddings, threshold, max_age_hours)
    multi = [story for story in stories if len(story["members"]) >= min_size]
    multi.sort(key=lambda story: len(story["members"]), reverse=True)

    age_text = "" if max_age_hours is None else f", max age {max_age_hours}h"
    print(f"\nThreshold {threshold}{age_text}: {len(multi)} stories with {min_size}+ articles\n")
    for rank, story in enumerate(multi, start=1):
        print(f"#{rank}  ({len(story['members'])} articles)")
        for article, sim in story["members"]:
            print(f"  {format_sim(sim)}  [{article['source']}] {article['title']}")
        print()


def print_comparison(articles, embeddings, low, high, max_age_hours=None) -> None:
    """List every 2+ story at the low threshold whose articles don't all stay together at the high one."""
    low_stories = simulate(articles, embeddings, low, max_age_hours)
    high_stories = simulate(articles, embeddings, high, max_age_hours)

    # Map each article to its story and joining similarity at the high threshold
    high_by_article = {}
    for story in high_stories:
        for article, sim in story["members"]:
            high_by_article[article["id"]] = (story, sim)

    changed = []
    for story in low_stories:
        if len(story["members"]) < 2:
            continue
        groups = {}
        for article, _ in story["members"]:
            groups.setdefault(high_by_article[article["id"]][0]["id"], []).append(article["id"])
        if len(groups) > 1:
            multi_groups = sum(1 for ids in groups.values() if len(ids) >= 2)
            kind = "split" if multi_groups >= 2 else "shrunk"
            changed.append((story, kind, len(groups)))

    changed.sort(key=lambda item: len(item[0]["members"]), reverse=True)
    print(
        f"\n{len(changed)} stories with 2+ articles at {low} are split or shrunk at {high}\n"
    )
    for story, kind, group_count in changed:
        print(f"Story {story['id']} at {low}: {len(story['members'])} articles, {kind} into {group_count} stories at {high}")
        print(f"  {'@' + str(low):>6}  {'@' + str(high):>6}  {'story':>5}")
        for article, low_sim in story["members"]:
            high_story, high_sim = high_by_article[article["id"]]
            size = len(high_story["members"])
            print(
                f"  {format_sim(low_sim):>6}  {format_sim(high_sim):>6}  {high_story['id']:>5}"
                f"  (size {size})  [{article['source']}] {article['title']}"
            )
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only simulation of incremental story clustering")
    parser.add_argument("threshold", nargs="?", type=float, help="cosine threshold to inspect")
    parser.add_argument(
        "--compare", nargs=2, type=float, metavar=("LOW", "HIGH"),
        help="list 2+ stories at LOW that are split or shrunk at HIGH",
    )
    parser.add_argument(
        "--max-age-hours", type=float,
        help="stop a story accepting articles once its newest is this many hours after its first",
    )
    parser.add_argument(
        "--thresholds", nargs="+", type=float, default=DEFAULT_THRESHOLDS,
        help="thresholds for the summary table",
    )
    parser.add_argument("--min-size", type=int, default=2, help="smallest story to list with a threshold")
    args = parser.parse_args()

    articles, embeddings = load_articles()
    logger.info(f"Loaded {len(articles)} articles with embeddings and published_at timestamps")

    if args.compare:
        print_comparison(articles, embeddings, *args.compare, args.max_age_hours)
    elif args.threshold is None:
        print_summary(articles, embeddings, args.thresholds, args.max_age_hours)
    else:
        print_stories(articles, embeddings, args.threshold, args.max_age_hours, args.min_size)


if __name__ == "__main__":
    main()
