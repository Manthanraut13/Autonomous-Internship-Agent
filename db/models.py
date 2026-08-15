"""
db/models.py
------------
SQLAlchemy ORM models for the Autonomous Internship Agent.

Models:
    Job         - Internship listings scraped from job platforms.
    PipelineRun - Execution history of pipeline runs (CLI and Dashboard).

Usage:
    from db.models import Base, Job, PipelineRun
    from db.database import engine
    Base.metadata.create_all(bind=engine)
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base

# Shared declarative base
Base = declarative_base()
Base.__allow_unmapped__ = True


# =========================================================================== #
# Job Model                                                                     #
# =========================================================================== #

class Job(Base):
    """
    Represents a single internship / job listing scraped from an external
    platform (Remotive, Arbeitnow, Himalayas, LinkedIn, etc.).

    Attributes:
        id              : Auto-incremented primary key.
        job_id          : Platform-specific unique job identifier string.
        title           : Job / internship title.
        company         : Name of the hiring company.
        location        : Job location (city/remote).
        description     : Full job description text.
        link            : Direct URL to the job posting.
        apply_url       : Direct application URL.
        source          : Platform name (e.g. 'remotive', 'arbeitnow').
        posted_at       : When the job was originally posted.
        scraped_at      : UTC timestamp when this record was created.
        updated_at      : UTC timestamp of last update.
        match_score     : LLM-assigned relevance score (0.0 – 100.0).
        match_reasoning : LLM explanation for the score.
        status          : 'saved' (Inbox) | 'applied' | 'rejected' (Not Applied)
    """

    __tablename__ = "jobs"

    __table_args__ = (
        UniqueConstraint("job_id", "source", name="uq_job_id_source"),
    )

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Platform-specific identifier
    job_id = Column(String(255), nullable=False, index=True)

    # Core job details
    title = Column(String(255), nullable=False)
    company = Column(String(255), nullable=False, index=True)
    location = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    link = Column(String(1000), nullable=False)
    apply_url = Column(String(1000), nullable=True)
    source = Column(String(50), nullable=False, index=True)

    # Timestamps
    posted_at = Column(DateTime, nullable=True)
    scraped_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Matching
    match_score = Column(Float, nullable=True)
    match_reasoning = Column(Text, nullable=True)

    # Workflow lifecycle status: 'saved' (Inbox/New), 'applied', 'rejected' (Not Applied)
    status = Column(
        String(50),
        nullable=False,
        default="saved",
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<Job(id={self.id}, title='{self.title}', "
            f"company='{self.company}', status='{self.status}', "
            f"match_score={self.match_score})>"
        )


# =========================================================================== #
# PipelineRun Model                                                            #
# =========================================================================== #

class PipelineRun(Base):
    """
    Logs every execution of the pipeline (whether triggered from CLI or Dashboard).
    Used to track accurate stats on successfully emailed reports.
    """

    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(50), default="running", nullable=False)  # 'success', 'failed', 'running'
    jobs_found = Column(Integer, default=0)
    jobs_matched = Column(Integer, default=0)
    email_sent = Column(Boolean, default=False)
    whatsapp_sent = Column(Boolean, default=False)
    csv_path = Column(String(500), nullable=True)
    source = Column(String(50), default="cli")  # 'cli' | 'dashboard'

    def __repr__(self) -> str:
        return (
            f"<PipelineRun(id={self.id}, status='{self.status}', "
            f"jobs_matched={self.jobs_matched}, email_sent={self.email_sent})>"
        )
