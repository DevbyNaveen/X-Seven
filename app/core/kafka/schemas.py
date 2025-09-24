"""
Avro Schemas for Kafka Messages
Defines message schemas for type safety and evolution
"""

from __future__ import annotations

import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

# Avro schema definitions
CONVERSATION_EVENT_SCHEMA = {
    "type": "record",
    "name": "ConversationEvent",
    "namespace": "com.xseven.events",
    "fields": [
        {"name": "id", "type": "string"},
        {"name": "type", "type": "string"},
        {"name": "timestamp", "type": "string"},
        {"name": "source", "type": "string"},
        {"name": "conversation_id", "type": "string"},
        {"name": "user_id", "type": ["null", "string"], "default": None},
        {"name": "session_id", "type": ["null", "string"], "default": None},
        {"name": "message_content", "type": ["null", "string"], "default": None},
        {"name": "message_type", "type": ["null", "string"], "default": None},
        {"name": "agent_type", "type": ["null", "string"], "default": None},
        {"name": "metadata", "type": {"type": "map", "values": "string"}},
        {"name": "correlation_id", "type": ["null", "string"], "default": None},
        {"name": "priority", "type": "string", "default": "normal"},
        {"name": "version", "type": "string", "default": "1.0"}
    ]
}

AI_RESPONSE_EVENT_SCHEMA = {
    "type": "record",
    "name": "AIResponseEvent",
    "namespace": "com.xseven.events",
    "fields": [
        {"name": "id", "type": "string"},
        {"name": "type", "type": "string"},
        {"name": "timestamp", "type": "string"},
        {"name": "source", "type": "string"},
        {"name": "model_name", "type": "string"},
        {"name": "model_provider", "type": "string"},
        {"name": "user_id", "type": ["null", "string"], "default": None},
        {"name": "conversation_id", "type": ["null", "string"], "default": None},
        {"name": "prompt", "type": "string"},
        {"name": "response", "type": "string"},
        {"name": "tokens_used", "type": ["null", "int"], "default": None},
        {"name": "response_time_ms", "type": ["null", "int"], "default": None},
        {"name": "cost_usd", "type": ["null", "double"], "default": None},
        {"name": "metadata", "type": {"type": "map", "values": "string"}},
        {"name": "correlation_id", "type": ["null", "string"], "default": None},
        {"name": "priority", "type": "string", "default": "normal"},
        {"name": "version", "type": "string", "default": "1.0"}
    ]
}

BUSINESS_ANALYTICS_EVENT_SCHEMA = {
    "type": "record",
    "name": "BusinessAnalyticsEvent",
    "namespace": "com.xseven.events",
    "fields": [
        {"name": "id", "type": "string"},
        {"name": "type", "type": "string"},
        {"name": "timestamp", "type": "string"},
        {"name": "source", "type": "string"},
        {"name": "business_id", "type": "string"},
        {"name": "metric_name", "type": "string"},
        {"name": "metric_value", "type": ["null", "string", "int", "double", "boolean"]},
        {"name": "metric_type", "type": "string"},
        {"name": "dimension", "type": {"type": "map", "values": "string"}},
        {"name": "aggregation_period", "type": ["null", "string"], "default": None},
        {"name": "metadata", "type": {"type": "map", "values": "string"}},
        {"name": "correlation_id", "type": ["null", "string"], "default": None},
        {"name": "priority", "type": "string", "default": "normal"},
        {"name": "version", "type": "string", "default": "1.0"}
    ]
}

SYSTEM_MONITORING_EVENT_SCHEMA = {
    "type": "record",
    "name": "SystemMonitoringEvent",
    "namespace": "com.xseven.events",
    "fields": [
        {"name": "id", "type": "string"},
        {"name": "type", "type": "string"},
        {"name": "timestamp", "type": "string"},
        {"name": "source", "type": "string"},
        {"name": "service_name", "type": "string"},
        {"name": "metric_name", "type": "string"},
        {"name": "metric_value", "type": "double"},
        {"name": "unit", "type": "string"},
        {"name": "tags", "type": {"type": "map", "values": "string"}},
        {"name": "alert_level", "type": ["null", "string"], "default": None},
        {"name": "metadata", "type": {"type": "map", "values": "string"}},
        {"name": "correlation_id", "type": ["null", "string"], "default": None},
        {"name": "priority", "type": "string", "default": "normal"},
        {"name": "version", "type": "string", "default": "1.0"}
    ]
}

DEAD_LETTER_EVENT_SCHEMA = {
    "type": "record",
    "name": "DeadLetterEvent",
    "namespace": "com.xseven.events",
    "fields": [
        {"name": "id", "type": "string"},
        {"name": "original_topic", "type": "string"},
        {"name": "original_partition", "type": "int"},
        {"name": "original_offset", "type": "long"},
        {"name": "original_timestamp", "type": "string"},
        {"name": "error_message", "type": "string"},
        {"name": "error_type", "type": "string"},
        {"name": "retry_count", "type": "int"},
        {"name": "original_payload", "type": "bytes"},
        {"name": "failed_at", "type": "string"},
        {"name": "metadata", "type": {"type": "map", "values": "string"}},
        {"name": "version", "type": "string", "default": "1.0"}
    ]
}


