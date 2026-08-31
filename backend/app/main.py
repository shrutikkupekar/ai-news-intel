import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.ingestion.rss_fetcher import ingest_all
from app.api import articles

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

scheduler = BackgroundScheduler()


def scheduled_ingest():
    """Wrapper so the scheduler owns its own DB session (not request-scoped)."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        ingest_all(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Phase 1: create_all is fine. Once the schema stabilizes (Phase 2+),
    # switch to Alembic migrations so schema changes are tracked and reversible.
    Base.metadata.create_all(bind=engine)

    scheduler.add_job(scheduled_ingest, "interval", minutes=10, id="rss_ingest")
    scheduler.start()
    logger.info("scheduler started: ingesting every 10 minutes")

    yield

    scheduler.shutdown()


app = FastAPI(title="AI News Intelligence Platform", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(articles.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/ingest/run")
def trigger_ingest(db: Session = Depends(get_db)):
    """Manually trigger ingestion — useful for testing without waiting 10 minutes."""
    results = ingest_all(db)
    return {"results": results}
