import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Load credentials from .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set. Please configure your .env file.")

# Create the engine — pool_pre_ping ensures dead connections are recycled.
#
# Pool sizing: supports up to pool_size + max_overflow = 20 concurrent sessions.
# This comfortably covers 8 parallel Prefect scraper tasks + Prefect's own
# internal DB operations without hitting SQLAlchemy's QueuePool limit.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False,       # Set True to log all SQL (useful for debugging)
    pool_size=15,     # Persistent connections kept alive in the pool
    max_overflow=5,   # Extra connections allowed under burst load (total = 20)
    pool_recycle=3600,# Recycle connections after 1h to prevent stale sockets
    pool_timeout=30,  # Raise immediately after 30s instead of hanging forever
)

# Session factory — use this to get a DB session
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_session() -> Session:
    """
    Returns a new SQLAlchemy session.
    Usage:
        session = get_session()
        try:
            # ... do work ...
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    """
    return SessionLocal()


def init_db():
    """
    Creates all tables if they don't exist yet.
    Called once on startup. Alembic handles migrations in production.
    """
    from database.models import Base
    Base.metadata.create_all(bind=engine)
