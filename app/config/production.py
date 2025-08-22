"""Production configuration settings."""
import os
from app.config.settings import Settings


class ProductionSettings(Settings):
    """Production-specific settings."""

    # Environment
    ENVIRONMENT: str = "production"
    DEBUG: bool = False

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY")  # Must be set in environment
    ALLOWED_HOSTS: list = ["api.x-sevenai.com", "x-sevenai.com"]

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 40

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL")

    # Monitoring
    SENTRY_DSN: str = os.getenv("SENTRY_DSN")

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "/var/log/x-sevenai/app.log"