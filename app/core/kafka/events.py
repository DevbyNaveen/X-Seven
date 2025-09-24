"""
Event System for Kafka Integration
Defines event types, handlers, and the event bus
"""

from __future__ import annotations

import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Type, TypeVar, Generic, Callable, Awaitable
from dataclasses import dataclass, asdict
from enum import Enum
import logging

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Type variables for generic event handling
T = TypeVar('T', bound='Event')
H = TypeVar('H', bound='EventHandler')


class EventType(str, Enum):
    """Standard event types for the system"""
    CONVERSATION_STARTED = "conversation.started"
    CONVERSATION_MESSAGE = "conversation.message"
    CONVERSATION_ENDED = "conversation.ended"
    AI_RESPONSE_GENERATED = "ai.response.generated"
    AI_MODEL_SWITCHED = "ai.model.switched"
    BUSINESS_ANALYTICS_UPDATE = "business.analytics.update"
    USER_ACTION = "user.action"
    SYSTEM_ERROR = "system.error"
    HEALTH_CHECK = "system.health_check"
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"


class EventPriority(str, Enum):
    """Event priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Event:
    """Base event class for all system events"""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str
    data: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    priority: EventPriority = EventPriority.NORMAL
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    version: str = "1.0"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization"""
        return {
            "id": self.id,
            "type": self.type.value,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "data": self.data,
            "metadata": self.metadata,
            "priority": self.priority.value,
            "correlation_id": self.correlation_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "version": self.version
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create event from dictionary"""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            type=EventType(data["type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            source=data["source"],
            data=data.get("data", {}),
            metadata=data.get("metadata", {}),
            priority=EventPriority(data.get("priority", "normal")),
            correlation_id=data.get("correlation_id"),
            user_id=data.get("user_id"),
            session_id=data.get("session_id"),
            version=data.get("version", "1.0")
        )
    
    def to_json(self) -> str:
        """Convert event to JSON string"""
        return json.dumps(self.to_dict(), default=str)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Event':
        """Create event from JSON string"""
        return cls.from_dict(json.loads(json_str))


class EventHandler(ABC):
    """Abstract base class for event handlers"""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    @abstractmethod
    async def handle(self, event: Event) -> None:
        """Handle an event"""
        pass
    
    @abstractmethod
    def can_handle(self, event: Event) -> bool:
        """Check if this handler can process the event"""
        pass
    
    async def on_error(self, event: Event, error: Exception) -> None:
        """Handle errors during event processing"""
        self.logger.error(f"Error handling event {event.id}: {error}", exc_info=True)


class EventBus:
    """Event bus for managing event publishing and subscription"""
    
    def __init__(self):
        self.handlers: Dict[EventType, List[EventHandler]] = {}
        self.middleware: List[Callable[[Event], Awaitable[Event]]] = []
        self.logger = logging.getLogger(__name__)
        self._running = False
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
    
    def add_middleware(self, middleware: Callable[[Event], Awaitable[Event]]) -> None:
        """Add middleware to process events before handling"""
        self.middleware.append(middleware)
    
    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Subscribe a handler to an event type"""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)
        self.logger.info(f"Subscribed handler {handler.name} to {event_type}")
    
    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Unsubscribe a handler from an event type"""
        if event_type in self.handlers:
            self.handlers[event_type] = [h for h in self.handlers[event_type] if h != handler]
            self.logger.info(f"Unsubscribed handler {handler.name} from {event_type}")
    
    async def publish(self, event: Event) -> None:
        """Publish an event to the bus"""
        if not self._running:
            await self.start()
        
        # Apply middleware
        processed_event = event
        for middleware in self.middleware:
            try:
                processed_event = await middleware(processed_event)
            except Exception as e:
                self.logger.error(f"Middleware error: {e}", exc_info=True)
                continue
        
        await self._event_queue.put(processed_event)
        self.logger.debug(f"Published event {event.id} of type {event.type}")
    
    async def start(self) -> None:
        """Start the event bus worker"""
        if self._running:
            return
        
        self._running = True
        self._worker_task = asyncio.create_task(self._worker())
        self.logger.info("Event bus started")
    
    async def stop(self) -> None:
        """Stop the event bus worker"""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Event bus stopped")
    
    async def _worker(self) -> None:
        """Worker coroutine to process events"""
        while self._running:
            try:
                # Wait for events with timeout to allow graceful shutdown
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                await self._process_event(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Worker error: {e}", exc_info=True)
    
    async def _process_event(self, event: Event) -> None:
        """Process a single event"""
        handlers = self.handlers.get(event.type, [])
        
        if not handlers:
            self.logger.warning(f"No handlers for event type {event.type}")
            return
        
        # Process handlers concurrently
        tasks = []
        for handler in handlers:
            if handler.can_handle(event):
                task = asyncio.create_task(self._handle_with_error_handling(handler, event))
                tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _handle_with_error_handling(self, handler: EventHandler, event: Event) -> None:
        """Handle event with error handling"""
        try:
            await handler.handle(event)
            self.logger.debug(f"Handler {handler.name} processed event {event.id}")
        except Exception as e:
            self.logger.error(f"Handler {handler.name} failed for event {event.id}: {e}")
            await handler.on_error(event, e)


# Specific event types for the system
class ConversationEventHandler(EventHandler):
    """Handler for conversation events"""
    
    def can_handle(self, event: Event) -> bool:
        return event.type in [
            EventType.CONVERSATION_STARTED,
            EventType.CONVERSATION_MESSAGE,
            EventType.CONVERSATION_ENDED
        ]
    
    async def handle(self, event: Event) -> None:
        self.logger.info(f"Processing conversation event: {event.type}")
        # Implementation will be added based on specific needs


class AIResponseEventHandler(EventHandler):
    """Handler for AI response events"""
    
    def can_handle(self, event: Event) -> bool:
        return event.type in [
            EventType.AI_RESPONSE_GENERATED,
            EventType.AI_MODEL_SWITCHED
        ]
    
    async def handle(self, event: Event) -> None:
        self.logger.info(f"Processing AI response event: {event.type}")
        # Implementation will be added based on specific needs


class BusinessAnalyticsEventHandler(EventHandler):
    """Handler for business analytics events"""
    
    def can_handle(self, event: Event) -> bool:
        return event.type == EventType.BUSINESS_ANALYTICS_UPDATE
    
    async def handle(self, event: Event) -> None:
        self.logger.info(f"Processing business analytics event: {event.type}")
        # Implementation will be added based on specific needs


class SystemEventHandler(EventHandler):
    """Handler for system events"""
    
    def can_handle(self, event: Event) -> bool:
        return event.type in [
            EventType.SYSTEM_ERROR,
            EventType.HEALTH_CHECK
        ]
    
    async def handle(self, event: Event) -> None:
        self.logger.info(f"Processing system event: {event.type}")
        # Implementation will be added based on specific needs


# Event factory functions
def create_conversation_event(
    event_type: EventType,
    conversation_id: str,
    user_id: str,
    data: Dict[str, Any],
    correlation_id: Optional[str] = None
) -> Event:
    """Create a conversation event"""
    return Event(
        type=event_type,
        source="conversation_service",
        data=data,
        metadata={"conversation_id": conversation_id},
        user_id=user_id,
        correlation_id=correlation_id
    )


def create_ai_response_event(
    model_name: str,
    response_data: Dict[str, Any],
    user_id: str,
    correlation_id: Optional[str] = None
) -> Event:
    """Create an AI response event"""
    return Event(
        type=EventType.AI_RESPONSE_GENERATED,
        source="ai_service",
        data=response_data,
        metadata={"model_name": model_name},
        user_id=user_id,
        correlation_id=correlation_id
    )


def create_business_analytics_event(
    metric_name: str,
    metric_value: Any,
    business_id: str,
    correlation_id: Optional[str] = None
) -> Event:
    """Create a business analytics event"""
    return Event(
        type=EventType.BUSINESS_ANALYTICS_UPDATE,
        source="analytics_service",
        data={"metric_name": metric_name, "metric_value": metric_value},
        metadata={"business_id": business_id},
        correlation_id=correlation_id
    )


def create_system_error_event(
    error_message: str,
    error_details: Dict[str, Any],
    source: str,
    correlation_id: Optional[str] = None
) -> Event:
    """Create a system error event"""
    return Event(
        type=EventType.SYSTEM_ERROR,
        source=source,
        data={"error_message": error_message, "error_details": error_details},
        priority=EventPriority.HIGH,
        correlation_id=correlation_id
    )
