"""
PipeCat AI Configuration Module

Handles configuration and initialization of PipeCat AI components
with integration to X-Seven's existing services.
"""

import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


class VoiceProvider(str, Enum):
    """Supported voice service providers."""
    ELEVENLABS = "elevenlabs"
    OPENAI = "openai"
    AZURE = "azure"
    CARTESIA = "cartesia"


class STTProvider(str, Enum):
    """Supported speech-to-text providers."""
    OPENAI_WHISPER = "openai_whisper"
    ELEVENLABS = "elevenlabs"
    AZURE = "azure"
    DEEPGRAM = "deepgram"


class TransportType(str, Enum):
    """Supported transport types."""
    TWILIO = "twilio"
    WEBRTC = "webrtc"
    WEBSOCKET = "websocket"
    DAILY = "daily"


@dataclass
class VoiceSettings:
    """Voice synthesis settings."""
    provider: VoiceProvider = VoiceProvider.ELEVENLABS
    voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # Default ElevenLabs voice
    stability: float = 0.5
    similarity_boost: float = 0.8
    style: float = 0.0
    use_speaker_boost: bool = True
    optimize_streaming_latency: int = 2
    output_format: str = "mp3_44100_128"


@dataclass
class STTSettings:
    """Speech-to-text settings."""
    provider: STTProvider = STTProvider.OPENAI_WHISPER
    model: str = "whisper-1"
    language: str = "en"
    temperature: float = 0.0
    response_format: str = "json"
    timestamp_granularities: List[str] = field(default_factory=lambda: ["word"])


@dataclass
class LLMSettings:
    """Language model settings for voice interactions."""
    provider: str = "openai"
    model: str = "gpt-4-turbo-preview"
    temperature: float = 0.7
    max_tokens: int = 1000
    system_prompt: str = "You are a helpful AI assistant optimized for voice conversations. Keep responses concise and natural for speech."


