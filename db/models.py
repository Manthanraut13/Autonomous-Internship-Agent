"""
db/models.py
------------
SQLAlchemy ORM models for the Autonomous Internship Agent.

Models:
    Job              - Internship listings scraped from job platforms.
    Application      - Records of submitted job applications.
    WhatsAppResponse - User approval / rejection responses via WhatsApp.

Relationships:
    Job  1──* Application
    Job  1──* WhatsAppResponse

Usage:
    from db.models import Base, Job, Application, WhatsAppResponse
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
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

# Shared declarative base — every model must inherit from this
Base = declarative_base()
Base.__allow_unmapped__ = True  # allow legacy relationship annotations without Mapped[]


# =========================================================================== #
# 1. Job Model                                                                 #
# =========================================================================== #

class Job(Base):
    """
    Represents a single internship / job listing scraped from an external
    platform (Indeed, LinkedIn, internship.com, etc.).

    Attributes:
        id           : Auto-incremented primary key.
        job_id       : Platform-specific unique job identifier string.
        title        : Job / internship title.
        company      : Name of the hiring company.
        description  : Full job description text.
        link         : Direct URL to the job posting.
        source       : Platform name (e.g. 'indeed', 'linkedin').
        scraped_at   : UTC timestamp when this record was created.
        match_score  : LLM-assigned relevance score (0.0 – 100.0), nullable
                       until the matcher node processes this job.
        status       : Workflow status for this job.
                       One of: 'pending' | 'approved' | 'rejected' |
                                'applied' | 'skipped' | 'error'

    Relationships:
        applications       : List[Application]       (one-to-many)
        whatsapp_responses : List[WhatsAppResponse]  (one-to-many)
    """

    __tablename__ = "jobs"

    __table_args__ = (
        # Prevent storing the same platform-specific job twice
        UniqueConstraint("job_id", "source", name="uq_job_id_source"),
    )

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Platform-specific identifier (e.g. Indeed's job key)
    job_id = Column(String(255), nullable=False, index=True)

    # Core job details
    title = Column(String(255), nullable=False)
    company = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    link = Column(String(1000), nullable=False)
    source = Column(String(50), nullable=False, index=True)  # 'indeed' | 'linkedin' | ...

    # Timestamps
    scraped_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Matching
    match_score = Column(Float, nullable=True)          # set by matcher node
    match_reasoning = Column(Text, nullable=True)       # LLM explanation

    # Workflow lifecycle status
    status = Column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )

    # Relationships
    applications = relationship(
        "Application",
        back_populates="job",
        cascade="all, delete-orphan",
    )
    whatsapp_responses = relationship(
        "WhatsAppResponse",
        back_populates="job",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """Human-readable representation for debugging."""
        return (
            f"<Job(id={self.id}, title='{self.title}', "
            f"company='{self.company}', status='{self.status}', "
            f"match_score={self.match_score})>"
        )


# =========================================================================== #
# 2. Application Model                                                         #
# =========================================================================== #

class Application(Base):
    """
    Records a single job application submitted by the agent on behalf of
    the user.

    Attributes:
        id               : Auto-incremented primary key.
        job_id           : Foreign key → jobs.id.
        applied_at       : UTC timestamp when the application was submitted.
        application_id   : Platform-returned confirmation / reference ID.
        status           : Current state of the application.
                           One of: 'submitted' | 'pending' | 'rejected' |
                                    'accepted' | 'error'
        application_link : Direct link to the submitted application page.

    Relationships:
        job : Job (many-to-one)
    """

    __tablename__ = "applications"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to the job listing
    job_id = Column(
        Integer,
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Submission details
    applied_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    application_id = Column(String(255), nullable=True)    # confirmation ID from platform
    status = Column(
        String(50),
        nullable=False,
        default="submitted",
        index=True,
    )
    application_link = Column(String(1000), nullable=True)  # link to submitted application

    # Timestamps
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    job = relationship("Job", back_populates="applications")

    def __repr__(self) -> str:
        """Human-readable representation for debugging."""
        return (
            f"<Application(id={self.id}, job_id={self.job_id}, "
            f"status='{self.status}', applied_at={self.applied_at})>"
        )


# =========================================================================== #
# 3. WhatsAppResponse Model                                                    #
# =========================================================================== #

class WhatsAppResponse(Base):
    """
    Stores the user's approval or rejection response received via WhatsApp
    for a particular job listing.

    Attributes:
        id            : Auto-incremented primary key.
        job_id        : Foreign key → jobs.id.
        user_approval : True = approved / False = rejected / None = pending.
        responded_at  : UTC timestamp when the user replied.
        message_sid   : Twilio message SID of the inbound reply.
        sent_at       : UTC timestamp when the approval request was sent out.
        sent_message_sid : Twilio SID of the outbound approval request.

    Relationships:
        job : Job (many-to-one)
    """

    __tablename__ = "whatsapp_responses"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to the job listing
    job_id = Column(
        Integer,
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # User response
    user_approval = Column(Boolean, nullable=True)   # None = no reply yet
    responded_at = Column(DateTime, nullable=True)   # set when user replies

    # Twilio message identifiers
    message_sid = Column(String(50), nullable=True)        # SID of inbound reply
    sent_message_sid = Column(String(50), nullable=True)   # SID of outbound request

    # Timestamps
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # when request sent

    # Relationships
    job = relationship("Job", back_populates="whatsapp_responses")

    def __repr__(self) -> str:
        """Human-readable representation for debugging."""
        return (
            f"<WhatsAppResponse(id={self.id}, job_id={self.job_id}, "
            f"user_approval={self.user_approval}, "
            f"responded_at={self.responded_at})>"
        )
