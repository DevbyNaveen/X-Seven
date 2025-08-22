"""Application settings using Pydantic."""
from functools import lru_cache
from typing import Dict, List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    This uses Pydantic to:
    1. Load values from .env file
    2. Validate data types
    3. Provide defaults
    """
    
    # API Settings
    PROJECT_NAME: str = "X-SevenAI"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Environment, Language & Logging
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    DEFAULT_LANGUAGE: str = "en"
    SUPPORTED_LANGUAGES: List[str] = [
        "en", "es", "fr", "de", "it", "lv", "et", "lt"
    ]
    LOG_LEVEL: str = "INFO"
    SENTRY_DSN: Optional[str] = None

    # Database
    DATABASE_URL: str = "sqlite:///./db/cafe2211.db"
    DB_ECHO: bool = False
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # Security
    SECRET_KEY: str = "dev-secret-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000", 
        "http://localhost:8000",
        "http://localhost:5500",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:5500",
    ]
    WEBSOCKET_ORIGINS: List[str] = [
        "ws://localhost:3000", 
        "ws://localhost:8000",
        "ws://localhost:5500",
        "ws://127.0.0.1:3000",
        "ws://127.0.0.1:8000",
        "ws://127.0.0.1:5500",
    ]
    
    # AI Language Models
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    # Preferred Groq model id (e.g., "qwen-3-32b", "gpt-oss-120b")
    GROQ_MODEL: Optional[str] = None

    # Voice Services
    ELEVENLABS_API_KEY: Optional[str] = None
    WHISPER_API_KEY: Optional[str] = None

    # Vector Database
    QDRANT_URL: Optional[str] = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None

    # External Services (Twilio, WhatsApp, Stripe)
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None
    
    # API URL for webhooks and callbacks
    API_URL: str = "http://localhost:8000"
    
    # --- These names now match your .env file ---
    WHATSAPP_UNIVERSAL_NUMBER: Optional[str] = None
    WHATSAPP_API_KEY: Optional[str] = None
    WHATSAPP_WEBHOOK_TOKEN: Optional[str] = None # For verifying webhook challenges
    STRIPE_WEBHOOK_SECRET: Optional[str] = None # For verifying webhook events
    
    # You may still need these for other API calls
    STRIPE_SECRET_KEY: Optional[str] = None 
    UNIVERSAL_BOT_NUMBER: Optional[str] = None
    WHATSAPP_BUSINESS_TOKEN: Optional[str] = None

    # Phone Provider Settings
    VONAGE_API_KEY: Optional[str] = None
    VONAGE_API_SECRET: Optional[str] = None
    VONAGE_APPLICATION_ID: Optional[str] = None

    MESSAGEBIRD_API_KEY: Optional[str] = None

    # Regional Phone Numbers
    ESTONIA_RECEIVER_NUMBER: Optional[str] = None
    LITHUANIA_RECEIVER_NUMBER: Optional[str] = None

    # Provider Selection
    DEFAULT_PHONE_PROVIDER: str = "twilio"
    PREFERRED_PROVIDERS_BY_REGION: Dict[str, List[str]] = {
        "LV": ["vonage", "messagebird"],
        "EE": ["twilio", "vonage"],
        "LT": ["vonage", "twilio"],
    }
    
    # Modern Pydantic configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        env_file_encoding='utf-8'
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Create cached settings instance.
    """
    return Settings()


# Create a single instance for easy importing
settings = get_settings()