@dataclass
class TransportSettings:
    """Transport configuration settings."""
    # Non-default fields first
    type: TransportType = TransportType.TWILIO
    host: str = "0.0.0.0"
    port: int = 8765

    # Optional fields with defaults
    account_sid: Optional[str] = None
    auth_token: Optional[str] = None
    phone_number: Optional[str] = None
    ice_servers: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class PipeCatConfig:
    """Main PipeCat configuration."""
    
    # Service settings
    voice_settings: VoiceSettings = field(default_factory=VoiceSettings)
    stt_settings: STTSettings = field(default_factory=STTSettings)
    llm_settings: LLMSettings = field(default_factory=LLMSettings)
    transport_settings: TransportSettings = field(default_factory=TransportSettings)
    
    # Integration settings
    enable_langgraph_integration: bool = True
    enable_temporal_integration: bool = True
    enable_crewai_integration: bool = True
    enable_dspy_integration: bool = True
    
    # Performance settings
    max_concurrent_calls: int = 100
    call_timeout_seconds: int = 300
    audio_buffer_size: int = 1024
    enable_vad: bool = True  # Voice Activity Detection
    vad_threshold: float = 0.5
    
    # Analytics settings
    enable_analytics: bool = True
    enable_recording: bool = True
    enable_transcription: bool = True
    
    # Error handling
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    enable_fallback: bool = True
    
    @classmethod
    def from_env(cls) -> "PipeCatConfig":
        """Create configuration from environment variables."""
        config = cls()
        
        # Voice settings
        if os.getenv("ELEVENLABS_VOICE_ID"):
            config.voice_settings.voice_id = os.getenv("ELEVENLABS_VOICE_ID")
        
        # Transport settings
        config.transport_settings.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        config.transport_settings.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        config.transport_settings.phone_number = os.getenv("TWILIO_PHONE_NUMBER")
        
        # LLM settings
        if os.getenv("OPENAI_MODEL"):
            config.llm_settings.model = os.getenv("OPENAI_MODEL")
        
        # Performance settings
        if os.getenv("MAX_CONCURRENT_CALLS"):
            config.max_concurrent_calls = int(os.getenv("MAX_CONCURRENT_CALLS"))
        
        return config
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of errors."""
        errors = []
        
        # Check required API keys
        if self.voice_settings.provider == VoiceProvider.ELEVENLABS:
            if not os.getenv("ELEVENLABS_API_KEY"):
                errors.append("ELEVENLABS_API_KEY is required for ElevenLabs voice")
        
        if self.stt_settings.provider == STTProvider.OPENAI_WHISPER:
            if not os.getenv("OPENAI_API_KEY"):
                errors.append("OPENAI_API_KEY is required for OpenAI Whisper")
        
        if self.transport_settings.type == TransportType.TWILIO:
            if not self.transport_settings.account_sid:
                errors.append("TWILIO_ACCOUNT_SID is required for Twilio transport")
            if not self.transport_settings.auth_token:
                errors.append("TWILIO_AUTH_TOKEN is required for Twilio transport")
        
        # Validate ranges
        if not 0 <= self.voice_settings.stability <= 1:
            errors.append("Voice stability must be between 0 and 1")
        
        if not 0 <= self.voice_settings.similarity_boost <= 1:
            errors.append("Voice similarity_boost must be between 0 and 1")
        
        if self.max_concurrent_calls <= 0:
            errors.append("max_concurrent_calls must be positive")
        
        return errors
    
    def get_api_keys(self) -> Dict[str, Optional[str]]:
        """Get all required API keys."""
        return {
            "elevenlabs": os.getenv("ELEVENLABS_API_KEY"),
            "openai": os.getenv("OPENAI_API_KEY"),
            "twilio_sid": os.getenv("TWILIO_ACCOUNT_SID"),
            "twilio_token": os.getenv("TWILIO_AUTH_TOKEN"),
            "groq": os.getenv("GROQ_API_KEY"),
            "anthropic": os.getenv("ANTHROPIC_API_KEY"),
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "voice_settings": {
                "provider": self.voice_settings.provider.value,
                "voice_id": self.voice_settings.voice_id,
                "stability": self.voice_settings.stability,
                "similarity_boost": self.voice_settings.similarity_boost,
                "style": self.voice_settings.style,
                "use_speaker_boost": self.voice_settings.use_speaker_boost,
                "optimize_streaming_latency": self.voice_settings.optimize_streaming_latency,
                "output_format": self.voice_settings.output_format,
            },
            "stt_settings": {
                "provider": self.stt_settings.provider.value,
                "model": self.stt_settings.model,
                "language": self.stt_settings.language,
                "temperature": self.stt_settings.temperature,
                "response_format": self.stt_settings.response_format,
                "timestamp_granularities": self.stt_settings.timestamp_granularities,
            },
            "llm_settings": {
                "provider": self.llm_settings.provider,
                "model": self.llm_settings.model,
                "temperature": self.llm_settings.temperature,
                "max_tokens": self.llm_settings.max_tokens,
                "system_prompt": self.llm_settings.system_prompt,
            },
            "transport_settings": {
                "type": self.transport_settings.type.value,
                "account_sid": self.transport_settings.account_sid,
                "phone_number": self.transport_settings.phone_number,
                "host": self.transport_settings.host,
                "port": self.transport_settings.port,
            },
            "integrations": {
                "langgraph": self.enable_langgraph_integration,
                "temporal": self.enable_temporal_integration,
                "crewai": self.enable_crewai_integration,
                "dspy": self.enable_dspy_integration,
            },
            "performance": {
                "max_concurrent_calls": self.max_concurrent_calls,
                "call_timeout_seconds": self.call_timeout_seconds,
                "audio_buffer_size": self.audio_buffer_size,
                "enable_vad": self.enable_vad,
                "vad_threshold": self.vad_threshold,
            },
            "analytics": {
                "enable_analytics": self.enable_analytics,
                "enable_recording": self.enable_recording,
                "enable_transcription": self.enable_transcription,
            },
            "error_handling": {
                "max_retries": self.max_retries,
                "retry_delay_seconds": self.retry_delay_seconds,
                "enable_fallback": self.enable_fallback,
            }
        }


# Global configuration instance
_config: Optional[PipeCatConfig] = None


def get_pipecat_config() -> PipeCatConfig:
    """Get the global PipeCat configuration instance."""
    global _config
    if _config is None:
        _config = PipeCatConfig.from_env()
        
        # Validate configuration
        errors = _config.validate()
        if errors:
            logger.warning(f"PipeCat configuration validation warnings: {errors}")
        else:
            logger.info("PipeCat configuration validated successfully")
    
    return _config


def set_pipecat_config(config: PipeCatConfig) -> None:
    """Set the global PipeCat configuration instance."""
    global _config
    _config = config
    logger.info("PipeCat configuration updated")
