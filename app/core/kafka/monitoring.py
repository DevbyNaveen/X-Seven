"""
Kafka Monitoring - Comprehensive monitoring and metrics collection
Provides real-time metrics, alerting, and performance monitoring for Kafka operations
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
from aiokafka.admin import AIOKafkaAdminClient
from aiokafka.errors import KafkaError

from app.config.settings import settings

logger = logging.getLogger(__name__)


class AlertLevel(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Alert data structure"""
    id: str
    level: AlertLevel
    title: str
    message: str
    timestamp: datetime
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[datetime] = None


@dataclass
class MetricThreshold:
    """Metric threshold configuration"""
    metric_name: str
    warning_threshold: float
    error_threshold: float
    critical_threshold: float
    comparison: str = "greater_than"  # greater_than, less_than, equals
    window_seconds: int = 60


class KafkaMonitor:
    """
    Comprehensive Kafka monitoring system
    Tracks performance metrics, health status, and generates alerts
    """
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.registry = registry or CollectorRegistry()
        self.admin_client: Optional[AIOKafkaAdminClient] = None
        
        # Monitoring state
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._alert_handlers: List[Callable[[Alert], None]] = []
        self._active_alerts: Dict[str, Alert] = {}
        
        # Metric collection interval
        self.collection_interval = 30.0  # seconds
        
        # Initialize Prometheus metrics
        self._init_prometheus_metrics()
        
        # Metric thresholds
        self.thresholds = [
            MetricThreshold("consumer_lag", 1000, 5000, 10000),
            MetricThreshold("producer_error_rate", 0.01, 0.05, 0.1),
            MetricThreshold("consumer_error_rate", 0.01, 0.05, 0.1),
            MetricThreshold("message_processing_time", 1000, 5000, 10000),  # ms
            MetricThreshold("disk_usage_percent", 80, 90, 95),
        ]
        
        self.logger = logging.getLogger(__name__)
    
    def _init_prometheus_metrics(self) -> None:
        """Initialize Prometheus metrics"""
        # Producer metrics
        self.producer_messages_sent = Counter(
            'kafka_producer_messages_sent_total',
            'Total number of messages sent by producer',
            ['topic'],
            registry=self.registry
        )
        
        self.producer_messages_failed = Counter(
            'kafka_producer_messages_failed_total',
            'Total number of failed message sends',
            ['topic', 'error_type'],
            registry=self.registry
        )
        
        self.producer_send_duration = Histogram(
            'kafka_producer_send_duration_seconds',
            'Time spent sending messages',
            ['topic'],
            registry=self.registry
        )
        
        self.producer_batch_size = Histogram(
            'kafka_producer_batch_size',
            'Size of producer batches',
            ['topic'],
            registry=self.registry
        )
        
        # Consumer metrics
        self.consumer_messages_consumed = Counter(
            'kafka_consumer_messages_consumed_total',
            'Total number of messages consumed',
            ['topic', 'group_id'],
            registry=self.registry
        )
        
        self.consumer_messages_processed = Counter(
            'kafka_consumer_messages_processed_total',
            'Total number of messages successfully processed',
            ['topic', 'group_id'],
            registry=self.registry
        )
        
        self.consumer_messages_failed = Counter(
            'kafka_consumer_messages_failed_total',
            'Total number of failed message processing',
            ['topic', 'group_id', 'error_type'],
            registry=self.registry
        )
        
        self.consumer_processing_duration = Histogram(
            'kafka_consumer_processing_duration_seconds',
            'Time spent processing messages',
            ['topic', 'group_id'],
            registry=self.registry
        )
        
        self.consumer_lag = Gauge(
            'kafka_consumer_lag',
            'Consumer lag in messages',
            ['topic', 'partition', 'group_id'],
            registry=self.registry
        )
        
        # Topic metrics
        self.topic_partition_count = Gauge(
            'kafka_topic_partition_count',
            'Number of partitions per topic',
            ['topic'],
            registry=self.registry
        )
        
        self.topic_message_rate = Gauge(
            'kafka_topic_message_rate',
            'Messages per second per topic',
            ['topic'],
            registry=self.registry
        )
        
        # Broker metrics
        self.broker_connection_count = Gauge(
            'kafka_broker_connection_count',
            'Number of active broker connections',
            registry=self.registry
        )
        
        self.broker_response_time = Histogram(
            'kafka_broker_response_time_seconds',
            'Broker response time',
            ['broker_id'],
            registry=self.registry
        )
        
        # System metrics
        self.system_health_score = Gauge(
            'kafka_system_health_score',
            'Overall system health score (0-100)',
            registry=self.registry
        )
        
        self.active_alerts_count = Gauge(
            'kafka_active_alerts_count',
            'Number of active alerts',
            ['level'],
            registry=self.registry
        )
    
    async def start(self) -> None:
        """Start the monitoring system"""
        if self._monitoring:
            return
        
        try:
            self.logger.info("🚀 Starting Kafka Monitor...")
            
            # Initialize admin client for cluster monitoring
            self.admin_client = AIOKafkaAdminClient(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                security_protocol=settings.KAFKA_SECURITY_PROTOCOL
            )
            await self.admin_client.start()
            
            self._monitoring = True
            self.logger.info("✅ Kafka Monitor started successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start Kafka Monitor: {e}")
            await self.stop()
            raise
    
    async def stop(self) -> None:
        """Stop the monitoring system"""
        if not self._monitoring:
            return
        
        try:
            self.logger.info("🛑 Stopping Kafka Monitor...")
            
            self._monitoring = False
            
            if self._monitor_task and not self._monitor_task.done():
                self._monitor_task.cancel()
                try:
                    await self._monitor_task
                except asyncio.CancelledError:
                    pass
            
            if self.admin_client:
                await self.admin_client.close()
                self.admin_client = None
            
            self.logger.info("✅ Kafka Monitor stopped successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Error stopping Kafka Monitor: {e}")
    
    async def start_monitoring(self) -> None:
        """Start the monitoring loop"""
        if not self._monitoring:
            await self.start()
        
        if self._monitor_task and not self._monitor_task.done():
            return
        
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        self.logger.info("🔄 Started monitoring loop")
    
    async def stop_monitoring(self) -> None:
        """Stop the monitoring loop"""
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("✅ Stopped monitoring loop")
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop"""
        while self._monitoring:
            try:
                await self._collect_metrics()
                await self._check_thresholds()
                # Health score is already updated in _update_system_metrics()
                
                await asyncio.sleep(self.collection_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"❌ Error in monitoring loop: {e}")
                await asyncio.sleep(5.0)  # Brief pause before retrying
    
    async def _collect_metrics(self) -> None:
        """Collect metrics from Kafka cluster"""
        try:
            if not self.admin_client:
                return
            
            # Collect topic metadata
            await self._collect_topic_metrics()
            
            # Collect broker metrics
            await self._collect_broker_metrics()
            
            # Update system metrics
            await self._update_system_metrics()
            
        except Exception as e:
            self.logger.error(f"❌ Error collecting metrics: {e}")
    
    async def _collect_topic_metrics(self) -> None:
        """Collect topic-level metrics"""
        try:
            # Get all topic names first
            topics = await self.admin_client.list_topics()
            
            if topics:
                # Get metadata for all topics at once
                metadata = await self.admin_client.describe_topics(topics)
                
                for topic_name in topics:
                    if topic_name in metadata:
                        topic_info = metadata[topic_name]
                        # topic_info.partitions is a list of partition info
                        partition_count = len(topic_info.partitions) if hasattr(topic_info, 'partitions') else 0
                        self.topic_partition_count.labels(topic=topic_name).set(partition_count)
                
        except Exception as e:
            self.logger.error(f"❌ Error collecting topic metrics: {e}")
    
    async def _collect_broker_metrics(self) -> None:
        """Collect broker-level metrics"""
        try:
            # This would require additional implementation to get broker metrics
            # For now, we'll set a placeholder
            self.broker_connection_count.set(len(settings.KAFKA_BOOTSTRAP_SERVERS))
            
        except Exception as e:
            self.logger.error(f"❌ Error collecting broker metrics: {e}")
    
    async def _update_system_metrics(self) -> None:
        """Update system-level metrics"""
        try:
            # Calculate health score based on various factors
            health_score = await self._calculate_health_score()
            self.system_health_score.set(health_score)
            
            # Update alert counts
            for level in AlertLevel:
                count = sum(1 for alert in self._active_alerts.values() 
                           if alert.level == level and not alert.resolved)
                self.active_alerts_count.labels(level=level.value).set(count)
                
        except Exception as e:
            self.logger.error(f"❌ Error updating system metrics: {e}")
    
    async def _calculate_health_score(self) -> float:
        """Calculate overall system health score (0-100)"""
        try:
            score = 100.0
            
            # Deduct points for active alerts
            for alert in self._active_alerts.values():
                if not alert.resolved:
                    if alert.level == AlertLevel.CRITICAL:
                        score -= 25
                    elif alert.level == AlertLevel.ERROR:
                        score -= 15
                    elif alert.level == AlertLevel.WARNING:
                        score -= 5
            
            # Ensure score is within bounds
            return max(0.0, min(100.0, score))
            
        except Exception as e:
            self.logger.error(f"❌ Error calculating health score: {e}")
            return 50.0  # Default to medium health
    
    async def _check_thresholds(self) -> None:
        """Check metric thresholds and generate alerts"""
        try:
            current_metrics = self.get_metrics()
            
            for threshold in self.thresholds:
                await self._check_metric_threshold(threshold, current_metrics)
                
        except Exception as e:
            self.logger.error(f"❌ Error checking thresholds: {e}")
    
    async def _check_metric_threshold(
        self,
        threshold: MetricThreshold,
        metrics: Dict[str, Any]
    ) -> None:
        """Check a specific metric threshold"""
        try:
            metric_value = metrics.get(threshold.metric_name)
            if metric_value is None:
                return
            
            # Determine alert level
            alert_level = None
            if self._exceeds_threshold(metric_value, threshold.critical_threshold, threshold.comparison):
                alert_level = AlertLevel.CRITICAL
            elif self._exceeds_threshold(metric_value, threshold.error_threshold, threshold.comparison):
                alert_level = AlertLevel.ERROR
            elif self._exceeds_threshold(metric_value, threshold.warning_threshold, threshold.comparison):
                alert_level = AlertLevel.WARNING
            
            alert_id = f"threshold_{threshold.metric_name}"
            
            if alert_level:
                # Create or update alert
                if alert_id not in self._active_alerts or self._active_alerts[alert_id].resolved:
                    alert = Alert(
                        id=alert_id,
                        level=alert_level,
                        title=f"Metric Threshold Exceeded: {threshold.metric_name}",
                        message=f"{threshold.metric_name} value {metric_value} exceeds {alert_level.value} threshold",
                        timestamp=datetime.utcnow(),
                        source="kafka_monitor",
                        metadata={
                            "metric_name": threshold.metric_name,
                            "metric_value": metric_value,
                            "threshold": getattr(threshold, f"{alert_level.value}_threshold")
                        }
                    )
                    
                    self._active_alerts[alert_id] = alert
                    await self._trigger_alert(alert)
            else:
                # Resolve alert if it exists
                if alert_id in self._active_alerts and not self._active_alerts[alert_id].resolved:
                    alert = self._active_alerts[alert_id]
                    alert.resolved = True
                    alert.resolved_at = datetime.utcnow()
                    await self._resolve_alert(alert)
                    
        except Exception as e:
            self.logger.error(f"❌ Error checking threshold for {threshold.metric_name}: {e}")
    
    def _exceeds_threshold(self, value: float, threshold: float, comparison: str) -> bool:
        """Check if value exceeds threshold based on comparison type"""
        if comparison == "greater_than":
            return value > threshold
        elif comparison == "less_than":
            return value < threshold
        elif comparison == "equals":
            return value == threshold
        else:
            return False
    
    async def _trigger_alert(self, alert: Alert) -> None:
        """Trigger an alert"""
        self.logger.warning(f"🚨 ALERT [{alert.level.value.upper()}]: {alert.title} - {alert.message}")
        
        # Call alert handlers
        for handler in self._alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                self.logger.error(f"❌ Error in alert handler: {e}")
    
    async def _resolve_alert(self, alert: Alert) -> None:
        """Resolve an alert"""
        self.logger.info(f"✅ RESOLVED: {alert.title}")
        
        # Call alert handlers for resolution
        for handler in self._alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                self.logger.error(f"❌ Error in alert resolution handler: {e}")
    
    def add_alert_handler(self, handler: Callable[[Alert], None]) -> None:
        """Add an alert handler"""
        self._alert_handlers.append(handler)
        self.logger.info("Added alert handler")
    
    def remove_alert_handler(self, handler: Callable[[Alert], None]) -> None:
        """Remove an alert handler"""
        if handler in self._alert_handlers:
            self._alert_handlers.remove(handler)
            self.logger.info("Removed alert handler")
    
    def record_producer_message_sent(self, topic: str, duration: float = 0.0) -> None:
        """Record a producer message sent"""
        self.producer_messages_sent.labels(topic=topic).inc()
        if duration > 0:
            self.producer_send_duration.labels(topic=topic).observe(duration)
    
    def record_producer_message_failed(self, topic: str, error_type: str) -> None:
        """Record a producer message failure"""
        self.producer_messages_failed.labels(topic=topic, error_type=error_type).inc()
    
    def record_consumer_message_consumed(self, topic: str, group_id: str) -> None:
        """Record a consumer message consumed"""
        self.consumer_messages_consumed.labels(topic=topic, group_id=group_id).inc()
    
    def record_consumer_message_processed(self, topic: str, group_id: str, duration: float = 0.0) -> None:
        """Record a consumer message processed"""
        self.consumer_messages_processed.labels(topic=topic, group_id=group_id).inc()
        if duration > 0:
            self.consumer_processing_duration.labels(topic=topic, group_id=group_id).observe(duration)
    
    def record_consumer_message_failed(self, topic: str, group_id: str, error_type: str) -> None:
        """Record a consumer message failure"""
        self.consumer_messages_failed.labels(topic=topic, group_id=group_id, error_type=error_type).inc()
    
    def set_consumer_lag(self, topic: str, partition: int, group_id: str, lag: int) -> None:
        """Set consumer lag for a partition"""
        self.consumer_lag.labels(topic=topic, partition=str(partition), group_id=group_id).set(lag)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics as dictionary"""
        try:
            # Generate Prometheus metrics
            metrics_output = generate_latest(self.registry).decode('utf-8')
            
            # Parse and return as dictionary (simplified)
            return {
                'prometheus_metrics': metrics_output,
                'active_alerts': len([a for a in self._active_alerts.values() if not a.resolved]),
                'total_alerts': len(self._active_alerts),
                'monitoring_active': self._monitoring,
                'collection_interval': self.collection_interval,
                'health_score': self._calculate_health_score_sync()
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error getting metrics: {e}")
            return {}
    
    def _calculate_health_score_sync(self) -> float:
        """Synchronous version of health score calculation"""
        try:
            score = 100.0
            
            for alert in self._active_alerts.values():
                if not alert.resolved:
                    if alert.level == AlertLevel.CRITICAL:
                        score -= 25
                    elif alert.level == AlertLevel.ERROR:
                        score -= 15
                    elif alert.level == AlertLevel.WARNING:
                        score -= 5
            
            return max(0.0, min(100.0, score))
            
        except Exception:
            return 50.0
    
    def get_active_alerts(self) -> List[Alert]:
        """Get list of active alerts"""
        return [alert for alert in self._active_alerts.values() if not alert.resolved]
    
    def get_alert_history(self, hours: int = 24) -> List[Alert]:
        """Get alert history for the specified number of hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return [
            alert for alert in self._active_alerts.values()
            if alert.timestamp >= cutoff_time
        ]
    
    def export_metrics(self, format: str = "prometheus") -> str:
        """Export metrics in specified format"""
        if format == "prometheus":
            return generate_latest(self.registry).decode('utf-8')
        elif format == "json":
            return json.dumps(self.get_metrics(), indent=2)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    async def perform_check(self) -> bool:
        """Perform health check for Kafka monitoring system"""
        try:
            if not self._monitoring or not self.admin_client:
                return False
            
            # Simple check - verify we can list topics
            topics = await self.admin_client.list_topics()
            return len(topics) >= 0  # Just check if we can connect and get a response
            
        except Exception as e:
            self.logger.error(f"❌ Health check failed: {e}")
            return False


# Alert handler implementations
def log_alert_handler(alert: Alert) -> None:
    """Simple log-based alert handler"""
    if alert.resolved:
        logger.info(f"✅ Alert resolved: {alert.title}")
    else:
        logger.warning(f"🚨 Alert triggered: {alert.title} - {alert.message}")


def webhook_alert_handler(webhook_url: str) -> Callable[[Alert], None]:
    """Create a webhook-based alert handler"""
    import httpx
    
    def handler(alert: Alert) -> None:
        try:
            payload = {
                "alert_id": alert.id,
                "level": alert.level.value,
                "title": alert.title,
                "message": alert.message,
                "timestamp": alert.timestamp.isoformat(),
                "resolved": alert.resolved,
                "metadata": alert.metadata
            }
            
            # This would be async in a real implementation
            # For now, just log the webhook call
            logger.info(f"📡 Would send webhook to {webhook_url}: {payload}")
            
        except Exception as e:
            logger.error(f"❌ Webhook alert handler error: {e}")
    
    return handler
