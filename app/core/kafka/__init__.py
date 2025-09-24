"""
Kafka Integration Module for X-SevenAI
Modern event-driven architecture with comprehensive features
"""

from .manager import KafkaManager
from .producer import KafkaProducer
from .consumer import KafkaConsumer
from .events import EventBus, Event, EventHandler
from .schemas import EventSchema, ConversationEvent, AIResponseEvent, BusinessAnalyticsEvent
from .monitoring import KafkaMonitor
from .health import KafkaHealthCheck

__all__ = [
    "KafkaManager",
    "KafkaProducer", 
    "KafkaConsumer",
    "EventBus",
    "Event",
    "EventHandler",
    "EventSchema",
    "ConversationEvent",
    "AIResponseEvent", 
    "BusinessAnalyticsEvent",
    "KafkaMonitor",
    "KafkaHealthCheck"
]
