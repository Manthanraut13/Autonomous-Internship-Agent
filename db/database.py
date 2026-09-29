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

def _create_engine_with_fallback():
    """
    Create a SQLAlchemy engine. Falls back gracefully through connection strategies:
    1. Primary PostgreSQL URL (with 15s timeout)
    2. If port 6543 (transaction pooler) fails on SSL/network, retry with port 5432 (session pooler)
    3. If Supabase pooler fails completely, retry with direct host (db.<project_ref>.supabase.co:5432)
    4. Finally, falls back to SQLite at data/agent.db if no remote connection succeeds.
    """
    db_url = settings.database_url
    pool_kwargs: dict = {}

    if db_url.startswith("postgresql"):
        import os
        import re
        from sqlalchemy.pool import NullPool

        connect_args = {
            "connect_timeout": 15,
        }
        if "sslmode" not in db_url:
            connect_args["sslmode"] = "require"

        # Determine candidates to attempt
        urls_to_try = [db_url]

        # If using Supabase port 6543, add port 5432 as candidate
        if ":6543" in db_url:
            urls_to_try.append(db_url.replace(":6543", ":5432"))

        if "pooler.supabase.com" in db_url:
            m = re.search(r"postgres(?:ql)?://([^:]+):([^@]+)@([^:/]+)(?::\d+)?/(.+)", db_url)
            if m:
                user, password, host, db_name = m.groups()
                clean_db_name = db_name.split("?")[0]
                if "." in user:
                    direct_user = "postgres"
                    ref = user.split(".")[-1]
                    direct_url = f"postgresql://{direct_user}:{password}@db.{ref}.supabase.co:5432/{clean_db_name}?sslmode=require"
                    if direct_url not in urls_to_try:
                        urls_to_try.append(direct_url)

        for attempt_url in urls_to_try:
            current_pool_kwargs = {
                "connect_args": connect_args,
                "pool_pre_ping": True,
            }
            if ":6543" in attempt_url or "pooler.supabase.com" in attempt_url:
                current_pool_kwargs["poolclass"] = NullPool
            else:
                current_pool_kwargs.update({
                    "pool_size": 5,
                    "max_overflow": 10,
                    "pool_timeout": 15,
                    "pool_recycle": 300,
                })

            masked = attempt_url.split("@")[-1] if "@" in attempt_url else attempt_url
            try:
                logger.info(f"Connecting to database ({masked})...")
                test_engine = create_engine(attempt_url, **current_pool_kwargs)
                with test_engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                logger.info(f"Database engine created successfully → PostgreSQL ({masked})")
                return test_engine
            except Exception as e:
                logger.warning(f"Connection attempt to {masked} failed: {e}")

        logger.warning(
            "All remote PostgreSQL connections failed. Falling back to SQLite at data/agent.db."
        )
        os.makedirs("data", exist_ok=True)
        db_url = "sqlite:///data/agent.db"
        pool_kwargs = {"connect_args": {"check_same_thread": False}}
    else:
        pool_kwargs = {"connect_args": {"check_same_thread": False}}

    eng = create_engine(
        db_url,
        echo=settings.debug,
        future=True,
        **pool_kwargs,
    )
    db_type = "SQLite" if "sqlite" in db_url else "Other"
    logger.info(f"Database engine created → {db_type}")
    return eng


engine = _create_engine_with_fallback()

# Enable WAL mode for SQLite to allow concurrent reads during writes
if "sqlite" in str(engine.url):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

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
    """
    logger.info("Initialising database tables…")
    try:
        Base.metadata.create_all(bind=engine)
        table_names = list(Base.metadata.tables.keys())
        logger.info(f"Tables created / verified: {table_names}")

        # Dynamic Schema Auto-Migration: Ensure all model columns exist in physical DB
        from sqlalchemy import inspect
        inspector = inspect(engine)
        if "jobs" in inspector.get_table_names():
            existing_cols = {col["name"] for col in inspector.get_columns("jobs")}
            with engine.begin() as conn:
                if "semantic_score" not in existing_cols:
                    logger.info("Migrating: Adding missing 'semantic_score' column to jobs table...")
                    conn.execute(text("ALTER TABLE jobs ADD COLUMN semantic_score FLOAT;"))
                    print("Auto-migration applied: Added 'semantic_score' column to jobs table.")
                if "role_type" not in existing_cols:
                    logger.info("Migrating: Adding missing 'role_type' column to jobs table...")
                    conn.execute(text("ALTER TABLE jobs ADD COLUMN role_type VARCHAR(20) DEFAULT 'internship';"))
                    print("Auto-migration applied: Added 'role_type' column to jobs table.")
                if "work_mode" not in existing_cols:
                    logger.info("Migrating: Adding missing 'work_mode' column to jobs table...")
                    conn.execute(text("ALTER TABLE jobs ADD COLUMN work_mode VARCHAR(50) DEFAULT 'onsite';"))
                    print("Auto-migration applied: Added 'work_mode' column to jobs table.")
    except Exception as exc:
        logger.error(f"Database initialisation warning: {exc}")


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
