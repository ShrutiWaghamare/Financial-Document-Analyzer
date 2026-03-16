"""
SQLAlchemy database for storing analysis job metadata and results.
Uses SQLite by default (no extra setup needed).
Set DATABASE_URL env var for PostgreSQL in production.
"""
import os

from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime

# SQLite by default — no install needed for development
# For PostgreSQL: DATABASE_URL=postgresql://user:password@localhost/financial_db
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///./financial.db",
)

# SQLite requires check_same_thread=False when used with FastAPI threading
_connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    _connect_args["check_same_thread"] = False

engine       = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base         = declarative_base()


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    job_id      = Column(String(36),  primary_key=True, index=True)
    status      = Column(String(20),  default="pending")   # pending | processing | done | failed
    query       = Column(Text,        nullable=True)
    filename    = Column(String(255), nullable=True)
    result      = Column(Text,        nullable=True)        # filled when status == done
    error       = Column(Text,        nullable=True)        # filled when status == failed
    output_file = Column(String(512), nullable=True)        # path to outputs/{job_id}.txt
    created_at  = Column(DateTime,    default=datetime.utcnow)
    updated_at  = Column(DateTime,    default=datetime.utcnow, onupdate=datetime.utcnow)


def init_db():
    """Create all tables if they don't exist. Called on FastAPI startup."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency: yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()