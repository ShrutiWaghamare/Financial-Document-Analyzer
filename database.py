"""
SQLAlchemy database for storing analysis job metadata and results.
Uses SQLite by default (no extra setup). Set DATABASE_URL for PostgreSQL in production.
"""
import os

from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime

# SQLite by default; use DATABASE_URL for PostgreSQL (e.g. postgresql://user:pass@localhost/financial_db)
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///./financial.db",
)

# SQLite needs check_same_thread=False when used with FastAPI
_connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    _connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    job_id = Column(String(36), primary_key=True, index=True)
    status = Column(String(20), default="pending")  # pending | processing | done | failed
    query = Column(Text, nullable=True)
    filename = Column(String(255), nullable=True)
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    output_file = Column(String(512), nullable=True)  # path in outputs/ folder
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency: yield a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
