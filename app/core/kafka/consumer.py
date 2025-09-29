"""
Kafka Consumer - Modern async consumer with advanced features
Handles message consumption with automatic retries, dead letter queues, and monitoring
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import Dict, Any, Optional, List, Callable, Awaitable, Set
from datetime import datetime
import uuid

from aiokafka import AIOKafkaConsumer, TopicPartition
from aiokafka.errors import KafkaError, ConsumerStoppedError
from aiokafka.structs import ConsumerRecord

from app.config.settings import settings
from .events import Event, EventBus, EventHandler
from .schemas import EventSchema, TOPIC_SCHEMAS

logger = logging.getLogger(__name__)


class MessageProcessor:
    """Base class for message processors"""
    
    async def process(self, message: ConsumerRecord) -> bool:
        """
        Process a message
        
        Args:
            message: Kafka message to process
            
        Returns:
            True if processing succeeded, False otherwise
        """
        raise NotImplementedError


class KafkaConsumer:
    """
    Modern Kafka consumer with advanced features:
    - Async/await support
    - Automatic retries with exponential backoff
    - Dead letter queue handling
    - Manual offset management
    - Metrics collection
    - Graceful shutdown
    """
    
    def __init__(
        self,
        topic: str,
        group_id: str,
        event_bus: Optional[EventBus] = None,
        processor: Optional[MessageProcessor] = None
    ):
        self.topic = topic
        self.group_id = group_id
        self.event_bus = event_bus
        self.processor = processor
        
        # Consumer configuration
        self.config = {
            'bootstrap_servers': settings.KAFKA_BOOTSTRAP_SERVERS,
            'group_id': group_id,
            'security_protocol': settings.KAFKA_SECURITY_PROTOCOL,
            'auto_offset_reset': settings.KAFKA_CONSUMER_AUTO_OFFSET_RESET,
            'enable_auto_commit': settings.KAFKA_CONSUMER_ENABLE_AUTO_COMMIT,
            'max_poll_records': settings.KAFKA_CONSUMER_MAX_POLL_RECORDS,
            'session_timeout_ms': settings.KAFKA_CONSUMER_SESSION_TIMEOUT_MS,
            'heartbeat_interval_ms': settings.KAFKA_CONSUMER_HEARTBEAT_INTERVAL_MS,
            'fetch_min_bytes': 1,
            'fetch_max_wait_ms': 500,
            'max_partition_fetch_bytes': 1048576,
            'isolation_level': 'read_committed',  # For transactional support
        }
        
        # Add security configuration if needed
        if settings.KAFKA_SECURITY_PROTOCOL != 'PLAINTEXT':
            if settings.KAFKA_SASL_MECHANISM:
                self.config['sasl_mechanism'] = settings.KAFKA_SASL_MECHANISM
                self.config['sasl_plain_username'] = settings.KAFKA_SASL_USERNAME
                self.config['sasl_plain_password'] = settings.KAFKA_SASL_PASSWORD
        
        self.consumer: Optional[AIOKafkaConsumer] = None
        self._running = False
        self._consuming = False
        self._shutdown_event = asyncio.Event()
        
        # Message handlers
        self.handlers: List[EventHandler] = []
        
        # Metrics
        self.metrics = {
            'messages_consumed': 0,
            'messages_processed': 0,
            'messages_failed': 0,
            'processing_time_total': 0.0,
            'retries_total': 0,
            'dead_letters_sent': 0,
            'last_processed_offset': {},
            'consumer_lag': 0,
        }
        
        # Error handling
        self.max_retries = 3
        self.retry_backoff = 1.0
        self.dead_letter_topic = "dead.letter.queue"
        
        self.logger = logging.getLogger(f"{__name__}.{topic}")
    
    def add_handler(self, handler: EventHandler) -> None:
        """Add an event handler"""
        self.handlers.append(handler)
        self.logger.info(f"Added handler {handler.name} for topic {self.topic}")
    
    def remove_handler(self, handler: EventHandler) -> None:
        """Remove an event handler"""
        if handler in self.handlers:
            self.handlers.remove(handler)
            self.logger.info(f"Removed handler {handler.name} for topic {self.topic}")
    
    async def start(self) -> None:
        """Start the Kafka consumer"""
        if self._running:
            return
        
        try:
            self.logger.info(f"🚀 Starting Kafka Consumer for topic: {self.topic}")
            
            self.consumer = AIOKafkaConsumer(
                self.topic,
                **self.config
            )
            
            await self.consumer.start()
            self._running = True
            
            self.logger.info(f"✅ Kafka Consumer started for topic: {self.topic}")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start Kafka Consumer for {self.topic}: {e}")
            await self.stop()
            raise
    
    async def stop(self) -> None:
        """Stop the Kafka consumer"""
        if not self._running:
            return
        
        try:
            self.logger.info(f"🛑 Stopping Kafka Consumer for topic: {self.topic}")
            
            # Signal shutdown
            self._shutdown_event.set()
            
            # Wait for consumption to stop
            if self._consuming:
                await asyncio.sleep(1.0)  # Give time for graceful shutdown
            
            if self.consumer:
                await self.consumer.stop()
                self.consumer = None
            
            self._running = False
            self.logger.info(f"✅ Kafka Consumer stopped for topic: {self.topic}")
            
        except Exception as e:
            self.logger.error(f"❌ Error stopping Kafka Consumer for {self.topic}: {e}")
    
    def is_running(self) -> bool:
        """Check if consumer is running"""
        return self._running and self.consumer is not None
    
    async def consume(self) -> None:
        """Main consumption loop with robust retry mechanism"""
        if not self.is_running():
            raise RuntimeError("Consumer not running")
        
        self._consuming = True
        self.logger.info(f"🔄 Starting consumption loop for topic: {self.topic}")
        
        # Retry configuration with exponential backoff
        max_retries = 5
        base_retry_delay = 1.0
        max_retry_delay = 30.0
        consecutive_failures = 0
        last_successful_poll = time.time()
        
        try:
            while self._running and not self._shutdown_event.is_set():
                try:
                    # Check if we need to reconnect due to extended outage
                    if time.time() - last_successful_poll > 60.0 and consecutive_failures >= 3:
                        self.logger.warning(f"Connection issues detected for {self.topic}, attempting reconnection")
                        await self._reconnect()
                    
                    # Poll for messages with timeout
                    msg_pack = await asyncio.wait_for(
                        self.consumer.getmany(timeout_ms=1000),
                        timeout=2.0
                    )
                    
                    # Reset failure counter on successful poll
                    consecutive_failures = 0
                    last_successful_poll = time.time()
                    
                    if not msg_pack:
                        continue
                    
                    # Process messages by partition
                    for topic_partition, messages in msg_pack.items():
                        await self._process_partition_messages(topic_partition, messages)
                    
                except asyncio.TimeoutError:
                    # Timeout is expected, continue polling
                    continue
                    
                except ConsumerStoppedError:
                    self.logger.info("Consumer stopped, exiting consumption loop")
                    break
                    
                except Exception as e:
                    consecutive_failures += 1
                    
                    # Calculate retry delay with exponential backoff and jitter
                    retry_attempt = min(consecutive_failures, max_retries)
                    delay = min(base_retry_delay * (2 ** (retry_attempt - 1)), max_retry_delay)
                    jitter = delay * 0.2 * (random.random() * 2 - 1)  # +/- 20% jitter
                    actual_delay = max(0.1, delay + jitter)
                    
                    self.logger.error(
                        f"❌ Error in consumption loop (attempt {consecutive_failures}): {e}. "
                        f"Retrying in {actual_delay:.2f}s"
                    )
                    
                    # If we've had too many consecutive failures, try to reconnect
                    if consecutive_failures >= max_retries:
                        self.logger.warning(
                            f"Too many consecutive failures ({consecutive_failures}) for {self.topic}, "
                            f"attempting to reconnect"
                        )
                        try:
                            await self._reconnect()
                            consecutive_failures = 0  # Reset counter on successful reconnect
                        except Exception as reconnect_error:
                            self.logger.error(f"Reconnection failed: {reconnect_error}")
                    
                    await asyncio.sleep(actual_delay)  # Backoff before retrying
        
        finally:
            self._consuming = False
            self.logger.info(f"✅ Consumption loop ended for topic: {self.topic}")
    
    async def _reconnect(self) -> None:
        """Attempt to reconnect the consumer"""
        self.logger.info(f"🔄 Attempting to reconnect consumer for topic: {self.topic}")
        
        try:
            # Stop current consumer
            if self.consumer:
                await self.consumer.stop()
                self.consumer = None
            
            # Create and start a new consumer
            self.consumer = AIOKafkaConsumer(
                self.topic,
                **self.config
            )
            
            await self.consumer.start()
            self.logger.info(f"✅ Successfully reconnected consumer for topic: {self.topic}")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to reconnect consumer for {self.topic}: {e}")
            raise
    
    async def _process_partition_messages(
        self,
        topic_partition: TopicPartition,
        messages: List[ConsumerRecord]
    ) -> None:
        """Process messages from a partition"""
        for message in messages:
            try:
                await self._process_message(message)
                
                # Commit offset after successful processing
                if not settings.KAFKA_CONSUMER_ENABLE_AUTO_COMMIT:
                    await self.consumer.commit({topic_partition: message.offset + 1})
                
                # Update metrics
                self.metrics['last_processed_offset'][topic_partition.partition] = message.offset
                
            except Exception as e:
                self.logger.error(
                    f"❌ Failed to process message at offset {message.offset}: {e}"
                )
                # Continue processing other messages
    
    async def _process_message(self, message: ConsumerRecord) -> None:
        """Process a single message"""
        start_time = time.time()
        
        try:
            self.metrics['messages_consumed'] += 1
            
            # Deserialize message
            event = await self._deserialize_message(message)
            if not event:
                return
            
            # Use custom processor if available
            if self.processor:
                success = await self.processor.process(message)
                if success:
                    self.metrics['messages_processed'] += 1
                else:
                    self.metrics['messages_failed'] += 1
                    await self._handle_processing_failure(message, Exception("Processor returned False"))
                return
            
            # Process with event handlers
            await self._process_with_handlers(event, message)
            
            # Publish to event bus if available
            if self.event_bus:
                await self.event_bus.publish(event)
            
            self.metrics['messages_processed'] += 1
            self.metrics['processing_time_total'] += time.time() - start_time
            
            self.logger.debug(
                f"✅ Processed message {event.id} from offset {message.offset}"
            )
            
        except Exception as e:
            self.metrics['messages_failed'] += 1
            self.logger.error(f"❌ Failed to process message at offset {message.offset}: {e}")
            await self._handle_processing_failure(message, e)
    
    async def _deserialize_message(self, message: ConsumerRecord) -> Optional[Event]:
        """Deserialize Kafka message to Event"""
        try:
            # Parse JSON message
            message_data = json.loads(message.value.decode('utf-8'))
            
            # Validate schema if available
            if not EventSchema.validate_message(self.topic, message_data):
                self.logger.warning(f"Schema validation failed for message at offset {message.offset}")
                return None
            
            # Create Event object
            event = Event.from_dict(message_data)
            
            # Add message metadata
            event.metadata.update({
                'kafka_topic': message.topic,
                'kafka_partition': message.partition,
                'kafka_offset': message.offset,
                'kafka_timestamp': message.timestamp,
                'kafka_key': message.key.decode('utf-8') if message.key else None
            })
            
            return event
            
        except Exception as e:
            self.logger.error(f"❌ Failed to deserialize message at offset {message.offset}: {e}")
            return None
    
    async def _process_with_handlers(self, event: Event, message: ConsumerRecord) -> None:
        """Process event with registered handlers"""
        if not self.handlers:
            return
        
        # Find applicable handlers
        applicable_handlers = [h for h in self.handlers if h.can_handle(event)]
        
        if not applicable_handlers:
            self.logger.debug(f"No handlers found for event type {event.type}")
            return
        
        # Process with handlers concurrently
        tasks = []
        for handler in applicable_handlers:
            task = asyncio.create_task(self._handle_with_retry(handler, event))
            tasks.append(task)
        
        # Wait for all handlers to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check for failures
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                handler = applicable_handlers[i]
                self.logger.error(f"Handler {handler.name} failed for event {event.id}: {result}")
    
    async def _handle_with_retry(self, handler: EventHandler, event: Event) -> None:
        """Handle event with retry logic"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                await handler.handle(event)
                return  # Success
                
            except Exception as e:
                last_exception = e
                self.metrics['retries_total'] += 1
                
                if attempt < self.max_retries:
                    delay = self.retry_backoff * (2 ** attempt)
                    self.logger.warning(
                        f"⚠️ Handler {handler.name} attempt {attempt + 1} failed for event {event.id}, "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    self.logger.error(
                        f"❌ All {self.max_retries + 1} attempts failed for handler {handler.name} "
                        f"and event {event.id}"
                    )
        
        # All retries failed, call error handler
        if last_exception:
            await handler.on_error(event, last_exception)
    
    async def _handle_processing_failure(self, message: ConsumerRecord, error: Exception) -> None:
        """Handle message processing failure"""
        try:
            # Create dead letter event
            dead_letter_data = {
                'id': str(uuid.uuid4()),
                'original_topic': message.topic,
                'original_partition': message.partition,
                'original_offset': message.offset,
                'original_timestamp': datetime.fromtimestamp(message.timestamp / 1000).isoformat(),
                'error_message': str(error),
                'error_type': type(error).__name__,
                'retry_count': 0,
                'original_payload': message.value,
                'failed_at': datetime.utcnow().isoformat(),
                'metadata': {
                    'consumer_group': self.group_id,
                    'topic': self.topic
                },
                'version': '1.0'
            }
            
            # Send to dead letter queue if available
            if self.dead_letter_topic in settings.KAFKA_TOPICS and self.event_bus:
                dead_letter_event = Event(
                    type="dead_letter_event",
                    source="kafka_consumer",
                    data=dead_letter_data,
                    priority="high"
                )
                
                await self.event_bus.publish(dead_letter_event)
                self.metrics['dead_letters_sent'] += 1
                
                self.logger.info(
                    f"📨 Sent failed message from offset {message.offset} to dead letter queue"
                )
            
        except Exception as dlq_error:
            self.logger.error(f"❌ Failed to send to dead letter queue: {dlq_error}")
    
    async def seek_to_beginning(self) -> None:
        """Seek to the beginning of all partitions"""
        if not self.is_running():
            raise RuntimeError("Consumer not running")
        
        partitions = self.consumer.assignment()
        await self.consumer.seek_to_beginning(*partitions)
        self.logger.info(f"✅ Seeked to beginning for topic {self.topic}")
    
    async def seek_to_end(self) -> None:
        """Seek to the end of all partitions"""
        if not self.is_running():
            raise RuntimeError("Consumer not running")
        
        partitions = self.consumer.assignment()
        await self.consumer.seek_to_end(*partitions)
        self.logger.info(f"✅ Seeked to end for topic {self.topic}")
    
    async def seek_to_offset(self, partition: int, offset: int) -> None:
        """Seek to a specific offset in a partition"""
        if not self.is_running():
            raise RuntimeError("Consumer not running")
        
        topic_partition = TopicPartition(self.topic, partition)
        self.consumer.seek(topic_partition, offset)
        self.logger.info(f"✅ Seeked to offset {offset} in partition {partition}")
    
    async def get_committed_offsets(self) -> Dict[int, int]:
        """Get committed offsets for all partitions"""
        if not self.is_running():
            raise RuntimeError("Consumer not running")
        
        partitions = self.consumer.assignment()
        committed = await self.consumer.committed(*partitions)
        
        return {tp.partition: offset for tp, offset in committed.items() if offset is not None}
    
    async def get_current_positions(self) -> Dict[int, int]:
        """Get current positions for all partitions"""
        if not self.is_running():
            raise RuntimeError("Consumer not running")
        
        partitions = self.consumer.assignment()
        positions = {}
        
        for tp in partitions:
            position = await self.consumer.position(tp)
            positions[tp.partition] = position
        
        return positions
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get consumer metrics"""
        avg_processing_time = (
            self.metrics['processing_time_total'] / max(self.metrics['messages_processed'], 1)
        )
        
        success_rate = (
            self.metrics['messages_processed'] / 
            max(self.metrics['messages_consumed'], 1)
        )
        
        return {
            **self.metrics,
            'avg_processing_time_ms': avg_processing_time * 1000,
            'success_rate': success_rate,
            'running': self._running,
            'consuming': self._consuming,
            'topic': self.topic,
            'group_id': self.group_id,
            'handlers_count': len(self.handlers)
        }
    
    async def pause_partitions(self, partitions: Optional[List[int]] = None) -> None:
        """Pause consumption from specific partitions"""
        if not self.is_running():
            raise RuntimeError("Consumer not running")
        
        if partitions is None:
            topic_partitions = self.consumer.assignment()
        else:
            topic_partitions = [TopicPartition(self.topic, p) for p in partitions]
        
        self.consumer.pause(*topic_partitions)
        self.logger.info(f"⏸️ Paused partitions: {[tp.partition for tp in topic_partitions]}")
    
    async def resume_partitions(self, partitions: Optional[List[int]] = None) -> None:
        """Resume consumption from specific partitions"""
        if not self.is_running():
            raise RuntimeError("Consumer not running")
        
        if partitions is None:
            topic_partitions = self.consumer.assignment()
        else:
            topic_partitions = [TopicPartition(self.topic, p) for p in partitions]
        
        self.consumer.resume(*topic_partitions)
        self.logger.info(f"▶️ Resumed partitions: {[tp.partition for tp in topic_partitions]}")


class BatchMessageProcessor(MessageProcessor):
    """Processor for handling messages in batches"""
    
    def __init__(self, batch_size: int = 100, flush_interval: float = 5.0):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.batch: List[ConsumerRecord] = []
        self.last_flush = time.time()
        self.logger = logging.getLogger(__name__)
    
    async def process(self, message: ConsumerRecord) -> bool:
        """Add message to batch and process when batch is full or timeout occurs"""
        self.batch.append(message)
        
        should_flush = (
            len(self.batch) >= self.batch_size or
            time.time() - self.last_flush >= self.flush_interval
        )
        
        if should_flush:
            return await self._flush_batch()
        
        return True
    
    async def _flush_batch(self) -> bool:
        """Process the current batch"""
        if not self.batch:
            return True
        
        try:
            await self.process_batch(self.batch)
            self.batch.clear()
            self.last_flush = time.time()
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Batch processing failed: {e}")
            self.batch.clear()
            self.last_flush = time.time()
            return False
    
    async def process_batch(self, messages: List[ConsumerRecord]) -> None:
        """Override this method to implement batch processing logic"""
        raise NotImplementedError
