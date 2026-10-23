from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    url: str


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    url: str
    published_at: Optional[datetime] = None
    created_at: datetime
    source: SourceOut


class StorySummaryOut(BaseModel):
    id: int
    title: str
    article_count: int
    source_count: int
    source_names: list[str]
    first_article_at: datetime
    latest_article_at: datetime
    topic: str


class StoryListOut(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[StorySummaryOut]


class StoryArticleOut(BaseModel):
    id: int
    title: str
    url: str
    source_name: str
    published_at: Optional[datetime] = None
    created_at: datetime
    similarity: Optional[float] = None


class StoryDetailOut(StorySummaryOut):
    articles: list[StoryArticleOut]
