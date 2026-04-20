"""URGP Configuration Management.

Pydantic-based settings with support for environment variables (URGP_ prefix)
and .env files. Fail-fast validation on startup with descriptive error messages.

Reference: docs/05-technical-design.md § Configuration (Pydantic Settings)
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import Field, PostgresDsn, RedisDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class URGPSettings(BaseSettings):
    """URGP application settings.

    All settings can be configured via:
    - Environment variables with URGP_ prefix (e.g., URGP_DATABASE_URL)
    - .env file in the project root
    - YAML config files (loaded separately)
    """

    # ─────────────────────────────────────────────
    # Application
    # ─────────────────────────────────────────────
    app_name: str = "URGP"
    app_version: str = "0.1.0"
    environment: str = Field(default="development", description="development | staging | production")
    debug: bool = Field(default=False, description="Enable debug mode (never in production)")

    # ─────────────────────────────────────────────
    # Database (PostgreSQL)
    # ─────────────────────────────────────────────
    database_url: PostgresDsn = Field(
        ...,
        description="PostgreSQL async connection URL (e.g., postgresql+asyncpg://user:pass@host:5432/db)",
    )
    database_pool_size: int = Field(default=10, ge=1, le=100, description="SQLAlchemy connection pool size")
    database_pool_overflow: int = Field(default=20, ge=0, le=100, description="Max overflow connections beyond pool")

    # ─────────────────────────────────────────────
    # Message Broker (RabbitMQ)
    # ─────────────────────────────────────────────
    rabbitmq_url: str = Field(
        ...,
        description="RabbitMQ AMQP connection URL (e.g., amqp://user:pass@host:5672/)",
    )

    # ─────────────────────────────────────────────
    # Cache (Redis)
    # ─────────────────────────────────────────────
    redis_url: RedisDsn = Field(
        ...,
        description="Redis connection URL (e.g., redis://host:6379/0)",
    )
    redis_cache_ttl: int = Field(default=300, ge=0, description="Default cache TTL in seconds (5 min)")

    # ─────────────────────────────────────────────
    # External Integrations
    # ─────────────────────────────────────────────
    default_git_provider: str = Field(default="github", description="Default Git provider: github | bitbucket | gitlab")
    default_issue_tracker: str = Field(default="jira", description="Default issue tracker: jira")

    # ─────────────────────────────────────────────
    # Security
    # ─────────────────────────────────────────────
    jwt_secret_key: str = Field(
        ...,
        min_length=32,
        description="Secret key for JWT token signing (min 32 chars)",
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT signing algorithm")
    jwt_expiry_minutes: int = Field(default=60, ge=5, description="JWT token expiry in minutes")
    api_key_hash_rounds: int = Field(default=12, ge=4, le=31, description="bcrypt hash rounds for API keys")
    signing_key: str = Field(
        ...,
        min_length=32,
        description="HMAC-SHA256 signing key for manifest signatures",
    )

    # ─────────────────────────────────────────────
    # Notifications
    # ─────────────────────────────────────────────
    smtp_host: str = Field(default="localhost", description="SMTP server hostname")
    smtp_port: int = Field(default=1025, ge=1, le=65535, description="SMTP server port")
    smtp_from: str = Field(default="urgp@company.com", description="Sender email address")
    smtp_username: str = Field(default="", description="SMTP auth username (empty = no auth)")
    smtp_password: str = Field(default="", description="SMTP auth password")

    # ─────────────────────────────────────────────
    # Rate Limiting
    # ─────────────────────────────────────────────
    rate_limit_read: int = Field(default=100, ge=1, description="Read requests per minute per API key")
    rate_limit_write: int = Field(default=20, ge=1, description="Write requests per minute per API key")

    # ─────────────────────────────────────────────
    # Operational
    # ─────────────────────────────────────────────
    log_level: str = Field(default="INFO", description="Logging level: DEBUG | INFO | WARNING | ERROR | CRITICAL")
    log_format: str = Field(default="json", description="Log format: json | console")
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origins",
    )
    api_prefix: str = Field(default="/api/v1", description="API URL prefix")

    # ─────────────────────────────────────────────
    # Server
    # ─────────────────────────────────────────────
    host: str = Field(default="0.0.0.0", description="Server bind host")
    port: int = Field(default=8000, ge=1, le=65535, description="Server bind port")
    workers: int = Field(default=1, ge=1, description="Number of Uvicorn workers")

    model_config = SettingsConfigDict(
        env_prefix="URGP_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─────────────────────────────────────────────
    # Validators
    # ─────────────────────────────────────────────
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is a known Python logging level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid_levels:
            msg = f"Invalid log_level '{v}'. Must be one of: {', '.join(sorted(valid_levels))}"
            raise ValueError(msg)
        return upper

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment is a known value."""
        valid_envs = {"development", "staging", "production"}
        lower = v.lower()
        if lower not in valid_envs:
            msg = f"Invalid environment '{v}'. Must be one of: {', '.join(sorted(valid_envs))}"
            raise ValueError(msg)
        return lower

    @model_validator(mode="after")
    def validate_production_settings(self) -> URGPSettings:
        """Ensure production-safe settings."""
        if self.environment == "production" and self.debug:
            msg = "Debug mode must be disabled in production"
            raise ValueError(msg)
        return self

    @property
    def database_url_str(self) -> str:
        """Return database URL as string for SQLAlchemy."""
        return str(self.database_url)

    def masked_dict(self) -> dict[str, Any]:
        """Return settings dict with sensitive values masked for logging."""
        data = self.model_dump()
        sensitive_keys = {"jwt_secret_key", "signing_key", "smtp_password"}
        for key in sensitive_keys:
            if data.get(key):
                data[key] = "***MASKED***"
        return data


@lru_cache
def get_settings() -> URGPSettings:
    """Get cached application settings (singleton).

    Returns:
        URGPSettings: Validated application settings.

    Raises:
        pydantic.ValidationError: If required settings are missing or invalid.
    """
    return URGPSettings()  # type: ignore[call-arg]
