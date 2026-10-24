# ai-news-intel

A news pipeline: RSS feeds are fetched, sent through Kafka, enriched (entities,
topics, embeddings), grouped into stories, and shown in a Next.js frontend.

## Where the repo lives
- The real repo is `~/dev/ai-news-intel`. Always work there.
- The copy in `~/Desktop/ai-news-intel` is an obsolete leftover that iCloud
  corrupts. Never read, edit or run anything from it.

## Everything runs in Docker
- All code runs in containers (postgres, kafka, api, worker, processor, web).
- Never run `pip install` or `npm install` on the host. Dependencies belong in
  `backend/requirements.txt` or `frontend/package.json` and get installed by
  the image build.
- Run backend scripts inside the api container:
  `docker compose exec api python -m scripts.<name>`
- Images are built with the classic builder (`DOCKER_BUILDKIT=0`), because
  BuildKit hung on `npm install` on this machine.
- Kafka has no volume. Recreating its container wipes all topics and any
  messages not yet consumed.

## Database
- Schema changes go through Alembic only:
  1. `docker compose exec api alembic revision --autogenerate -m "..."`
  2. Read the generated file in `backend/alembic/versions/` and fix it if needed.
  3. Only then apply it with `docker compose exec api alembic upgrade head`.
- `Base.metadata.create_all` was removed on purpose. Don't add it back.
- Take a database backup before running any script that changes data.

## Scripts that change data
- `backfill_stories`, `reclassify_topics` and `merge_duplicate_sources` have a
  `--dry-run` flag. Always run with `--dry-run` first, show the result, and
  only run for real when the owner says so (after a backup).
- `clean_existing_articles` has no dry-run mode. Don't pass it a `--dry-run`
  flag. Ask the owner before running it.

## Key tunables (constants in the code)
- `TITLE_DUPLICATE_THRESHOLD` in `backend/app/consumers/raw_consumer.py`
- `STORY_SIMILARITY_THRESHOLD` and `STORY_WINDOW_HOURS` in `backend/app/clustering.py`
- Topic keywords in `TOPIC_TAXONOMY` in `backend/app/topics.py`
  (test with `docker compose exec api python -m scripts.test_topic_classifier`)

## Git
- Never commit or push unless asked.

## How to work with the owner
- The owner is learning. Explain what you are doing and why in plain language,
  before and after each step, and avoid unexplained jargon.
