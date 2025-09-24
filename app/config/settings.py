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
    
    # Security - Now using Supabase tokens only
    SECRET_KEY: str = "dev-secret-change-me"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000", 
        "http://localhost:8000",
        "http://localhost:5500",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:5500",
        "http://localhost:8084",
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
    # Preferred Groq model id (default: "llama-3.1-8b-instant").
    # You can override via environment variable GROQ_MODEL.
    GROQ_MODEL: Optional[str] = "llama-3.3-70b-versatile"
    # Groq request controls
    GROQ_MAX_TOKENS: int = 600
    GROQ_MAX_HISTORY: int = 6
    GROQ_MIN_HISTORY: int = 3
    # Safeguard to keep full prompt body under a safe character limit
    GROQ_MAX_PROMPT_CHARS: int = 12000
    # Limit the number of businesses included in rich context
    GROQ_MAX_BUSINESSES: int = 8

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
    
    # Supabase
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None  # Legacy key (often anon)
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None  # Preferred server‑side key for table access
    SUPABASE_API_KEY: Optional[str] = None  # Legacy fallback
    SUPABASE_JWT_SECRET: Optional[str] = None
    SUPABASE_PROJECT_ID: Optional[str] = None

    # AWS Configuration (required for Agent Squad / Bedrock)
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_DEFAULT_REGION: str = "us-east-1"
    AWS_REGION: str = "us-east-1"

    # Kafka Configuration - Modern Event Streaming
    KAFKA_BOOTSTRAP_SERVERS: List[str] = ["localhost:9092"]
    KAFKA_SECURITY_PROTOCOL: str = "PLAINTEXT"
    KAFKA_SASL_MECHANISM: Optional[str] = None
    KAFKA_SASL_USERNAME: Optional[str] = None
    KAFKA_SASL_PASSWORD: Optional[str] = None
    KAFKA_SSL_CAFILE: Optional[str] = None
    KAFKA_SSL_CERTFILE: Optional[str] = None
    KAFKA_SSL_KEYFILE: Optional[str] = None
    
    # Kafka Producer Settings
    KAFKA_PRODUCER_ACKS: str = "all"  # Wait for all replicas
    KAFKA_PRODUCER_RETRIES: int = 3
    KAFKA_PRODUCER_BATCH_SIZE: int = 16384
    KAFKA_PRODUCER_LINGER_MS: int = 10
    KAFKA_PRODUCER_COMPRESSION_TYPE: str = "gzip"
    KAFKA_PRODUCER_MAX_REQUEST_SIZE: int = 1048576
    
    # Kafka Consumer Settings
    KAFKA_CONSUMER_GROUP_ID: str = "xseven-ai-consumers"
    KAFKA_CONSUMER_AUTO_OFFSET_RESET: str = "earliest"
    KAFKA_CONSUMER_ENABLE_AUTO_COMMIT: bool = False
    KAFKA_CONSUMER_MAX_POLL_RECORDS: int = 500
    KAFKA_CONSUMER_SESSION_TIMEOUT_MS: int = 30000
    KAFKA_CONSUMER_HEARTBEAT_INTERVAL_MS: int = 3000
    
    # Schema Registry
    SCHEMA_REGISTRY_URL: str = "http://localhost:8081"
    SCHEMA_REGISTRY_USERNAME: Optional[str] = None
    SCHEMA_REGISTRY_PASSWORD: Optional[str] = None
    
    # Kafka Topics Configuration
    KAFKA_TOPICS: Dict[str, Dict[str, Any]] = {
        "conversation.events": {
            "partitions": 3,
            "replication_factor": 1,
            "config": {
                "cleanup.policy": "compact",
                "retention.ms": 604800000  # 7 days
            }
        },
        "ai.responses": {
            "partitions": 6,
            "replication_factor": 1,
            "config": {
                "cleanup.policy": "delete",
                "retention.ms": 259200000  # 3 days
            }
        },
        "business.analytics": {
            "partitions": 2,
            "replication_factor": 1,
            "config": {
                "cleanup.policy": "compact",
                "retention.ms": 2592000000  # 30 days
            }
        },
        "system.monitoring": {
            "partitions": 1,
            "replication_factor": 1,
            "config": {
                "cleanup.policy": "delete",
                "retention.ms": 86400000  # 1 day
            }
        },
        "dead.letter.queue": {
            "partitions": 1,
            "replication_factor": 1,
            "config": {
                "cleanup.policy": "delete",
                "retention.ms": 604800000  # 7 days
            }
        }
    }
    
    # Event Sourcing Settings
    ENABLE_EVENT_SOURCING: bool = True
    EVENT_STORE_BATCH_SIZE: int = 100
    EVENT_REPLAY_BATCH_SIZE: int = 1000

    
    
    # Modern Pydantic configuration - ignore extra fields
    # Load environment variables from .env; extra fields are ignored.
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        env_file_encoding='utf-8',
        extra="ignore"  # Ignore extra environment variables
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Create cached settings instance.
    """
    return Settings()


# Create a single instance for easy importing
settings = get_settings()