class EventSchema:
    """Schema registry for event types"""
    
    SCHEMAS = {
        "conversation.events": CONVERSATION_EVENT_SCHEMA,
        "ai.responses": AI_RESPONSE_EVENT_SCHEMA,
        "business.analytics": BUSINESS_ANALYTICS_EVENT_SCHEMA,
        "system.monitoring": SYSTEM_MONITORING_EVENT_SCHEMA,
        "dead.letter.queue": DEAD_LETTER_EVENT_SCHEMA
    }
    
    @classmethod
    def get_schema(cls, topic: str) -> Dict[str, Any]:
        """Get schema for a topic"""
        return cls.SCHEMAS.get(topic, {})
    
    @classmethod
    def validate_message(cls, topic: str, message: Dict[str, Any]) -> bool:
        """Validate message against schema"""
        schema = cls.get_schema(topic)
        if not schema:
            return True  # No schema validation
        
        # Basic validation - in production, use proper Avro validation
        required_fields = [field["name"] for field in schema.get("fields", []) 
                          if "default" not in field and field.get("type") != ["null", "string"]]
        
        return all(field in message for field in required_fields)


# Pydantic models for type safety
class ConversationEvent(BaseModel):
    """Conversation event model"""
    id: str
    type: str
    timestamp: str
    source: str
    conversation_id: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    message_content: Optional[str] = None
    message_type: Optional[str] = None
    agent_type: Optional[str] = None
    metadata: Dict[str, str] = Field(default_factory=dict)
    correlation_id: Optional[str] = None
    priority: str = "normal"
    version: str = "1.0"


class AIResponseEvent(BaseModel):
    """AI response event model"""
    id: str
    type: str
    timestamp: str
    source: str
    model_name: str
    model_provider: str
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    prompt: str
    response: str
    tokens_used: Optional[int] = None
    response_time_ms: Optional[int] = None
    cost_usd: Optional[float] = None
    metadata: Dict[str, str] = Field(default_factory=dict)
    correlation_id: Optional[str] = None
    priority: str = "normal"
    version: str = "1.0"


class BusinessAnalyticsEvent(BaseModel):
    """Business analytics event model"""
    id: str
    type: str
    timestamp: str
    source: str
    business_id: str
    metric_name: str
    metric_value: Any
    metric_type: str
    dimension: Dict[str, str] = Field(default_factory=dict)
    aggregation_period: Optional[str] = None
    metadata: Dict[str, str] = Field(default_factory=dict)
    correlation_id: Optional[str] = None
    priority: str = "normal"
    version: str = "1.0"


class SystemMonitoringEvent(BaseModel):
    """System monitoring event model"""
    id: str
    type: str
    timestamp: str
    source: str
    service_name: str
    metric_name: str
    metric_value: float
    unit: str
    tags: Dict[str, str] = Field(default_factory=dict)
    alert_level: Optional[str] = None
    metadata: Dict[str, str] = Field(default_factory=dict)
    correlation_id: Optional[str] = None
    priority: str = "normal"
    version: str = "1.0"


class DeadLetterEvent(BaseModel):
    """Dead letter event model"""
    id: str
    original_topic: str
    original_partition: int
    original_offset: int
    original_timestamp: str
    error_message: str
    error_type: str
    retry_count: int
    original_payload: bytes
    failed_at: str
    metadata: Dict[str, str] = Field(default_factory=dict)
    version: str = "1.0"


# Schema evolution utilities
class SchemaEvolution:
    """Utilities for schema evolution and compatibility"""
    
    @staticmethod
    def is_compatible(old_schema: Dict[str, Any], new_schema: Dict[str, Any]) -> bool:
        """Check if schemas are compatible"""
        # Basic compatibility check - in production, use proper Avro compatibility
        old_fields = {field["name"]: field for field in old_schema.get("fields", [])}
        new_fields = {field["name"]: field for field in new_schema.get("fields", [])}
        
        # Check if all required old fields exist in new schema
        for field_name, field_def in old_fields.items():
            if field_name not in new_fields:
                if "default" not in field_def:
                    return False
        
        return True
    
    @staticmethod
    def migrate_message(message: Dict[str, Any], from_version: str, to_version: str) -> Dict[str, Any]:
        """Migrate message between schema versions"""
        # Implementation would depend on specific migration rules
        migrated = message.copy()
        migrated["version"] = to_version
        return migrated


# Topic configuration
TOPIC_SCHEMAS = {
    "conversation.events": {
        "schema": CONVERSATION_EVENT_SCHEMA,
        "model": ConversationEvent,
        "key_field": "conversation_id"
    },
    "ai.responses": {
        "schema": AI_RESPONSE_EVENT_SCHEMA,
        "model": AIResponseEvent,
        "key_field": "conversation_id"
    },
    "business.analytics": {
        "schema": BUSINESS_ANALYTICS_EVENT_SCHEMA,
        "model": BusinessAnalyticsEvent,
        "key_field": "business_id"
    },
    "system.monitoring": {
        "schema": SYSTEM_MONITORING_EVENT_SCHEMA,
        "model": SystemMonitoringEvent,
        "key_field": "service_name"
    },
    "dead.letter.queue": {
        "schema": DEAD_LETTER_EVENT_SCHEMA,
        "model": DeadLetterEvent,
        "key_field": "original_topic"
    }
}
