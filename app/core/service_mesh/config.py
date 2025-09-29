"""
Configuration Management for Service Mesh
Centralized configuration with validation and hot-reload
"""

import os
import json
import logging
from typing import Any, Dict, Optional, Type, Union, Callable, List
from dataclasses import dataclass, asdict
from enum import Enum
import yaml
from pathlib import Path
from pydantic import BaseModel, validator
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)


class ServiceConfig(BaseModel):
    """Base configuration for services"""
    enabled: bool = True
    timeout: int = 30
    retry_count: int = 3
    retry_delay: float = 1.0
    health_check_interval: int = 30
    
    class Config:
        extra = "allow"


class DatabaseConfig(ServiceConfig):
    """Database configuration"""
    host: str = "localhost"
    port: int = 5432
    database: str = "xseven"
    username: str = "postgres"
    password: str = ""
    ssl_mode: str = "prefer"
    pool_size: int = 20
    max_overflow: int = 30
    
    @validator('port')
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError('Port must be between 1 and 65535')
        return v


class RedisConfig(ServiceConfig):
    """Redis configuration"""
    host: str = "localhost"
    port: int = 6379
    database: int = 0
    password: Optional[str] = None
    ssl: bool = False
    socket_timeout: int = 30
    socket_connect_timeout: int = 30
    
    @validator('port')
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError('Port must be between 1 and 65535')
        return v


class KafkaConfig(ServiceConfig):
    """Kafka configuration"""
    bootstrap_servers: str = "localhost:9092"
    security_protocol: str = "PLAINTEXT"
    consumer_group_id: str = "xseven-consumer"
    topics: Dict[str, Dict[str, Any]] = {}
    
    @validator('bootstrap_servers')
    def validate_servers(cls, v):
        if not v:
            raise ValueError('Bootstrap servers cannot be empty')
        return v


class TemporalConfig(ServiceConfig):
    """Temporal configuration"""
    host: str = "localhost"
    port: int = 7233
    namespace: str = "default"
    task_queue: str = "xseven-tasks"
    
    @validator('port')
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError('Port must be between 1 and 65535')
        return v


class CrewAIConfig(ServiceConfig):
    """CrewAI configuration"""
    max_agents: int = 10
    timeout: int = 300
    verbose: bool = False
    memory: bool = True


class DSPyConfig(ServiceConfig):
    """DSPy configuration"""
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 1000
    optimization_enabled: bool = True
    training_data_path: Optional[str] = None


class VoiceConfig(ServiceConfig):
    """Voice service configuration"""
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    stt_provider: str = "openai"
    tts_provider: str = "elevenlabs"
    voice_id: str = "pNInz6obpgDQGcFmaJgB"
    max_concurrent_calls: int = 10


class ServiceMeshConfig(BaseModel):
    """Service mesh configuration"""
    database: DatabaseConfig = DatabaseConfig()
    redis: RedisConfig = RedisConfig()
    kafka: KafkaConfig = KafkaConfig()
    temporal: TemporalConfig = TemporalConfig()
    crewai: CrewAIConfig = CrewAIConfig()
    dspy: DSPyConfig = DSPyConfig()
    voice: VoiceConfig = VoiceConfig()
    
    # Service mesh settings
    health_check_interval: int = 30
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 60
    max_concurrent_starts: int = 3
    startup_timeout: int = 300


class ConfigFileHandler(FileSystemEventHandler):
    """Handle configuration file changes"""
    
    def __init__(self, config_manager: 'ConfigManager'):
        self.config_manager = config_manager
    
    def on_modified(self, event):
        if event.src_path.endswith(('.yml', '.yaml', '.json')):
            asyncio.create_task(self.config_manager.reload_config())


