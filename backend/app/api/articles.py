from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Article
from app.schemas import ArticleOut

router = APIRouter(prefix="/api/articles", tags=["articles"])


@router.get("", response_model=list[ArticleOut])
def list_articles(
    q: Optional[str] = Query(None, description="Search in title"),
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    query = db.query(Article).options(joinedload(Article.source))

    if q:
        query = query.filter(or_(Article.title.ilike(f"%{q}%")))

    articles = (
        query.order_by(Article.published_at.desc().nullslast())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return articles


@router.get("/{article_id}", response_model=ArticleOut)
def get_article(article_id: int, db: Session = Depends(get_db)):
    return db.query(Article).options(joinedload(Article.source)).get(article_id)
