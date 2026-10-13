import logging
from datetime import timedelta

import numpy as np
from rapidfuzz import fuzz
from sqlalchemy import text

from app.database import SessionLocal
from app.models import Article, Source

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("analyze_semantic_similarity")

COSINE_THRESHOLD = 0.5
TIME_WINDOW_HOURS = 6


def analyze_semantic_similarity() -> None:
    """Analyze embedding cosine similarity for articles published within 6-hour windows."""
    db = SessionLocal()
    try:
        # Guarantee this script can't write anything, even by accident
        db.execute(text("SET TRANSACTION READ ONLY"))

        # Fetch all embedded articles ordered by published_at
        articles = (
            db.query(Article, Source)
            .join(Source, Article.source_id == Source.id)
            .filter(Article.published_at.isnot(None))
            .filter(Article.embedding.isnot(None))
            .order_by(Article.published_at)
            .all()
        )
        logger.info(f"Loaded {len(articles)} articles with embeddings and published_at timestamps")

        if len(articles) < 2:
            print("Not enough articles to compare")
            return

        # L2-normalize so a dot product is the cosine similarity
        embeddings = np.array(
            [np.asarray(article.embedding, dtype=np.float32) for article, _ in articles]
        )
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        embeddings = embeddings / norms

        window = timedelta(hours=TIME_WINDOW_HOURS)
        matches = []

        for i, (article_i, source_i) in enumerate(articles):
            # Articles are sorted, so only look forward (each pair once) and
            # stop at the first article outside the 6-hour window
            end = i + 1
            while end < len(articles) and articles[end][0].published_at - article_i.published_at <= window:
                end += 1
            if end == i + 1:
                continue

            similarities = embeddings[i + 1 : end] @ embeddings[i]

            for offset in np.nonzero(similarities >= COSINE_THRESHOLD)[0]:
                article_j, source_j = articles[i + 1 + offset]
                matches.append(
                    {
                        "cosine": float(similarities[offset]),
                        "title_score": fuzz.token_sort_ratio(article_i.title, article_j.title),
                        "title_a": article_i.title,
                        "source_a": source_i.name,
                        "title_b": article_j.title,
                        "source_b": source_j.name,
                    }
                )

        # Sort by cosine similarity descending
        matches.sort(key=lambda x: x["cosine"], reverse=True)

        # Print results
        if matches:
            print(f"\nFound {len(matches)} article pairs with cosine similarity >= {COSINE_THRESHOLD}:\n")
            for match in matches:
                print(f"Cosine: {match['cosine']:.3f}  Title score: {match['title_score']:.1f}")
                print(f"  [{match['source_a']}] {match['title_a']}")
                print(f"  [{match['source_b']}] {match['title_b']}")
                print()
        else:
            print(f"No article pairs found with cosine similarity >= {COSINE_THRESHOLD}")
    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    analyze_semantic_similarity()
