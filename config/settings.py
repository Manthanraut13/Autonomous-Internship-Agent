"""
config/settings.py
------------------
Pydantic BaseSettings class for loading and validating all environment
variables used by the Autonomous Internship Agent.

All settings are read from the .env file in the project root.
A @field_validator is used on DATABASE_URL to ensure it references a
supported database dialect (postgresql / sqlite for tests).

Usage:
    from config.settings import settings
    print(settings.groq_api_key)
"""

from __future__ import annotations

import logging
from typing import List, Optional, Union

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    Central settings object that reads values from the .env file.

    Environment variables are case-insensitive; pydantic-settings will
    match  OPENAI_API_KEY  ->  openai_api_key  automatically.

    Attributes:
        groq_api_key         : Secret key for Groq API calls.
        groq_model           : Model name, defaults to 'llama3-70b-8192'.
        langchain_tracing_v2 : Enable LangSmith tracing (true/false).
        langchain_api_key    : LangSmith API key.
        langchain_project    : LangSmith project name.
        langchain_endpoint   : LangSmith server URL.
        twilio_account_sid   : Twilio Account SID (starts with AC...).
        twilio_auth_token    : Twilio Auth Token.
        twilio_phone_number  : Twilio WhatsApp-enabled phone (E.164).
        user_whatsapp_number : Recipient WhatsApp number (E.164).
        sendgrid_api_key     : SendGrid API key for email delivery.
        sender_email         : Verified sender email address.
        recipient_email      : User email for daily summaries.
        database_url         : SQLAlchemy-style database URL (validated).
        match_score_threshold: Minimum score (0-100) to send approval.
        approval_timeout_hours: Hours before auto-reject on no reply.
        auto_reject_on_timeout: If True, reject jobs with no reply.
        job_sources          : List of job platforms to scrape.
        debug                : Enable verbose debug logging.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,   # GROQ_API_KEY == groq_api_key
        extra="ignore",         # silently ignore unknown env vars
    )

    # ------------------------------------------------------------------ #
    # Groq                                                                 #
    # ------------------------------------------------------------------ #
    groq_api_key: str
    groq_model: str = "llama-3.1-8b-instant"

    # ------------------------------------------------------------------ #
    # LangSmith / LangChain tracing                                        #
    # ------------------------------------------------------------------ #
    langchain_tracing_v2: bool = False
    langchain_api_key: Optional[str] = None
    langchain_project: str = "internship-agent"
    langchain_endpoint: str = "https://api.smith.langchain.com"

    # ------------------------------------------------------------------ #
    # Twilio (WhatsApp)                                                    #
    # ------------------------------------------------------------------ #
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_phone_number: str            # Twilio WhatsApp number (E.164)
    user_whatsapp_number: str           # Recipient WhatsApp number (E.164)

    # ------------------------------------------------------------------ #
    # Email Delivery (SendGrid or Gmail / SMTP / OAuth2)                  #
    # ------------------------------------------------------------------ #
    sendgrid_api_key: Optional[str] = None
    sender_email: str = "noreply@internshipagent.com"
    recipient_email: str = "manthanr141@gmail.com"
    gmail_user: Optional[str] = None
    gmail_app_password: Optional[str] = None
    gmail_credentials_file: str = "credentials.json"
    gmail_token_file: str = "token.json"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587

    # ------------------------------------------------------------------ #
    # Database                                                             #
    # ------------------------------------------------------------------ #
    database_url: str  # validated below by @field_validator

    # ------------------------------------------------------------------ #
    # Agent behaviour                                                      #
    # ------------------------------------------------------------------ #
    match_score_threshold: int = 70
    approval_timeout_hours: int = 24
    auto_reject_on_timeout: bool = True

    # ------------------------------------------------------------------ #
    # Job sources  (stored in .env as a comma-separated string)           #
    # Declared as str here to prevent pydantic-settings from trying to   #
    # JSON-decode the value; the @field_validator converts it to a list. #
    # ------------------------------------------------------------------ #
    job_sources: Union[List[str], str] = "indeed,linkedin,internship.com,arbeitnow,remotive,himalayas,apollo,jsearch"

    # ------------------------------------------------------------------ #
    # Additional APIs                                                      #
    # ------------------------------------------------------------------ #
    adzuna_app_id: Optional[str] = None
    adzuna_api_key: Optional[str] = None
    apollo_api_key: Optional[str] = None
    jsearch_api_key: Optional[str] = None

    # ------------------------------------------------------------------ #
    # Candidate Profile                                                    #
    # ------------------------------------------------------------------ #
    candidate_name: str = "Manthan Raut"
    candidate_email: str = "manthanr141@gmail.com"
    candidate_phone: str = "+919529883808"
    candidate_github: str = "https://github.com/Manthanraut13"
    candidate_linkedin: str = "https://linkedin.com/in/manthan-raut"

    # ------------------------------------------------------------------ #
    # Dashboard Authentication                                             #
    # ------------------------------------------------------------------ #
    admin_username: str = "admin"
    admin_password: str = "admin123"
    auth_secret_key: str = "agent-secure-auth-secret-key-change-in-production"

    # ------------------------------------------------------------------ #
    # Debug flag                                                           #
    # ------------------------------------------------------------------ #
    debug: bool = False


    # ================================================================== #
    # Field Validators                                                     #
    # ================================================================== #

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """
        Ensure DATABASE_URL targets a supported dialect and normalize postgres:// to postgresql://.
        """
        if not value:
            return "sqlite:///data/agent.db"

        # Auto-convert legacy Render / Heroku postgres:// prefix
        if value.startswith("postgres://"):
            value = value.replace("postgres://", "postgresql://", 1)

        accepted_prefixes = (
            "postgresql://",
            "postgresql+psycopg2://",
            "sqlite://",
        )

        if not any(value.startswith(prefix) for prefix in accepted_prefixes):
            raise ValueError(
                f"DATABASE_URL must start with one of {accepted_prefixes}.\n"
                f"  Current value  : '{value}'\n"
                f"  Example (valid): 'postgresql://user:password@localhost:5432/internship_agent'\n"
                f"  Check your .env file and ensure DATABASE_URL is correct."
            )

        logger.debug("DATABASE_URL validated successfully.")
        return value

    @field_validator("job_sources", mode="before")
    @classmethod
    def parse_job_sources(cls, value) -> List[str]:
        """
        Accept job_sources either as a Python list or as a
        comma-separated string coming straight from the .env file.

        Args:
            value: Raw value - either List[str] or a comma-separated str.

        Returns:
            List[str]: Cleaned list of source names (lowercase, stripped).

        Examples:
            >>> parse_job_sources("indeed,linkedin , internship.com")
            ['indeed', 'linkedin', 'internship.com']

            >>> parse_job_sources(["Indeed", "LinkedIn"])
            ['indeed', 'linkedin']
        """
        if isinstance(value, str):
            return [s.strip().lower() for s in value.split(",") if s.strip()]
        # Already a list (e.g., when set programmatically in tests)
        return [str(s).strip().lower() for s in value]

    @field_validator("match_score_threshold", mode="before")
    @classmethod
    def validate_threshold(cls, value) -> int:
        """
        Ensure match_score_threshold is between 0 and 100 inclusive.

        Args:
            value: Raw threshold value from environment.

        Returns:
            int: Validated threshold.

        Raises:
            ValueError: If value is outside the range [0, 100].

        Examples:
            >>> validate_threshold(70)
            70

            >>> validate_threshold(150)
            # raises ValueError
        """
        value = int(value)
        if not (0 <= value <= 100):
            raise ValueError(
                f"MATCH_SCORE_THRESHOLD must be between 0 and 100 inclusive. "
                f"Got: {value}"
            )
        return value

    @field_validator("approval_timeout_hours", mode="before")
    @classmethod
    def validate_timeout(cls, value) -> int:
        """
        Ensure approval_timeout_hours is a positive integer (>= 1).

        Args:
            value: Raw timeout value from environment.

        Returns:
            int: Validated timeout hours.

        Raises:
            ValueError: If value is less than 1.

        Examples:
            >>> validate_timeout(24)
            24

            >>> validate_timeout(0)
            # raises ValueError
        """
        value = int(value)
        if value < 1:
            raise ValueError(
                f"APPROVAL_TIMEOUT_HOURS must be >= 1. Got: {value}"
            )
        return value

    # ================================================================== #
    # Model-level validator (runs after all fields are set)               #
    # ================================================================== #

    @model_validator(mode="after")
    def log_loaded_settings(self) -> "Settings":
        """
        Log a confirmation message (without leaking secrets) once all
        fields have been loaded and validated successfully.

        Returns:
            Settings: Self (required by Pydantic model_validator).
        """
        logger.info(
            "Settings loaded successfully:\n"
            f"  groq_model             = {self.groq_model}\n"
            f"  langchain_tracing_v2   = {self.langchain_tracing_v2}\n"
            f"  langchain_project      = {self.langchain_project}\n"
            f"  twilio_phone_number    = {self.twilio_phone_number}\n"
            f"  sender_email           = {self.sender_email}\n"
            f"  recipient_email        = {self.recipient_email}\n"
            f"  match_score_threshold  = {self.match_score_threshold}\n"
            f"  approval_timeout_hours = {self.approval_timeout_hours}\n"
            f"  auto_reject_on_timeout = {self.auto_reject_on_timeout}\n"
            f"  job_sources            = {self.job_sources}\n"
            f"  debug                  = {self.debug}"
        )
        return self

    # ================================================================== #
    # Convenience properties                                               #
    # ================================================================== #

    @property
    def is_debug(self) -> bool:
        """Return True when debug mode is active."""
        return self.debug

    @property
    def whatsapp_from(self) -> str:
        """
        Return the Twilio sender address in the format required by the
        Twilio WhatsApp API: 'whatsapp:+1xxxxxxxxxx'

        Returns:
            str: Properly prefixed Twilio WhatsApp sender number.
        """
        number = self.twilio_phone_number
        if not number.startswith("whatsapp:"):
            return f"whatsapp:{number}"
        return number

    @property
    def whatsapp_to(self) -> str:
        """
        Return the recipient WhatsApp address in Twilio format:
        'whatsapp:+91xxxxxxxxxx'

        Returns:
            str: Properly prefixed recipient WhatsApp number.
        """
        number = self.user_whatsapp_number
        if not number.startswith("whatsapp:"):
            return f"whatsapp:{number}"
        return number


# --------------------------------------------------------------------------- #
# Singleton – import and use anywhere in the project                          #
#                                                                             #
#   from config.settings import settings                                      #
#   print(settings.groq_model)            # llama3-70b-8192                  #
#   print(settings.whatsapp_from)         # whatsapp:+19383003509            #
# --------------------------------------------------------------------------- #
settings = Settings()