class ConfigManager:
    """Centralized configuration management with hot-reload"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._find_config_file()
        self.config: ServiceMeshConfig = ServiceMeshConfig()
        self._observers: List[Callable] = []
        self._file_observer: Optional[Observer] = None
        self._lock = asyncio.Lock()
        
        # Load initial configuration
        self.load_config()
        
        # Start file monitoring
        self.start_file_monitoring()
    
    def _find_config_file(self) -> str:
        """Find configuration file in standard locations"""
        possible_paths = [
            "config/service_mesh.yml",
            "config/service_mesh.yaml",
            "service_mesh.yml",
            "service_mesh.yaml",
            "config/service_mesh.json",
            "service_mesh.json",
            os.getenv("XSEVEN_CONFIG_PATH", "")
        ]
        
        for path in possible_paths:
            if path and os.path.exists(path):
                return path
        
        # Create default config if none exists
        default_path = "config/service_mesh.yml"
        os.makedirs(os.path.dirname(default_path), exist_ok=True)
        
        with open(default_path, 'w') as f:
            yaml.dump(asdict(ServiceMeshConfig()), f, default_flow_style=False)
        
        return default_path
    
    def load_config(self):
        """Load configuration from file"""
        try:
            if not os.path.exists(self.config_path):
                logger.warning(f"Config file not found: {self.config_path}")
                return
            
            with open(self.config_path, 'r') as f:
                if self.config_path.endswith(('.yml', '.yaml')):
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)
            
            # Substitute environment variables
            data = self._substitute_env_vars(data)
            
            self.config = ServiceMeshConfig(**data)
            logger.info(f"✅ Configuration loaded from {self.config_path}")
            
        except Exception as e:
            logger.error(f"❌ Failed to load configuration: {e}")
            raise
    
    def _substitute_env_vars(self, data: Any) -> Any:
        """Recursively substitute environment variables in configuration data"""
        import re
        
        if isinstance(data, dict):
            return {key: self._substitute_env_vars(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._substitute_env_vars(item) for item in data]
        elif isinstance(data, str):
            # Match ${VAR:default} or ${VAR} patterns
            pattern = r'\$\{([^:}]+)(?::([^}]*))?\}'
            def replace_var(match):
                var_name = match.group(1)
                default_value = match.group(2) or ''
                return os.getenv(var_name, default_value)
            return re.sub(pattern, replace_var, data)
        else:
            return data
    
    async def reload_config(self):
        """Reload configuration and notify observers"""
        async with self._lock:
            try:
                old_config = self.config
                self.load_config()
                
                # Notify observers
                await self._notify_observers(old_config, self.config)
                
                logger.info("🔄 Configuration reloaded successfully")
                
            except Exception as e:
                logger.error(f"❌ Failed to reload configuration: {e}")
    
    def start_file_monitoring(self):
        """Start monitoring configuration file for changes"""
        if self._file_observer:
            return
        
        try:
            self._file_observer = Observer()
            handler = ConfigFileHandler(self)
            self._file_observer.schedule(
                handler, 
                os.path.dirname(self.config_path) or '.', 
                recursive=False
            )
            self._file_observer.start()
            logger.info(f"🔍 Started monitoring: {self.config_path}")
            
        except Exception as e:
            logger.warning(f"⚠️ Could not start file monitoring: {e}")
    
    def stop_file_monitoring(self):
        """Stop file monitoring"""
        if self._file_observer:
            self._file_observer.stop()
            self._file_observer.join()
            self._file_observer = None
            logger.info("🛑 Stopped file monitoring")
    
    def add_observer(self, callback: Callable):
        """Add configuration change observer"""
        self._observers.append(callback)
    
    def remove_observer(self, callback: Callable):
        """Remove configuration change observer"""
        if callback in self._observers:
            self._observers.remove(callback)
    
    async def _notify_observers(self, old_config: ServiceMeshConfig, new_config: ServiceMeshConfig):
        """Notify all observers of configuration changes"""
        tasks = []
        for observer in self._observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    task = asyncio.create_task(observer(old_config, new_config))
                else:
                    observer(old_config, new_config)
                    task = None
                
                if task:
                    tasks.append(task)
                    
            except Exception as e:
                logger.error(f"Error in config observer: {e}")
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def get_config(self, service_name: str = None) -> Any:
        """Get configuration for a specific service or entire config"""
        if service_name:
            return getattr(self.config, service_name, None)
        return self.config
    
    def update_config(self, service_name: str, updates: Dict[str, Any]):
        """Update configuration for a specific service"""
        try:
            service_config = getattr(self.config, service_name)
            for key, value in updates.items():
                if hasattr(service_config, key):
                    setattr(service_config, key, value)
            
            logger.info(f"📝 Updated {service_name} configuration")
            
        except Exception as e:
            logger.error(f"❌ Failed to update {service_name} configuration: {e}")
    
    def save_config(self):
        """Save current configuration to file"""
        try:
            with open(self.config_path, 'w') as f:
                if self.config_path.endswith(('.yml', '.yaml')):
                    yaml.dump(self.config.dict(), f, default_flow_style=False)
                else:
                    json.dump(self.config.dict(), f, indent=2)
            
            logger.info(f"💾 Configuration saved to {self.config_path}")
            
        except Exception as e:
            logger.error(f"❌ Failed to save configuration: {e}")
    
    def validate_config(self) -> List[str]:
        """Validate current configuration"""
        errors = []
        
        try:
            # Validate database config
            db_config = self.config.database
            if not db_config.host:
                errors.append("Database host is required")
            if not db_config.database:
                errors.append("Database name is required")
            
            # Validate Redis config
            redis_config = self.config.redis
            if not redis_config.host:
                errors.append("Redis host is required")
            
            # Validate Kafka config
            kafka_config = self.config.kafka
            if not kafka_config.bootstrap_servers:
                errors.append("Kafka bootstrap servers are required")
            
            # Validate Temporal config
            temporal_config = self.config.temporal
            if not temporal_config.host:
                errors.append("Temporal host is required")
            
        except Exception as e:
            errors.append(f"Configuration validation error: {e}")
        
        return errors
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get configuration summary"""
        return {
            "config_path": self.config_path,
            "services": {
                "database": self.config.database.dict(),
                "redis": self.config.redis.dict(),
                "kafka": self.config.kafka.dict(),
                "temporal": self.config.temporal.dict(),
                "crewai": self.config.crewai.dict(),
                "dspy": self.config.dspy.dict(),
                "voice": self.config.voice.dict()
            },
            "validation_errors": self.validate_config()
        }


# Global config manager
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get global configuration manager"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
