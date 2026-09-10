import logging
from datetime import timedelta

from rapidfuzz import fuzz
from sqlalchemy import func

from app.database import SessionLocal
from app.models import Article, Source

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("analyze_title_similarity")

SIMILARITY_THRESHOLD = 40
TIME_WINDOW_HOURS = 6


def analyze_title_similarity() -> None:
    """Analyze title similarity for articles published within 6-hour windows."""
    db = SessionLocal()
    try:
        # Fetch all articles ordered by published_at
        articles = (
            db.query(Article, Source)
            .join(Source, Article.source_id == Source.id)
            .filter(Article.published_at.isnot(None))
            .order_by(Article.published_at)
            .all()
        )
        logger.info(f"Loaded {len(articles)} articles with published_at timestamps")

        # Collect all similarity matches
        matches = []

        for i, (article_i, source_i) in enumerate(articles):
            # Compare against all articles within 6 hours
            for article_j, source_j in articles[i + 1 :]:
                # Check if within 6-hour window
                time_diff = article_j.published_at - article_i.published_at
                if time_diff > timedelta(hours=TIME_WINDOW_HOURS):
                    # Articles are too far apart; stop checking
                    break

                # Compute similarity score
                score = fuzz.token_sort_ratio(
                    article_i.title, article_j.title, score_cutoff=0
                )

                if score > SIMILARITY_THRESHOLD:
                    matches.append(
                        {
                            "score": score,
                            "title_a": article_i.title,
                            "source_a": source_i.name,
                            "title_b": article_j.title,
                            "source_b": source_j.name,
                            "published_at_a": article_i.published_at,
                            "published_at_b": article_j.published_at,
                        }
                    )

        # Sort by score descending
        matches.sort(key=lambda x: x["score"], reverse=True)

        # Print results
        if matches:
            print(f"\nFound {len(matches)} title pairs with similarity > {SIMILARITY_THRESHOLD}:\n")
            for match in matches:
                print(
                    f"Score: {match['score']:.1f}"
                )
                print(f"  [{match['source_a']}] {match['title_a']}")
                print(f"  [{match['source_b']}] {match['title_b']}")
                print()
        else:
            print(f"No title pairs found with similarity > {SIMILARITY_THRESHOLD}")
    finally:
        db.close()


if __name__ == "__main__":
    analyze_title_similarity()
