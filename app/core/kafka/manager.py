"""
Kafka Manager - Central coordination for Kafka operations
Handles topic management, producer/consumer lifecycle, and health monitoring
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional, Any, Set
from contextlib import asynccontextmanager
import json

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.errors import TopicAlreadyExistsError, KafkaError
from kafka.errors import KafkaTimeoutError

from app.config.settings import settings
from .producer import KafkaProducer
from .consumer import KafkaConsumer
from .events import EventBus, Event
from .schemas import EventSchema, TOPIC_SCHEMAS
from .monitoring import KafkaMonitor
from .health import KafkaHealthCheck

logger = logging.getLogger(__name__)


class KafkaManager:
    """
    Central Kafka manager for the X-SevenAI system
    Coordinates all Kafka operations including topic management, 
    producer/consumer lifecycle, and health monitoring
    """
    
    def __init__(self):
        self.bootstrap_servers = settings.KAFKA_BOOTSTRAP_SERVERS
        self.security_protocol = settings.KAFKA_SECURITY_PROTOCOL
        
        # Core components
        self.admin_client: Optional[AIOKafkaAdminClient] = None
        self.producer: Optional[KafkaProducer] = None
        self.consumers: Dict[str, KafkaConsumer] = {}
        self.event_bus: Optional[EventBus] = None
        self.monitor: Optional[KafkaMonitor] = None
        self.health_check: Optional[KafkaHealthCheck] = None
        
        # State management
        self._initialized = False
        self._running = False
        self._topics_created: Set[str] = set()
        self._consumer_tasks: Dict[str, asyncio.Task] = {}
        
        self.logger = logging.getLogger(__name__)
    
    async def initialize(self) -> None:
        """Initialize Kafka manager with retry logic"""
        if self._initialized:
            return

        max_retries = 3
        retry_delay = 5  # seconds

        for attempt in range(max_retries):
            try:
                self.logger.info(f"🚀 Initializing Kafka Manager... (attempt {attempt + 1}/{max_retries})")

                # Initialize admin client
                await self._init_admin_client()

                # Create topics
                await self._create_topics()

                # Initialize event bus
                self.event_bus = EventBus()
                await self.event_bus.start()

                # Initialize producer
                self.producer = KafkaProducer(self.event_bus)
                await self.producer.start()

                # Initialize monitoring
                self.monitor = KafkaMonitor()
                await self.monitor.start()

                # Initialize health check
                self.health_check = KafkaHealthCheck(self)

                self._initialized = True
                self.logger.info("✅ Kafka Manager initialized successfully")
                return

            except Exception as e:
                self.logger.warning(f"❌ Failed to initialize Kafka Manager (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    self.logger.info(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
        
        # If we reach here, all attempts failed
        self.logger.error("❌ All retry attempts failed. Kafka Manager will be disabled.")
        raise RuntimeError("Failed to initialize Kafka Manager after all retry attempts")
    
    async def health_check_and_reconnect(self) -> bool:
        """Perform health check and attempt to reconnect if Kafka is down"""
        if not self.health_check:
            return False

        try:
            is_healthy = await self.health_check.perform_check()
            if is_healthy and not self._initialized:
                self.logger.info("Kafka is now available, attempting to reinitialize...")
                await self.initialize()
                return True
            elif not is_healthy and self._initialized:
                self.logger.warning("Kafka is no longer available, shutting down...")
                await self.stop()
                return False
            return is_healthy
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
    
    async def start(self) -> None:
        """Start the Kafka manager and all services"""
        if not self._initialized:
            await self.initialize()
        
        if self._running:
            return
        
        try:
            self.logger.info("🚀 Starting Kafka Manager...")
            
            # Start consumers for all configured topics
            await self._start_consumers()
            
            # Start monitoring
            if self.monitor:
                await self.monitor.start_monitoring()
            
            self._running = True
            self.logger.info("✅ Kafka Manager started successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start Kafka Manager: {e}")
            await self.stop()
            raise
    
    async def stop(self) -> None:
        """Stop the Kafka manager and all services"""
        if not self._running:
            return
        
        self.logger.info("🛑 Stopping Kafka Manager...")
        
        try:
            # Stop consumers
            await self._stop_consumers()
            
            # Stop monitoring
            if self.monitor:
                await self.monitor.stop_monitoring()
            
            # Stop producer
            if self.producer:
                await self.producer.stop()
            
            # Stop event bus
            if self.event_bus:
                await self.event_bus.stop()
            
            self._running = False
            self.logger.info("✅ Kafka Manager stopped successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Error stopping Kafka Manager: {e}")
        finally:
            await self.cleanup()
    
    async def cleanup(self) -> None:
        """Clean up resources"""
        try:
            # Close admin client
            if self.admin_client:
                await self.admin_client.close()
                self.admin_client = None
            
            # Cancel consumer tasks
            for task in self._consumer_tasks.values():
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
            self._consumer_tasks.clear()
            self.consumers.clear()
            self._initialized = False
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
    
    async def _init_admin_client(self) -> None:
        """Initialize Kafka admin client"""
        self.admin_client = AIOKafkaAdminClient(
            bootstrap_servers=self.bootstrap_servers,
            security_protocol=self.security_protocol,
            request_timeout_ms=30000,
            connections_max_idle_ms=540000
        )
        
        await self.admin_client.start()
        self.logger.info("✅ Kafka admin client initialized")
        
        # Verify connection by listing topics
        try:
            await self.admin_client.list_topics()
        except Exception as e:
            self.logger.error(f"Failed to verify Kafka connection: {e}")
            raise
    
    async def _create_topics(self) -> None:
        """Create Kafka topics based on configuration"""
        if not self.admin_client:
            raise RuntimeError("Admin client not initialized")
        
        topics_to_create = []
        
        for topic_name, topic_config in settings.KAFKA_TOPICS.items():
            if topic_name not in self._topics_created:
                new_topic = NewTopic(
                    name=topic_name,
                    num_partitions=topic_config["partitions"],
                    replication_factor=topic_config["replication_factor"],
                    topic_configs=topic_config.get("config", {})
                )
                topics_to_create.append(new_topic)
        
        if topics_to_create:
            try:
                await self.admin_client.create_topics(topics_to_create)
                for topic in topics_to_create:
                    self._topics_created.add(topic.name)
                    self.logger.info(f"✅ Created topic: {topic.name}")
                    
            except TopicAlreadyExistsError:
                # Topics already exist, which is fine
                for topic in topics_to_create:
                    self._topics_created.add(topic.name)
                    self.logger.info(f"✅ Topic already exists: {topic.name}")
            except Exception as e:
                self.logger.error(f"❌ Failed to create topics: {e}")
                raise
    
    async def _start_consumers(self) -> None:
        """Start consumers for all configured topics"""
        for topic_name in settings.KAFKA_TOPICS.keys():
            if topic_name not in self.consumers:
                consumer = KafkaConsumer(
                    topic=topic_name,
                    group_id=f"{settings.KAFKA_CONSUMER_GROUP_ID}-{topic_name}",
                    event_bus=self.event_bus
                )
                
                self.consumers[topic_name] = consumer
                await consumer.start()
                
                # Start consumer task
                task = asyncio.create_task(consumer.consume())
                self._consumer_tasks[topic_name] = task
                
                self.logger.info(f"✅ Started consumer for topic: {topic_name}")
    
    async def _stop_consumers(self) -> None:
        """Stop all consumers"""
        for topic_name, consumer in self.consumers.items():
            try:
                await consumer.stop()
                
                # Cancel consumer task
                if topic_name in self._consumer_tasks:
                    task = self._consumer_tasks[topic_name]
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                    del self._consumer_tasks[topic_name]
                
                self.logger.info(f"✅ Stopped consumer for topic: {topic_name}")
                
            except Exception as e:
                self.logger.error(f"❌ Error stopping consumer for {topic_name}: {e}")
    
    async def publish_event(self, topic: str, event: Event, key: Optional[str] = None) -> None:
        """Publish an event to a topic"""
        if not self.producer:
            raise RuntimeError("Producer not initialized")
        
        await self.producer.send(topic, event, key)
    
    async def get_topic_metadata(self, topic: str) -> Dict[str, Any]:
        """Get metadata for a topic"""
        if not self.admin_client:
            raise RuntimeError("Admin client not initialized")
        
        try:
            metadata = await self.admin_client.describe_topics([topic])
            return metadata.get(topic, {})
        except Exception as e:
            self.logger.error(f"Failed to get metadata for topic {topic}: {e}")
            return {}
    
    async def get_consumer_group_info(self, group_id: str) -> Dict[str, Any]:
        """Get consumer group information"""
        if not self.admin_client:
            raise RuntimeError("Admin client not initialized")
        
        try:
            # This would require additional implementation for consumer group management
            return {"group_id": group_id, "status": "active"}
        except Exception as e:
            self.logger.error(f"Failed to get consumer group info for {group_id}: {e}")
            return {}
    
    async def reset_consumer_offset(self, topic: str, partition: int, offset: int) -> None:
        """Reset consumer offset for a topic partition"""
        # This would require stopping the consumer, resetting offset, and restarting
        self.logger.warning("Consumer offset reset not implemented yet")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of Kafka manager"""
        if self.health_check:
            return self.health_check.get_status()
        
        return {
            "status": "unknown",
            "initialized": self._initialized,
            "running": self._running,
            "topics_created": len(self._topics_created),
            "active_consumers": len(self.consumers),
            "producer_active": self.producer is not None and self.producer.is_running()
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get Kafka metrics"""
        if self.monitor:
            return self.monitor.get_metrics()
        
        return {}
    
    @asynccontextmanager
    async def transaction(self):
        """Context manager for transactional operations"""
        if not self.producer:
            raise RuntimeError("Producer not initialized")
        
        # Begin transaction
        await self.producer.begin_transaction()
        
        try:
            yield
            # Commit transaction
            await self.producer.commit_transaction()
        except Exception as e:
            # Abort transaction
            await self.producer.abort_transaction()
            raise e
    
    async def create_topic(self, name: str, partitions: int = 1, replication_factor: int = 1, 
                          config: Optional[Dict[str, str]] = None) -> None:
        """Create a new topic dynamically"""
        if not self.admin_client:
            raise RuntimeError("Admin client not initialized")
        
        new_topic = NewTopic(
            name=name,
            num_partitions=partitions,
            replication_factor=replication_factor,
            topic_configs=config or {}
        )
        
        try:
            await self.admin_client.create_topics([new_topic])
            self._topics_created.add(name)
            self.logger.info(f"✅ Created topic: {name}")
        except TopicAlreadyExistsError:
            self.logger.info(f"✅ Topic already exists: {name}")
        except Exception as e:
            self.logger.error(f"❌ Failed to create topic {name}: {e}")
            raise
    
    async def delete_topic(self, name: str) -> None:
        """Delete a topic"""
        if not self.admin_client:
            raise RuntimeError("Admin client not initialized")
        
        try:
            await self.admin_client.delete_topics([name])
            self._topics_created.discard(name)
            self.logger.info(f"✅ Deleted topic: {name}")
        except Exception as e:
            self.logger.error(f"❌ Failed to delete topic {name}: {e}")
            raise


# Global Kafka manager instance
_kafka_manager: Optional[KafkaManager] = None


async def get_kafka_manager() -> KafkaManager:
    """Get the global Kafka manager instance"""
    global _kafka_manager
    
    if _kafka_manager is None:
        _kafka_manager = KafkaManager()
        await _kafka_manager.initialize()
    
    return _kafka_manager


async def cleanup_kafka_manager() -> None:
    """Cleanup the global Kafka manager instance"""
    global _kafka_manager
    
    if _kafka_manager:
        await _kafka_manager.stop()
        _kafka_manager = None
