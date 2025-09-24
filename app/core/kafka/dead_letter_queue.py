"""
Dead Letter Queue Implementation
Handles failed messages with retry logic, error analysis, and recovery mechanisms
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import uuid

from .events import Event, EventType, EventHandler
from .producer import KafkaProducer
from .consumer import KafkaConsumer, MessageProcessor
from .schemas import DeadLetterEvent

logger = logging.getLogger(__name__)


class FailureReason(str, Enum):
    """Failure reason categories"""
    DESERIALIZATION_ERROR = "deserialization_error"
    SCHEMA_VALIDATION_ERROR = "schema_validation_error"
    PROCESSING_ERROR = "processing_error"
    TIMEOUT_ERROR = "timeout_error"
    DEPENDENCY_ERROR = "dependency_error"
    UNKNOWN_ERROR = "unknown_error"


class RetryStrategy(str, Enum):
    """Retry strategy types"""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    FIXED_DELAY = "fixed_delay"
    LINEAR_BACKOFF = "linear_backoff"
    NO_RETRY = "no_retry"


@dataclass
class DeadLetterMessage:
    """Dead letter message structure"""
    id: str
    original_topic: str
    original_partition: int
    original_offset: int
    original_key: Optional[str]
    original_value: bytes
    original_headers: Dict[str, bytes]
    original_timestamp: datetime
    
    failure_reason: FailureReason
    error_message: str
    error_details: Dict[str, Any]
    
    retry_count: int
    max_retries: int
    retry_strategy: RetryStrategy
    next_retry_at: Optional[datetime]
    
    created_at: datetime
    last_retry_at: Optional[datetime]
    
    metadata: Dict[str, Any]


class DeadLetterQueueManager:
    """
    Dead Letter Queue Manager
    Handles failed message processing with sophisticated retry and recovery mechanisms
    """
    
    def __init__(self, kafka_producer: KafkaProducer):
        self.producer = kafka_producer
        self.dead_letter_topic = "dead.letter.queue"
        
        # Configuration
        self.default_max_retries = 3
        self.default_retry_strategy = RetryStrategy.EXPONENTIAL_BACKOFF
        self.retry_base_delay = 60  # seconds
        self.max_retry_delay = 3600  # 1 hour
        
        # Message storage and tracking
        self.dead_letters: Dict[str, DeadLetterMessage] = {}
        self.retry_queue: List[str] = []
        
        # Retry task
        self._retry_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Error analysis
        self.error_patterns: Dict[str, int] = {}
        self.failure_stats: Dict[FailureReason, int] = {reason: 0 for reason in FailureReason}
        
        self.logger = logging.getLogger(__name__)
    
    async def start(self) -> None:
        """Start the dead letter queue manager"""
        if self._running:
            return
        
        self._running = True
        self._retry_task = asyncio.create_task(self._retry_loop())
        self.logger.info("🚀 Dead Letter Queue Manager started")
    
    async def stop(self) -> None:
        """Stop the dead letter queue manager"""
        self._running = False
        
        if self._retry_task and not self._retry_task.done():
            self._retry_task.cancel()
            try:
                await self._retry_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("✅ Dead Letter Queue Manager stopped")
    
    async def send_to_dead_letter_queue(
        self,
        original_topic: str,
        original_partition: int,
        original_offset: int,
        original_key: Optional[str],
        original_value: bytes,
        original_headers: Dict[str, bytes],
        original_timestamp: datetime,
        error: Exception,
        failure_reason: FailureReason = FailureReason.UNKNOWN_ERROR,
        max_retries: Optional[int] = None,
        retry_strategy: Optional[RetryStrategy] = None
    ) -> str:
        """Send a failed message to the dead letter queue"""
        
        # Generate unique ID for dead letter message
        dlq_id = str(uuid.uuid4())
        
        # Analyze error
        error_details = self._analyze_error(error)
        
        # Create dead letter message
        dead_letter_msg = DeadLetterMessage(
            id=dlq_id,
            original_topic=original_topic,
            original_partition=original_partition,
            original_offset=original_offset,
            original_key=original_key,
            original_value=original_value,
            original_headers=original_headers,
            original_timestamp=original_timestamp,
            
            failure_reason=failure_reason,
            error_message=str(error),
            error_details=error_details,
            
            retry_count=0,
            max_retries=max_retries or self.default_max_retries,
            retry_strategy=retry_strategy or self.default_retry_strategy,
            next_retry_at=self._calculate_next_retry_time(0, retry_strategy or self.default_retry_strategy),
            
            created_at=datetime.utcnow(),
            last_retry_at=None,
            
            metadata={
                'source_consumer_group': 'unknown',
                'processing_attempts': 1
            }
        )
        
        # Store dead letter message
        self.dead_letters[dlq_id] = dead_letter_msg
        
        # Add to retry queue if retries are configured
        if dead_letter_msg.max_retries > 0:
            self.retry_queue.append(dlq_id)
        
        # Update statistics
        self.failure_stats[failure_reason] += 1
        error_pattern = self._extract_error_pattern(error)
        self.error_patterns[error_pattern] = self.error_patterns.get(error_pattern, 0) + 1
        
        # Send to Kafka dead letter topic
        await self._send_to_kafka_dlq(dead_letter_msg)
        
        self.logger.warning(
            f"📨 Message sent to DLQ: {dlq_id} from {original_topic}:{original_partition}:{original_offset} "
            f"- Reason: {failure_reason.value} - Error: {str(error)[:100]}"
        )
        
        return dlq_id
    
    async def _send_to_kafka_dlq(self, dead_letter_msg: DeadLetterMessage) -> None:
        """Send dead letter message to Kafka topic"""
        try:
            # Create event for dead letter message
            dlq_event = Event(
                type=EventType.SYSTEM_ERROR,
                source="dead_letter_queue",
                data={
                    'dlq_id': dead_letter_msg.id,
                    'original_topic': dead_letter_msg.original_topic,
                    'original_partition': dead_letter_msg.original_partition,
                    'original_offset': dead_letter_msg.original_offset,
                    'failure_reason': dead_letter_msg.failure_reason.value,
                    'error_message': dead_letter_msg.error_message,
                    'retry_count': dead_letter_msg.retry_count,
                    'max_retries': dead_letter_msg.max_retries,
                    'created_at': dead_letter_msg.created_at.isoformat()
                },
                metadata={
                    'original_key': dead_letter_msg.original_key,
                    'original_payload_size': len(dead_letter_msg.original_value),
                    'error_details': dead_letter_msg.error_details
                },
                priority="high"
            )
            
            await self.producer.send(self.dead_letter_topic, dlq_event, key=dead_letter_msg.id)
            
        except Exception as e:
            self.logger.error(f"❌ Failed to send dead letter message to Kafka: {e}")
    
    async def _retry_loop(self) -> None:
        """Main retry processing loop"""
        while self._running:
            try:
                await self._process_retry_queue()
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"❌ Error in retry loop: {e}")
                await asyncio.sleep(5)
    
    async def _process_retry_queue(self) -> None:
        """Process messages in the retry queue"""
        if not self.retry_queue:
            return
        
        current_time = datetime.utcnow()
        ready_for_retry = []
        
        # Find messages ready for retry
        for dlq_id in self.retry_queue[:]:
            dead_letter_msg = self.dead_letters.get(dlq_id)
            if not dead_letter_msg:
                self.retry_queue.remove(dlq_id)
                continue
            
            if (dead_letter_msg.next_retry_at and 
                dead_letter_msg.next_retry_at <= current_time and
                dead_letter_msg.retry_count < dead_letter_msg.max_retries):
                ready_for_retry.append(dlq_id)
        
        # Process retry attempts
        for dlq_id in ready_for_retry:
            await self._attempt_retry(dlq_id)
    
    async def _attempt_retry(self, dlq_id: str) -> None:
        """Attempt to retry a dead letter message"""
        dead_letter_msg = self.dead_letters.get(dlq_id)
        if not dead_letter_msg:
            return
        
        try:
            self.logger.info(
                f"🔄 Attempting retry {dead_letter_msg.retry_count + 1}/{dead_letter_msg.max_retries} "
                f"for message {dlq_id}"
            )
            
            # Attempt to reprocess the message
            success = await self._reprocess_message(dead_letter_msg)
            
            if success:
                # Successful retry
                self.logger.info(f"✅ Successfully retried message {dlq_id}")
                self.retry_queue.remove(dlq_id)
                del self.dead_letters[dlq_id]
                
                # Send success event
                await self._send_retry_success_event(dead_letter_msg)
                
            else:
                # Failed retry
                dead_letter_msg.retry_count += 1
                dead_letter_msg.last_retry_at = datetime.utcnow()
                
                if dead_letter_msg.retry_count >= dead_letter_msg.max_retries:
                    # Max retries reached
                    self.logger.error(f"❌ Max retries reached for message {dlq_id}")
                    self.retry_queue.remove(dlq_id)
                    await self._send_max_retries_reached_event(dead_letter_msg)
                else:
                    # Schedule next retry
                    dead_letter_msg.next_retry_at = self._calculate_next_retry_time(
                        dead_letter_msg.retry_count,
                        dead_letter_msg.retry_strategy
                    )
                    
                    self.logger.warning(
                        f"⚠️ Retry failed for message {dlq_id}, next retry at {dead_letter_msg.next_retry_at}"
                    )
        
        except Exception as e:
            self.logger.error(f"❌ Error during retry attempt for {dlq_id}: {e}")
    
    async def _reprocess_message(self, dead_letter_msg: DeadLetterMessage) -> bool:
        """Attempt to reprocess a dead letter message"""
        try:
            # This is a simplified reprocessing - in a real implementation,
            # you would need to recreate the original processing context
            
            # For now, we'll just simulate reprocessing
            # In practice, you might:
            # 1. Recreate the original consumer record
            # 2. Apply the original message handlers
            # 3. Check if external dependencies are now available
            
            # Simulate processing delay
            await asyncio.sleep(0.1)
            
            # For demonstration, we'll have a 30% success rate for retries
            import random
            return random.random() < 0.3
            
        except Exception as e:
            self.logger.error(f"❌ Reprocessing failed: {e}")
            return False
    
    def _calculate_next_retry_time(self, retry_count: int, strategy: RetryStrategy) -> datetime:
        """Calculate next retry time based on strategy"""
        base_delay = self.retry_base_delay
        
        if strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = min(base_delay * (2 ** retry_count), self.max_retry_delay)
        elif strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = min(base_delay * (retry_count + 1), self.max_retry_delay)
        elif strategy == RetryStrategy.FIXED_DELAY:
            delay = base_delay
        else:  # NO_RETRY
            delay = 0
        
        return datetime.utcnow() + timedelta(seconds=delay)
    
    def _analyze_error(self, error: Exception) -> Dict[str, Any]:
        """Analyze error and extract useful information"""
        return {
            'error_type': type(error).__name__,
            'error_module': getattr(error, '__module__', 'unknown'),
            'error_args': str(error.args) if error.args else '',
            'is_retryable': self._is_retryable_error(error),
            'suggested_action': self._suggest_action(error)
        }
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Determine if an error is retryable"""
        # Network/connectivity errors are usually retryable
        retryable_errors = [
            'ConnectionError',
            'TimeoutError',
            'TemporaryFailure',
            'ServiceUnavailable'
        ]
        
        error_type = type(error).__name__
        return any(retryable in error_type for retryable in retryable_errors)
    
    def _suggest_action(self, error: Exception) -> str:
        """Suggest action based on error type"""
        error_type = type(error).__name__
        
        suggestions = {
            'ConnectionError': 'Check network connectivity and service availability',
            'TimeoutError': 'Increase timeout or check service performance',
            'ValidationError': 'Review message schema and data format',
            'SerializationError': 'Check message serialization format',
            'AuthenticationError': 'Verify credentials and permissions',
            'AuthorizationError': 'Check access permissions for topic/resource'
        }
        
        return suggestions.get(error_type, 'Review error details and logs')
    
    def _extract_error_pattern(self, error: Exception) -> str:
        """Extract error pattern for analysis"""
        error_msg = str(error).lower()
        
        # Common error patterns
        if 'connection' in error_msg:
            return 'connection_error'
        elif 'timeout' in error_msg:
            return 'timeout_error'
        elif 'serialization' in error_msg or 'deserialization' in error_msg:
            return 'serialization_error'
        elif 'validation' in error_msg:
            return 'validation_error'
        elif 'permission' in error_msg or 'authorization' in error_msg:
            return 'permission_error'
        else:
            return 'unknown_error'
    
    async def _send_retry_success_event(self, dead_letter_msg: DeadLetterMessage) -> None:
        """Send event when retry succeeds"""
        try:
            success_event = Event(
                type=EventType.SYSTEM_ERROR,  # Could create a new type for recovery
                source="dead_letter_queue",
                data={
                    'event_type': 'retry_success',
                    'dlq_id': dead_letter_msg.id,
                    'original_topic': dead_letter_msg.original_topic,
                    'retry_count': dead_letter_msg.retry_count,
                    'total_retry_time_seconds': (
                        datetime.utcnow() - dead_letter_msg.created_at
                    ).total_seconds()
                },
                priority="normal"
            )
            
            await self.producer.send("system.monitoring", success_event)
            
        except Exception as e:
            self.logger.error(f"❌ Failed to send retry success event: {e}")
    
    async def _send_max_retries_reached_event(self, dead_letter_msg: DeadLetterMessage) -> None:
        """Send event when max retries are reached"""
        try:
            max_retries_event = Event(
                type=EventType.SYSTEM_ERROR,
                source="dead_letter_queue",
                data={
                    'event_type': 'max_retries_reached',
                    'dlq_id': dead_letter_msg.id,
                    'original_topic': dead_letter_msg.original_topic,
                    'failure_reason': dead_letter_msg.failure_reason.value,
                    'total_retry_attempts': dead_letter_msg.retry_count,
                    'suggested_action': dead_letter_msg.error_details.get('suggested_action', 'Manual intervention required')
                },
                priority="high"
            )
            
            await self.producer.send("system.monitoring", max_retries_event)
            
        except Exception as e:
            self.logger.error(f"❌ Failed to send max retries event: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get dead letter queue statistics"""
        total_dead_letters = len(self.dead_letters)
        pending_retries = len(self.retry_queue)
        
        # Calculate retry success rate
        total_retries = sum(msg.retry_count for msg in self.dead_letters.values())
        successful_retries = total_retries - pending_retries  # Simplified calculation
        
        return {
            'total_dead_letters': total_dead_letters,
            'pending_retries': pending_retries,
            'total_retry_attempts': total_retries,
            'estimated_successful_retries': max(0, successful_retries),
            'failure_reasons': dict(self.failure_stats),
            'error_patterns': dict(self.error_patterns),
            'oldest_dead_letter': min(
                (msg.created_at for msg in self.dead_letters.values()),
                default=None
            ),
            'retry_queue_size': len(self.retry_queue)
        }
    
    def get_dead_letter_details(self, dlq_id: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific dead letter message"""
        dead_letter_msg = self.dead_letters.get(dlq_id)
        if not dead_letter_msg:
            return None
        
        return {
            'id': dead_letter_msg.id,
            'original_topic': dead_letter_msg.original_topic,
            'original_partition': dead_letter_msg.original_partition,
            'original_offset': dead_letter_msg.original_offset,
            'failure_reason': dead_letter_msg.failure_reason.value,
            'error_message': dead_letter_msg.error_message,
            'error_details': dead_letter_msg.error_details,
            'retry_count': dead_letter_msg.retry_count,
            'max_retries': dead_letter_msg.max_retries,
            'next_retry_at': dead_letter_msg.next_retry_at.isoformat() if dead_letter_msg.next_retry_at else None,
            'created_at': dead_letter_msg.created_at.isoformat(),
            'last_retry_at': dead_letter_msg.last_retry_at.isoformat() if dead_letter_msg.last_retry_at else None,
            'metadata': dead_letter_msg.metadata
        }
    
    async def manual_retry(self, dlq_id: str) -> bool:
        """Manually trigger retry for a dead letter message"""
        dead_letter_msg = self.dead_letters.get(dlq_id)
        if not dead_letter_msg:
            return False
        
        self.logger.info(f"🔄 Manual retry triggered for message {dlq_id}")
        
        # Reset retry timing and add to queue if not already there
        dead_letter_msg.next_retry_at = datetime.utcnow()
        if dlq_id not in self.retry_queue:
            self.retry_queue.append(dlq_id)
        
        return True
    
    async def delete_dead_letter(self, dlq_id: str) -> bool:
        """Delete a dead letter message (manual cleanup)"""
        if dlq_id in self.dead_letters:
            del self.dead_letters[dlq_id]
            
            if dlq_id in self.retry_queue:
                self.retry_queue.remove(dlq_id)
            
            self.logger.info(f"🗑️ Deleted dead letter message {dlq_id}")
            return True
        
        return False
