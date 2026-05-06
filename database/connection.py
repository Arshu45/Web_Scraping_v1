import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Load credentials from .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set. Please configure your .env file.")

# Create the engine — pool_pre_ping ensures dead connections are recycled
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False,  # Set to True to log all SQL statements (useful for debugging)
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
