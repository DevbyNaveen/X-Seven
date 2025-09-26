"""
Kafka Integration with X-SevenAI Services
Provides event-driven messaging patterns and service integration
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
import json

from .manager import KafkaManager, get_kafka_manager
from .events import Event, EventType, EventHandler, create_conversation_event, create_ai_response_event, create_business_analytics_event
from .producer import KafkaProducer
from .consumer import KafkaConsumer

logger = logging.getLogger(__name__)


# Global flag indicating whether Kafka is available
_KAFKA_ENABLED = True

class ConversationEventIntegration(EventHandler):
    """Integration handler for conversation events"""
    
    def __init__(self, redis_manager=None, supabase_client=None):
        super().__init__("conversation_integration")
        self.redis_manager = redis_manager
        self.supabase_client = supabase_client
    
    def can_handle(self, event: Event) -> bool:
        return event.type in [
            EventType.CONVERSATION_STARTED,
            EventType.CONVERSATION_MESSAGE,
            EventType.CONVERSATION_ENDED
        ]
    
    async def handle(self, event: Event) -> None:
        """Handle conversation events"""
        try:
            if event.type == EventType.CONVERSATION_STARTED:
                await self._handle_conversation_started(event)
            elif event.type == EventType.CONVERSATION_MESSAGE:
                await self._handle_conversation_message(event)
            elif event.type == EventType.CONVERSATION_ENDED:
                await self._handle_conversation_ended(event)
                
        except Exception as e:
            self.logger.error(f"Error handling conversation event {event.id}: {e}")
            raise
    
    async def _handle_conversation_started(self, event: Event) -> None:
        """Handle conversation started event"""
        conversation_id = event.data.get('conversation_id')
        user_id = event.user_id
        
        self.logger.info(f"Conversation started: {conversation_id} for user {user_id}")
        
        # Store in Redis for quick access
        if self.redis_manager:
            await self.redis_manager.store_conversation_state(
                conversation_id,
                {
                    'status': 'active',
                    'started_at': event.timestamp.isoformat(),
                    'user_id': user_id,
                    'metadata': event.data
                }
            )
        
        # Store in Supabase for persistence
        if self.supabase_client:
            try:
                self.supabase_client.table('conversations').insert({
                    'id': conversation_id,
                    'user_id': user_id,
                    'status': 'active',
                    'started_at': event.timestamp.isoformat(),
                    'metadata': event.data
                }).execute()
            except Exception as e:
                self.logger.error(f"Failed to store conversation in Supabase: {e}")
    
    async def _handle_conversation_message(self, event: Event) -> None:
        """Handle conversation message event"""
        conversation_id = event.data.get('conversation_id')
        message_content = event.data.get('message_content')
        message_type = event.data.get('message_type', 'user')
        
        self.logger.info(f"Message in conversation {conversation_id}: {message_type}")
        
        # Update conversation state in Redis
        if self.redis_manager:
            await self.redis_manager.update_conversation_state(
                conversation_id,
                {
                    'last_message_at': event.timestamp.isoformat(),
                    'message_count': await self._increment_message_count(conversation_id)
                }
            )
        
        # Store message in Supabase
        if self.supabase_client:
            try:
                self.supabase_client.table('conversation_messages').insert({
                    'conversation_id': conversation_id,
                    'content': message_content,
                    'message_type': message_type,
                    'timestamp': event.timestamp.isoformat(),
                    'metadata': event.metadata
                }).execute()
            except Exception as e:
                self.logger.error(f"Failed to store message in Supabase: {e}")
    
    async def _handle_conversation_ended(self, event: Event) -> None:
        """Handle conversation ended event"""
        conversation_id = event.data.get('conversation_id')
        
        self.logger.info(f"Conversation ended: {conversation_id}")
        
        # Update status in Redis
        if self.redis_manager:
            await self.redis_manager.update_conversation_state(
                conversation_id,
                {
                    'status': 'ended',
                    'ended_at': event.timestamp.isoformat()
                }
            )
        
        # Update in Supabase
        if self.supabase_client:
            try:
                self.supabase_client.table('conversations').update({
                    'status': 'ended',
                    'ended_at': event.timestamp.isoformat()
                }).eq('id', conversation_id).execute()
            except Exception as e:
                self.logger.error(f"Failed to update conversation in Supabase: {e}")
    
    async def _increment_message_count(self, conversation_id: str) -> int:
        """Increment and return message count for conversation"""
        if self.redis_manager:
            return await self.redis_manager.increment_counter(f"conversation:{conversation_id}:messages")
        return 1


class AIResponseEventIntegration(EventHandler):
    """Integration handler for AI response events"""
    
    def __init__(self, analytics_service=None, cost_tracker=None):
        super().__init__("ai_response_integration")
        self.analytics_service = analytics_service
        self.cost_tracker = cost_tracker
    
    def can_handle(self, event: Event) -> bool:
        return event.type in [
            EventType.AI_RESPONSE_GENERATED,
            EventType.AI_MODEL_SWITCHED
        ]
    
    async def handle(self, event: Event) -> None:
        """Handle AI response events"""
        try:
            if event.type == EventType.AI_RESPONSE_GENERATED:
                await self._handle_ai_response_generated(event)
            elif event.type == EventType.AI_MODEL_SWITCHED:
                await self._handle_model_switched(event)
                
        except Exception as e:
            self.logger.error(f"Error handling AI response event {event.id}: {e}")
            raise
    
    async def _handle_ai_response_generated(self, event: Event) -> None:
        """Handle AI response generated event"""
        model_name = event.data.get('model_name')
        tokens_used = event.data.get('tokens_used', 0)
        response_time = event.data.get('response_time_ms', 0)
        cost = event.data.get('cost_usd', 0.0)
        
        self.logger.info(f"AI response generated: {model_name}, tokens: {tokens_used}")
        
        # Track costs
        if self.cost_tracker and cost > 0:
            await self.cost_tracker.record_usage(
                model_name=model_name,
                tokens=tokens_used,
                cost=cost,
                user_id=event.user_id,
                timestamp=event.timestamp
            )
        
        # Update analytics
        if self.analytics_service:
            await self.analytics_service.record_ai_usage(
                model=model_name,
                tokens=tokens_used,
                response_time=response_time,
                user_id=event.user_id
            )
    
    async def _handle_model_switched(self, event: Event) -> None:
        """Handle model switched event"""
        old_model = event.data.get('old_model')
        new_model = event.data.get('new_model')
        reason = event.data.get('reason', 'user_request')
        
        self.logger.info(f"Model switched: {old_model} -> {new_model} ({reason})")
        
        # Track model switching patterns
        if self.analytics_service:
            await self.analytics_service.record_model_switch(
                from_model=old_model,
                to_model=new_model,
                reason=reason,
                user_id=event.user_id
            )


class BusinessAnalyticsEventIntegration(EventHandler):
    """Integration handler for business analytics events"""
    
    def __init__(self, analytics_db=None, dashboard_service=None):
        super().__init__("business_analytics_integration")
        self.analytics_db = analytics_db
        self.dashboard_service = dashboard_service
    
    def can_handle(self, event: Event) -> bool:
        return event.type == EventType.BUSINESS_ANALYTICS_UPDATE
    
    async def handle(self, event: Event) -> None:
        """Handle business analytics events"""
        try:
            metric_name = event.data.get('metric_name')
            metric_value = event.data.get('metric_value')
            business_id = event.metadata.get('business_id')
            
            self.logger.info(f"Analytics update: {metric_name} = {metric_value} for business {business_id}")
            
            # Store in analytics database
            if self.analytics_db:
                await self.analytics_db.store_metric(
                    business_id=business_id,
                    metric_name=metric_name,
                    metric_value=metric_value,
                    timestamp=event.timestamp,
                    metadata=event.data
                )
            
            # Update real-time dashboard
            if self.dashboard_service:
                await self.dashboard_service.update_metric(
                    business_id=business_id,
                    metric_name=metric_name,
                    metric_value=metric_value
                )
                
        except Exception as e:
            self.logger.error(f"Error handling business analytics event {event.id}: {e}")
            raise


class KafkaServiceIntegrator:
    """Main service integrator for Kafka with X-SevenAI services"""
    
    def __init__(self):
        self.kafka_manager: Optional[KafkaManager] = None
        self.integrations: Dict[str, EventHandler] = {}
        self.event_publishers: Dict[str, Callable] = {}
        self._initialized = False
        
        self.logger = logging.getLogger(__name__)
    
    async def initialize(
        self,
        redis_manager=None,
        supabase_client=None,
        analytics_service=None,
        cost_tracker=None,
        dashboard_service=None
    ) -> None:
        """Initialize the service integrator and attempt to connect to Kafka.
        If the connection fails, set the global _KAFKA_ENABLED flag to False so the rest of the
        system can continue operating without Kafka.
        """
        global _KAFKA_ENABLED  # Declare global at the top of the function
        # Attempt to connect to Kafka
        try:
            self.logger.info("🚀 Initializing Kafka Service Integrator (connection test)...")
            self.kafka_manager = await get_kafka_manager()
            _KAFKA_ENABLED = True
            self.logger.info("✅ Kafka connection successful")
        except Exception as e:
            _KAFKA_ENABLED = False
            self.logger.warning(f"⚠️ Kafka initialization failed (continuing without Kafka): {e}")
            return  # Skip further setup

        # If already initialized, nothing to do
        if self._initialized:
            return

        try:
            self.logger.info("🚀 Initializing Kafka Service Integrator (full setup)...")
            # Initialize integrations
            self.integrations['conversation'] = ConversationEventIntegration(
                redis_manager=redis_manager,
                supabase_client=supabase_client
            )
            self.integrations['ai_response'] = AIResponseEventIntegration(
                analytics_service=analytics_service,
                cost_tracker=cost_tracker
            )
            self.integrations['business_analytics'] = BusinessAnalyticsEventIntegration(
                analytics_db=analytics_service,
                dashboard_service=dashboard_service
            )
            # Register event handlers with event bus
            if self.kafka_manager.event_bus:
                for event_type in EventType:
                    for integration in self.integrations.values():
                        if integration.can_handle(Event(type=event_type, source="test")):
                            self.kafka_manager.event_bus.subscribe(event_type, integration)
            # Setup event publishers
            self._setup_event_publishers()
            self._initialized = True
            self.logger.info("✅ Kafka Service Integrator fully initialized")
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize Kafka Service Integrator: {e}")
            raise
    
    async def start_health_monitoring(self) -> None:
        """Start background health monitoring for Kafka"""
        async def health_monitor():
            while True:
                try:
                    await asyncio.sleep(30)  # Check every 30 seconds
                    if hasattr(self, 'kafka_manager') and self.kafka_manager:
                        await self.kafka_manager.health_check_and_reconnect()
                except Exception as e:
                    self.logger.error(f"Health monitoring error: {e}")

        # Start the monitoring task
        self._health_monitor_task = asyncio.create_task(health_monitor())
        self.logger.info("✅ Kafka health monitoring started")
    
    def _setup_event_publishers(self) -> None:
        """Setup event publishing functions"""
        self.event_publishers = {
            'conversation_started': self._publish_conversation_started,
            'conversation_message': self._publish_conversation_message,
            'conversation_ended': self._publish_conversation_ended,
            'ai_response_generated': self._publish_ai_response_generated,
            'business_analytics_update': self._publish_business_analytics_update,
        }
    
    async def _publish_conversation_started(
        self,
        conversation_id: str,
        user_id: str,
        metadata: Dict[str, Any] = None
    ) -> None:
        """Publish conversation started event"""
        event = create_conversation_event(
            event_type=EventType.CONVERSATION_STARTED,
            conversation_id=conversation_id,
            user_id=user_id,
            data={
                'conversation_id': conversation_id,
                'action': 'started',
                **(metadata or {})
            }
        )
        
        await self.kafka_manager.publish_event("conversation.events", event, key=conversation_id)
    
    async def _publish_conversation_message(
        self,
        conversation_id: str,
        user_id: str,
        message_content: str,
        message_type: str = "user",
        metadata: Dict[str, Any] = None
    ) -> None:
        """Publish conversation message event"""
        event = create_conversation_event(
            event_type=EventType.CONVERSATION_MESSAGE,
            conversation_id=conversation_id,
            user_id=user_id,
            data={
                'conversation_id': conversation_id,
                'message_content': message_content,
                'message_type': message_type,
                'action': 'message',
                **(metadata or {})
            }
        )
        
        await self.kafka_manager.publish_event("conversation.events", event, key=conversation_id)
    
    async def _publish_conversation_ended(
        self,
        conversation_id: str,
        user_id: str,
        metadata: Dict[str, Any] = None
    ) -> None:
        """Publish conversation ended event"""
        event = create_conversation_event(
            event_type=EventType.CONVERSATION_ENDED,
            conversation_id=conversation_id,
            user_id=user_id,
            data={
                'conversation_id': conversation_id,
                'action': 'ended',
                **(metadata or {})
            }
        )
        
        await self.kafka_manager.publish_event("conversation.events", event, key=conversation_id)
    
    async def _publish_ai_response_generated(
        self,
        model_name: str,
        response_data: Dict[str, Any],
        user_id: str,
        conversation_id: str = None
    ) -> None:
        """Publish AI response generated event"""
        event = create_ai_response_event(
            model_name=model_name,
            response_data=response_data,
            user_id=user_id
        )
        
        if conversation_id:
            event.metadata['conversation_id'] = conversation_id
        
        await self.kafka_manager.publish_event("ai.responses", event, key=conversation_id or user_id)
    
    async def _publish_business_analytics_update(
        self,
        metric_name: str,
        metric_value: Any,
        business_id: str,
        metadata: Dict[str, Any] = None
    ) -> None:
        """Publish business analytics update event"""
        event = create_business_analytics_event(
            metric_name=metric_name,
            metric_value=metric_value,
            business_id=business_id
        )
        
        if metadata:
            event.data.update(metadata)
        
        await self.kafka_manager.publish_event("business.analytics", event, key=business_id)
    
    async def publish_event(self, event_type: str, **kwargs) -> None:
        """Generic event publisher"""
        if not self._initialized:
            raise RuntimeError("Service integrator not initialized")
        
        publisher = self.event_publishers.get(event_type)
        if not publisher:
            raise ValueError(f"Unknown event type: {event_type}")
        
        await publisher(**kwargs)
    
    def get_integration(self, name: str) -> Optional[EventHandler]:
        """Get integration by name"""
        return self.integrations.get(name)
    
    async def shutdown(self) -> None:
        """Shutdown the service integrator and health monitoring"""
        if hasattr(self, '_health_monitor_task') and self._health_monitor_task:
            self._health_monitor_task.cancel()
            try:
                await self._health_monitor_task
            except asyncio.CancelledError:
                pass

        if self.kafka_manager:
            await self.kafka_manager.stop()

        self._initialized = False
        self.logger.info("✅ Kafka Service Integrator shutdown complete")


# Global service integrator instance
_service_integrator: Optional[KafkaServiceIntegrator] = None


async def get_kafka_service_integrator() -> KafkaServiceIntegrator:
    """Get the global Kafka service integrator"""
    global _service_integrator
    
    if _service_integrator is None:
        _service_integrator = KafkaServiceIntegrator()
    
    return _service_integrator


async def initialize_kafka_integration(
    redis_manager=None,
    supabase_client=None,
    analytics_service=None,
    cost_tracker=None,
    dashboard_service=None
) -> KafkaServiceIntegrator:
    """Initialize Kafka integration with services and health monitoring"""
    integrator = await get_kafka_service_integrator()

    if not integrator._initialized:
        await integrator.initialize(
            redis_manager=redis_manager,
            supabase_client=supabase_client,
            analytics_service=analytics_service,
            cost_tracker=cost_tracker,
            dashboard_service=dashboard_service
        )

        # Start health monitoring
        await integrator.start_health_monitoring()

    return integrator


# Convenience functions for event publishing
async def publish_conversation_started(conversation_id: str, user_id: str, **kwargs) -> None:
    """Publish conversation started event"""
    if not _KAFKA_ENABLED:
        logger.debug("Kafka disabled – skipping publish_conversation_started")
        return
    integrator = await get_kafka_service_integrator()
    await integrator.publish_event('conversation_started', 
                                 conversation_id=conversation_id, 
                                 user_id=user_id, 
                                 **kwargs)


async def publish_conversation_message(conversation_id: str, user_id: str, message_content: str, **kwargs) -> None:
    """Publish conversation message event"""
    if not _KAFKA_ENABLED:
        logger.debug("Kafka disabled – skipping publish_conversation_message")
        return
    integrator = await get_kafka_service_integrator()
    await integrator.publish_event('conversation_message',
                                 conversation_id=conversation_id,
                                 user_id=user_id,
                                 message_content=message_content,
                                 **kwargs)


async def publish_ai_response_generated(model_name: str, response_data: Dict[str, Any], user_id: str, **kwargs) -> None:
    """Publish AI response generated event"""
    if not _KAFKA_ENABLED:
        logger.debug("Kafka disabled – skipping publish_ai_response_generated")
        return
    integrator = await get_kafka_service_integrator()
    await integrator.publish_event('ai_response_generated',
                                 model_name=model_name,
                                 response_data=response_data,
                                 user_id=user_id,
                                 **kwargs)


async def publish_business_analytics_update(metric_name: str, metric_value: Any, business_id: str, **kwargs) -> None:
        if not _KAFKA_ENABLED:
            logger.debug("Kafka disabled – skipping publish_business_analytics_update")
            return
        integrator = await get_kafka_service_integrator()
        await integrator.publish_event('business_analytics_update',
                                 metric_name=metric_name,
                                 metric_value=metric_value,
                                 business_id=business_id,
                                 **kwargs)
