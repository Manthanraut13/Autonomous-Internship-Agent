"""
db/database.py
--------------
Database engine, session factory, table initialisation, and FastAPI
dependency injection for the Autonomous Internship Agent.

Usage:
    # Initialise tables (run once on startup)
    from db.database import init_db
    init_db()

    # Use in FastAPI endpoints via Depends
    from db.database import get_db
    from sqlalchemy.orm import Session
    from fastapi import Depends

    @app.get("/jobs")
    def list_jobs(db: Session = Depends(get_db)):
        return db.query(Job).all()

    # Use as a context manager in non-FastAPI code
    from db.database import SessionLocal
    with SessionLocal() as db:
        jobs = db.query(Job).all()
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from config.settings import settings
from db.models import Base

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Engine                                                                       #
# --------------------------------------------------------------------------- #

# Connection pool tuning — safe defaults for a single-process agent
_POOL_KWARGS: dict = {}

if settings.database_url.startswith("postgresql"):
    # PostgreSQL: use a small persistent connection pool
    _POOL_KWARGS = {
        "pool_size": 5,          # keep 5 connections open
        "max_overflow": 10,      # allow up to 10 extra on burst
        "pool_timeout": 30,      # seconds to wait for a connection
        "pool_recycle": 1800,    # recycle connections every 30 min
        "pool_pre_ping": True,   # verify connection health before use
    }
else:
    # SQLite (local / test): no connection pool needed
    _POOL_KWARGS = {
        "connect_args": {"check_same_thread": False},
    }

engine = create_engine(
    settings.database_url,
    echo=settings.debug,   # log SQL statements only in debug mode
    future=True,           # use SQLAlchemy 2.x-style queries
    **_POOL_KWARGS,
)

# Enable WAL mode for SQLite to allow concurrent reads during writes
if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

logger.info(
    f"Database engine created → "
    f"{'PostgreSQL' if 'postgresql' in settings.database_url else 'SQLite'}"
)

# --------------------------------------------------------------------------- #
# Session factory                                                              #
# --------------------------------------------------------------------------- #

SessionLocal: sessionmaker = sessionmaker(
    bind=engine,
    autocommit=False,   # explicit commits required — safer for our workflows
    autoflush=False,    # flush only on commit or explicit flush()
    expire_on_commit=False,  # keep objects usable after commit
    class_=Session,
)

# --------------------------------------------------------------------------- #
# Table initialisation                                                         #
# --------------------------------------------------------------------------- #

def init_db() -> None:
    """
    Create all database tables defined in db/models.py if they do not
    already exist.

    This function is idempotent — it is safe to call multiple times.
    Run it once on application startup or as a one-off setup command:

        python -c "from db.database import init_db; init_db()"

    Raises:
        sqlalchemy.exc.OperationalError: If the database is unreachable
            or the DATABASE_URL is misconfigured.

    Example:
        >>> init_db()
        Tables created: ['jobs', 'applications', 'whatsapp_responses']
    """
    logger.info("Initialising database tables…")
    try:
        Base.metadata.create_all(bind=engine)
        table_names = list(Base.metadata.tables.keys())
        logger.info(f"Tables created / verified: {table_names}")
        print(f"Database tables created: {table_names}")
    except Exception as exc:
        logger.error(f"Failed to create database tables: {exc}", exc_info=True)
        raise


def drop_db() -> None:
    """
    Drop ALL tables managed by this application.

    WARNING: This is destructive — all data will be lost.
    Intended for use in automated tests only.

    Example:
        >>> drop_db()   # use only in tests!
    """
    logger.warning("Dropping ALL database tables — data will be lost!")
    Base.metadata.drop_all(bind=engine)
    logger.info("All tables dropped.")


# --------------------------------------------------------------------------- #
# FastAPI dependency                                                           #
# --------------------------------------------------------------------------- #

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session and guarantees
    the session is always closed after the request — even on error.

    The session is automatically rolled back if an unhandled exception
    escapes the endpoint handler.

    Yields:
        Session: An active SQLAlchemy ORM session bound to the engine.

    Usage in a FastAPI route:
        from fastapi import Depends
        from sqlalchemy.orm import Session
        from db.database import get_db

        @router.get("/jobs")
        def list_jobs(db: Session = Depends(get_db)):
            return db.query(Job).all()
    """
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# Context manager helper (for use outside FastAPI)                            #
# --------------------------------------------------------------------------- #

@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context-manager wrapper around SessionLocal for use in scripts,
    schedulers, and background tasks where FastAPI's Depends is not
    available.

    Automatically commits on success and rolls back on exception.

    Usage:
        from db.database import get_db_context

        with get_db_context() as db:
            jobs = db.query(Job).filter(Job.status == "pending").all()

    Yields:
        Session: An active SQLAlchemy ORM session.

    Raises:
        Any exception raised inside the block after rolling back the
        session and closing it cleanly.
    """
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
        logger.debug("DB transaction committed.")
    except Exception as exc:
        db.rollback()
        logger.error(f"DB transaction rolled back due to: {exc}", exc_info=True)
        raise
    finally:
        db.close()
        logger.debug("DB session closed.")


# --------------------------------------------------------------------------- #
# Health check helper                                                          #
# --------------------------------------------------------------------------- #

def check_db_connection() -> bool:
    """
    Verify that the database is reachable by executing a lightweight
    SELECT 1 query.

    Returns:
        bool: True if the database responds correctly, False otherwise.

    Example:
        >>> check_db_connection()
        True
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database health check: OK")
        return True
    except Exception as exc:
        logger.error(f"Database health check failed: {exc}", exc_info=True)
        return False
