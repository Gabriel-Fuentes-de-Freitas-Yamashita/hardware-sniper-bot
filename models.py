from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from database import Base

class Feed(Base):
    __tablename__ = "feeds"
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(255), unique=True, nullable=False)
    name = Column(String(100))

class NewsItem(Base):
    __tablename__ = "news"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255))
    link = Column(String(500), unique=True) # Link único para evitar notícias duplicadas
    published_at = Column(DateTime(timezone=True), server_default=func.now())
    feed_id = Column(Integer, ForeignKey("feeds.id"))