"""
Kafka Producer - Modern async producer with advanced features
Handles message publishing with retries, transactions, and monitoring
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
import uuid

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError, KafkaTimeoutError
from aiokafka.structs import RecordMetadata

from app.config.settings import settings
from .events import Event, EventBus
from .schemas import EventSchema, TOPIC_SCHEMAS

logger = logging.getLogger(__name__)


class KafkaProducer:
    """
    Modern Kafka producer with advanced features:
    - Async/await support
    - Automatic retries with exponential backoff
    - Transaction support
    - Schema validation
    - Metrics collection
    - Dead letter queue handling
    """
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        self.bootstrap_servers = settings.KAFKA_BOOTSTRAP_SERVERS
        self.event_bus = event_bus
        
        # Producer configuration
        self.config = {
            'bootstrap_servers': self.bootstrap_servers,
            'security_protocol': settings.KAFKA_SECURITY_PROTOCOL,
            'acks': settings.KAFKA_PRODUCER_ACKS,
            'max_batch_size': settings.KAFKA_PRODUCER_BATCH_SIZE,
            'linger_ms': settings.KAFKA_PRODUCER_LINGER_MS,
            'compression_type': settings.KAFKA_PRODUCER_COMPRESSION_TYPE,
            'max_request_size': settings.KAFKA_PRODUCER_MAX_REQUEST_SIZE,
            'enable_idempotence': True,  # Exactly-once semantics
            'transactional_id': f'xseven-producer-{uuid.uuid4().hex[:8]}',
            'request_timeout_ms': 30000,
            'transaction_timeout_ms': 120000,
        }
        
        # Add security configuration if needed
        if settings.KAFKA_SECURITY_PROTOCOL != 'PLAINTEXT':
            if settings.KAFKA_SASL_MECHANISM:
                self.config['sasl_mechanism'] = settings.KAFKA_SASL_MECHANISM
                self.config['sasl_plain_username'] = settings.KAFKA_SASL_USERNAME
                self.config['sasl_plain_password'] = settings.KAFKA_SASL_PASSWORD
        
        self.producer: Optional[AIOKafkaProducer] = None
        self._running = False
        self._transaction_active = False
        
        # Metrics
        self.metrics = {
            'messages_sent': 0,
            'messages_failed': 0,
            'bytes_sent': 0,
            'send_duration_total': 0.0,
            'retries_total': 0,
            'transactions_committed': 0,
            'transactions_aborted': 0,
        }
        
        self.logger = logging.getLogger(__name__)
    
    async def start(self) -> None:
        """Start the Kafka producer"""
        if self._running:
            return
        
        try:
            self.logger.info("🚀 Starting Kafka Producer...")
            
            self.producer = AIOKafkaProducer(**self.config)
            await self.producer.start()
            
            # Note: init_transactions is not available in aiokafka 0.12.0
            # Transactions are handled automatically when transactional_id is provided
            self._running = True
            self.logger.info("✅ Kafka Producer started successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start Kafka Producer: {e}")
            await self.stop()
            raise
    
    async def stop(self) -> None:
        """Stop the Kafka producer"""
        if not self._running:
            return
        
        try:
            self.logger.info("🛑 Stopping Kafka Producer...")
            
            # Abort any active transaction
            if self._transaction_active:
                await self.abort_transaction()
            
            if self.producer:
                await self.producer.stop()
                self.producer = None
            
            self._running = False
            self.logger.info("✅ Kafka Producer stopped successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Error stopping Kafka Producer: {e}")
    
    def is_running(self) -> bool:
        """Check if producer is running"""
        return self._running and self.producer is not None
    
    async def send(
        self,
        topic: str,
        event: Event,
        key: Optional[str] = None,
        partition: Optional[int] = None,
        headers: Optional[Dict[str, bytes]] = None,
        timeout: Optional[float] = None
    ) -> RecordMetadata:
        """
        Send an event to a Kafka topic
        
        Args:
            topic: Target topic
            event: Event to send
            key: Message key for partitioning
            partition: Specific partition (optional)
            headers: Message headers
            timeout: Send timeout
            
        Returns:
            RecordMetadata with send results
        """
        if not self.is_running():
            raise RuntimeError("Producer not running")
        
        start_time = time.time()
        
        try:
            # Validate schema if available
            message_dict = event.to_dict()
            if not EventSchema.validate_message(topic, message_dict):
                raise ValueError(f"Message validation failed for topic {topic}")
            
            # Serialize message
            message_bytes = json.dumps(message_dict).encode('utf-8')
            
            # Determine key
            if key is None and topic in TOPIC_SCHEMAS:
                key_field = TOPIC_SCHEMAS[topic].get('key_field')
                if key_field and key_field in message_dict:
                    key = str(message_dict[key_field])
            
            # Convert key to bytes if provided
            key_bytes = key.encode('utf-8') if key else None
            
            # Prepare headers
            send_headers = headers or {}
            send_headers.update({
                'event_id': event.id.encode('utf-8'),
                'event_type': event.type.value.encode('utf-8'),
                'source': event.source.encode('utf-8'),
                'timestamp': event.timestamp.isoformat().encode('utf-8'),
                'version': event.version.encode('utf-8')
            })
            
            # Send message
            future = await self.producer.send(
                topic=topic,
                value=message_bytes,
                key=key_bytes,
                partition=partition,
                headers=list(send_headers.items())
            )
            
            # Update metrics
            self.metrics['messages_sent'] += 1
            self.metrics['bytes_sent'] += len(message_bytes)
            self.metrics['send_duration_total'] += time.time() - start_time
            
            self.logger.debug(
                f"✅ Sent event {event.id} to topic {topic} "
                f"(partition: {future.partition}, offset: {future.offset})"
            )
            
            return future
            
        except Exception as e:
            self.metrics['messages_failed'] += 1
            self.logger.error(f"❌ Failed to send event {event.id} to topic {topic}: {e}")
            
            # Send to dead letter queue if configured
            await self._handle_send_failure(topic, event, e)
            raise
    
    async def send_batch(
        self,
        topic: str,
        events: List[Event],
        key_func: Optional[callable] = None,
        timeout: Optional[float] = None
    ) -> List[RecordMetadata]:
        """
        Send a batch of events to a topic
        
        Args:
            topic: Target topic
            events: List of events to send
            key_func: Function to generate keys from events
            timeout: Send timeout
            
        Returns:
            List of RecordMetadata for each sent event
        """
        if not events:
            return []
        
        tasks = []
        for event in events:
            key = key_func(event) if key_func else None
            task = self.send(topic, event, key=key, timeout=timeout)
            tasks.append(task)
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Separate successful sends from failures
            successful = []
            failed = []
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    failed.append((events[i], result))
                else:
                    successful.append(result)
            
            if failed:
                self.logger.warning(f"Batch send: {len(successful)} succeeded, {len(failed)} failed")
            
            return successful
            
        except Exception as e:
            self.logger.error(f"❌ Batch send failed: {e}")
            raise
    
    async def begin_transaction(self) -> None:
        """Begin a transaction"""
        if not self.is_running():
            raise RuntimeError("Producer not running")
        
        if self._transaction_active:
            raise RuntimeError("Transaction already active")
        
        if not self.config.get('transactional_id'):
            raise RuntimeError("Transactional producer not configured")
        
        try:
            await self.producer.begin_transaction()
            self._transaction_active = True
            self.logger.debug("🔄 Transaction started")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to begin transaction: {e}")
            raise
    
    async def commit_transaction(self) -> None:
        """Commit the current transaction"""
        if not self._transaction_active:
            raise RuntimeError("No active transaction")
        
        try:
            await self.producer.commit_transaction()
            self._transaction_active = False
            self.metrics['transactions_committed'] += 1
            self.logger.debug("✅ Transaction committed")
            
        except Exception as e:
            self.metrics['transactions_aborted'] += 1
            self.logger.error(f"❌ Failed to commit transaction: {e}")
            self._transaction_active = False
            raise
    
    async def abort_transaction(self) -> None:
        """Abort the current transaction"""
        if not self._transaction_active:
            return
        
        try:
            await self.producer.abort_transaction()
            self._transaction_active = False
            self.metrics['transactions_aborted'] += 1
            self.logger.debug("🔄 Transaction aborted")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to abort transaction: {e}")
            self._transaction_active = False
    
    async def flush(self, timeout: Optional[float] = None) -> None:
        """Flush pending messages"""
        if not self.is_running():
            return
        
        try:
            await asyncio.wait_for(self.producer.flush(), timeout=timeout)
            self.logger.debug("✅ Producer flushed")
            
        except asyncio.TimeoutError:
            self.logger.warning("⚠️ Producer flush timed out")
        except Exception as e:
            self.logger.error(f"❌ Failed to flush producer: {e}")
    
    async def _handle_send_failure(self, topic: str, event: Event, error: Exception) -> None:
        """Handle send failure by routing to dead letter queue"""
        try:
            # Create dead letter event
            dead_letter_event = Event(
                type="dead_letter_event",
                source="kafka_producer",
                data={
                    "original_topic": topic,
                    "original_event": event.to_dict(),
                    "error_message": str(error),
                    "error_type": type(error).__name__,
                    "retry_count": 0,
                    "failed_at": datetime.utcnow().isoformat()
                },
                priority="high"
            )
            
            # Try to send to dead letter queue
            if "dead.letter.queue" in settings.KAFKA_TOPICS:
                await self.send("dead.letter.queue", dead_letter_event)
                self.logger.info(f"📨 Sent failed event {event.id} to dead letter queue")
            
        except Exception as dlq_error:
            self.logger.error(f"❌ Failed to send to dead letter queue: {dlq_error}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get producer metrics"""
        avg_send_time = (
            self.metrics['send_duration_total'] / max(self.metrics['messages_sent'], 1)
        )
        
        return {
            **self.metrics,
            'avg_send_time_ms': avg_send_time * 1000,
            'success_rate': (
                self.metrics['messages_sent'] / 
                max(self.metrics['messages_sent'] + self.metrics['messages_failed'], 1)
            ),
            'running': self._running,
            'transaction_active': self._transaction_active
        }
    
    async def send_with_retry(
        self,
        topic: str,
        event: Event,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
        **kwargs
    ) -> RecordMetadata:
        """
        Send event with exponential backoff retry
        
        Args:
            topic: Target topic
            event: Event to send
            max_retries: Maximum retry attempts
            backoff_factor: Backoff multiplier
            **kwargs: Additional send arguments
            
        Returns:
            RecordMetadata on success
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return await self.send(topic, event, **kwargs)
                
            except Exception as e:
                last_exception = e
                self.metrics['retries_total'] += 1
                
                if attempt < max_retries:
                    delay = backoff_factor * (2 ** attempt)
                    self.logger.warning(
                        f"⚠️ Send attempt {attempt + 1} failed for event {event.id}, "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    self.logger.error(
                        f"❌ All {max_retries + 1} send attempts failed for event {event.id}"
                    )
        
        raise last_exception
