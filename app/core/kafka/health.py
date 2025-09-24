"""
Kafka Health Check - Comprehensive health monitoring
Provides health status, diagnostics, and readiness checks for Kafka components
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.admin import AIOKafkaAdminClient
from aiokafka.errors import KafkaError, KafkaTimeoutError

from app.config.settings import settings

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Health check result"""
    component: str
    status: HealthStatus
    message: str
    timestamp: datetime
    duration_ms: float
    details: Dict[str, Any]


@dataclass
class ComponentHealth:
    """Component health information"""
    name: str
    status: HealthStatus
    last_check: datetime
    checks: List[HealthCheckResult]
    uptime_seconds: float
    error_count: int


class KafkaHealthCheck:
    """
    Comprehensive health check system for Kafka components
    Monitors connectivity, performance, and operational status
    """
    
    def __init__(self, kafka_manager=None):
        self.kafka_manager = kafka_manager
        self.bootstrap_servers = settings.KAFKA_BOOTSTRAP_SERVERS
        
        # Health check configuration
        self.check_interval = 30.0  # seconds
        self.timeout = 10.0  # seconds
        self.max_response_time = 5000  # ms
        
        # Component health tracking
        self.components: Dict[str, ComponentHealth] = {}
        self.overall_status = HealthStatus.UNKNOWN
        self.last_overall_check = datetime.utcnow()
        
        # Health check tasks
        self._health_check_task: Optional[asyncio.Task] = None
        self._running = False
        
        self.logger = logging.getLogger(__name__)
    
    async def start_health_checks(self) -> None:
        """Start continuous health monitoring"""
        if self._running:
            return
        
        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        self.logger.info("🚀 Started Kafka health checks")
    
    async def stop_health_checks(self) -> None:
        """Stop continuous health monitoring"""
        self._running = False
        
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("✅ Stopped Kafka health checks")
    
    async def _health_check_loop(self) -> None:
        """Main health check loop"""
        while self._running:
            try:
                await self.perform_full_health_check()
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"❌ Error in health check loop: {e}")
                await asyncio.sleep(5.0)
    
    async def perform_full_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check of all components"""
        start_time = time.time()
        
        try:
            self.logger.debug("🔍 Performing full health check...")
            
            # Check individual components
            checks = await asyncio.gather(
                self._check_broker_connectivity(),
                self._check_topic_availability(),
                self._check_producer_health(),
                self._check_consumer_health(),
                self._check_admin_client_health(),
                return_exceptions=True
            )
            
            # Process results
            broker_result, topic_result, producer_result, consumer_result, admin_result = checks
            
            # Update component health
            self._update_component_health("broker", broker_result)
            self._update_component_health("topics", topic_result)
            self._update_component_health("producer", producer_result)
            self._update_component_health("consumer", consumer_result)
            self._update_component_health("admin", admin_result)
            
            # Calculate overall health
            self._calculate_overall_health()
            
            duration_ms = (time.time() - start_time) * 1000
            
            result = {
                "overall_status": self.overall_status.value,
                "last_check": self.last_overall_check.isoformat(),
                "check_duration_ms": duration_ms,
                "components": {
                    name: {
                        "status": comp.status.value,
                        "last_check": comp.last_check.isoformat(),
                        "uptime_seconds": comp.uptime_seconds,
                        "error_count": comp.error_count,
                        "recent_checks": len(comp.checks)
                    }
                    for name, comp in self.components.items()
                },
                "summary": self._get_health_summary()
            }
            
            self.logger.debug(f"✅ Health check completed in {duration_ms:.2f}ms")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Full health check failed: {e}")
            self.overall_status = HealthStatus.UNHEALTHY
            return {
                "overall_status": self.overall_status.value,
                "error": str(e),
                "last_check": datetime.utcnow().isoformat()
            }
    
    async def _check_broker_connectivity(self) -> HealthCheckResult:
        """Check broker connectivity"""
        start_time = time.time()
        component = "broker"
        
        try:
            # Test connection to brokers
            admin_client = AIOKafkaAdminClient(
                bootstrap_servers=self.bootstrap_servers,
                security_protocol=settings.KAFKA_SECURITY_PROTOCOL,
                request_timeout_ms=int(self.timeout * 1000)
            )
            
            await admin_client.start()
            
            # Try to get cluster metadata
            metadata = await admin_client.describe_cluster()
            broker_count = len(metadata.brokers) if hasattr(metadata, 'brokers') else 0
            
            await admin_client.close()
            
            duration_ms = (time.time() - start_time) * 1000
            
            if broker_count > 0:
                return HealthCheckResult(
                    component=component,
                    status=HealthStatus.HEALTHY,
                    message=f"Connected to {broker_count} brokers",
                    timestamp=datetime.utcnow(),
                    duration_ms=duration_ms,
                    details={"broker_count": broker_count}
                )
            else:
                return HealthCheckResult(
                    component=component,
                    status=HealthStatus.UNHEALTHY,
                    message="No brokers available",
                    timestamp=datetime.utcnow(),
                    duration_ms=duration_ms,
                    details={"broker_count": 0}
                )
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                component=component,
                status=HealthStatus.UNHEALTHY,
                message=f"Broker connectivity failed: {str(e)}",
                timestamp=datetime.utcnow(),
                duration_ms=duration_ms,
                details={"error": str(e)}
            )
    
    async def _check_topic_availability(self) -> HealthCheckResult:
        """Check topic availability"""
        start_time = time.time()
        component = "topics"
        
        try:
            admin_client = AIOKafkaAdminClient(
                bootstrap_servers=self.bootstrap_servers,
                security_protocol=settings.KAFKA_SECURITY_PROTOCOL,
                request_timeout_ms=int(self.timeout * 1000)
            )
            
            await admin_client.start()
            
            # Check configured topics
            topic_names = list(settings.KAFKA_TOPICS.keys())
            if topic_names:
                metadata = await admin_client.describe_topics(topic_names)
                available_topics = len(metadata)
                total_topics = len(topic_names)
            else:
                available_topics = 0
                total_topics = 0
            
            await admin_client.close()
            
            duration_ms = (time.time() - start_time) * 1000
            
            if available_topics == total_topics and total_topics > 0:
                status = HealthStatus.HEALTHY
                message = f"All {total_topics} topics available"
            elif available_topics > 0:
                status = HealthStatus.DEGRADED
                message = f"{available_topics}/{total_topics} topics available"
            else:
                status = HealthStatus.UNHEALTHY
                message = "No topics available"
            
            return HealthCheckResult(
                component=component,
                status=status,
                message=message,
                timestamp=datetime.utcnow(),
                duration_ms=duration_ms,
                details={
                    "available_topics": available_topics,
                    "total_topics": total_topics,
                    "topic_names": topic_names
                }
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                component=component,
                status=HealthStatus.UNHEALTHY,
                message=f"Topic check failed: {str(e)}",
                timestamp=datetime.utcnow(),
                duration_ms=duration_ms,
                details={"error": str(e)}
            )
    
    async def _check_producer_health(self) -> HealthCheckResult:
        """Check producer health"""
        start_time = time.time()
        component = "producer"
        
        try:
            if self.kafka_manager and self.kafka_manager.producer:
                producer = self.kafka_manager.producer
                
                if producer.is_running():
                    metrics = producer.get_metrics()
                    
                    # Check error rate
                    total_messages = metrics.get('messages_sent', 0) + metrics.get('messages_failed', 0)
                    error_rate = metrics.get('messages_failed', 0) / max(total_messages, 1)
                    
                    duration_ms = (time.time() - start_time) * 1000
                    
                    if error_rate < 0.01:  # Less than 1% error rate
                        status = HealthStatus.HEALTHY
                        message = f"Producer healthy (error rate: {error_rate:.2%})"
                    elif error_rate < 0.05:  # Less than 5% error rate
                        status = HealthStatus.DEGRADED
                        message = f"Producer degraded (error rate: {error_rate:.2%})"
                    else:
                        status = HealthStatus.UNHEALTHY
                        message = f"Producer unhealthy (error rate: {error_rate:.2%})"
                    
                    return HealthCheckResult(
                        component=component,
                        status=status,
                        message=message,
                        timestamp=datetime.utcnow(),
                        duration_ms=duration_ms,
                        details=metrics
                    )
                else:
                    return HealthCheckResult(
                        component=component,
                        status=HealthStatus.UNHEALTHY,
                        message="Producer not running",
                        timestamp=datetime.utcnow(),
                        duration_ms=(time.time() - start_time) * 1000,
                        details={}
                    )
            else:
                return HealthCheckResult(
                    component=component,
                    status=HealthStatus.UNKNOWN,
                    message="Producer not initialized",
                    timestamp=datetime.utcnow(),
                    duration_ms=(time.time() - start_time) * 1000,
                    details={}
                )
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                component=component,
                status=HealthStatus.UNHEALTHY,
                message=f"Producer health check failed: {str(e)}",
                timestamp=datetime.utcnow(),
                duration_ms=duration_ms,
                details={"error": str(e)}
            )
    
    async def _check_consumer_health(self) -> HealthCheckResult:
        """Check consumer health"""
        start_time = time.time()
        component = "consumer"
        
        try:
            if self.kafka_manager and self.kafka_manager.consumers:
                consumers = self.kafka_manager.consumers
                
                healthy_consumers = 0
                total_consumers = len(consumers)
                consumer_details = {}
                
                for topic, consumer in consumers.items():
                    if consumer.is_running():
                        healthy_consumers += 1
                        metrics = consumer.get_metrics()
                        consumer_details[topic] = {
                            "status": "running",
                            "metrics": metrics
                        }
                    else:
                        consumer_details[topic] = {
                            "status": "stopped",
                            "metrics": {}
                        }
                
                duration_ms = (time.time() - start_time) * 1000
                
                if healthy_consumers == total_consumers and total_consumers > 0:
                    status = HealthStatus.HEALTHY
                    message = f"All {total_consumers} consumers healthy"
                elif healthy_consumers > 0:
                    status = HealthStatus.DEGRADED
                    message = f"{healthy_consumers}/{total_consumers} consumers healthy"
                else:
                    status = HealthStatus.UNHEALTHY
                    message = "No healthy consumers"
                
                return HealthCheckResult(
                    component=component,
                    status=status,
                    message=message,
                    timestamp=datetime.utcnow(),
                    duration_ms=duration_ms,
                    details={
                        "healthy_consumers": healthy_consumers,
                        "total_consumers": total_consumers,
                        "consumers": consumer_details
                    }
                )
            else:
                return HealthCheckResult(
                    component=component,
                    status=HealthStatus.UNKNOWN,
                    message="No consumers initialized",
                    timestamp=datetime.utcnow(),
                    duration_ms=(time.time() - start_time) * 1000,
                    details={}
                )
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                component=component,
                status=HealthStatus.UNHEALTHY,
                message=f"Consumer health check failed: {str(e)}",
                timestamp=datetime.utcnow(),
                duration_ms=duration_ms,
                details={"error": str(e)}
            )
    
    async def _check_admin_client_health(self) -> HealthCheckResult:
        """Check admin client health"""
        start_time = time.time()
        component = "admin"
        
        try:
            if self.kafka_manager and self.kafka_manager.admin_client:
                # Try a simple admin operation
                admin_client = self.kafka_manager.admin_client
                
                # List topics as a health check
                metadata = await admin_client.describe_topics()
                topic_count = len(metadata)
                
                duration_ms = (time.time() - start_time) * 1000
                
                return HealthCheckResult(
                    component=component,
                    status=HealthStatus.HEALTHY,
                    message=f"Admin client healthy ({topic_count} topics accessible)",
                    timestamp=datetime.utcnow(),
                    duration_ms=duration_ms,
                    details={"accessible_topics": topic_count}
                )
            else:
                return HealthCheckResult(
                    component=component,
                    status=HealthStatus.UNKNOWN,
                    message="Admin client not initialized",
                    timestamp=datetime.utcnow(),
                    duration_ms=(time.time() - start_time) * 1000,
                    details={}
                )
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                component=component,
                status=HealthStatus.UNHEALTHY,
                message=f"Admin client health check failed: {str(e)}",
                timestamp=datetime.utcnow(),
                duration_ms=duration_ms,
                details={"error": str(e)}
            )
    
    def _update_component_health(self, component_name: str, result: HealthCheckResult) -> None:
        """Update component health based on check result"""
        if isinstance(result, Exception):
            # Handle exception results
            result = HealthCheckResult(
                component=component_name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check exception: {str(result)}",
                timestamp=datetime.utcnow(),
                duration_ms=0.0,
                details={"error": str(result)}
            )
        
        if component_name not in self.components:
            self.components[component_name] = ComponentHealth(
                name=component_name,
                status=HealthStatus.UNKNOWN,
                last_check=datetime.utcnow(),
                checks=[],
                uptime_seconds=0.0,
                error_count=0
            )
        
        component = self.components[component_name]
        
        # Update status
        component.status = result.status
        component.last_check = result.timestamp
        
        # Add check to history (keep last 10)
        component.checks.append(result)
        if len(component.checks) > 10:
            component.checks.pop(0)
        
        # Update error count
        if result.status == HealthStatus.UNHEALTHY:
            component.error_count += 1
        
        # Calculate uptime (simplified)
        if component.checks:
            first_check = component.checks[0].timestamp
            component.uptime_seconds = (datetime.utcnow() - first_check).total_seconds()
    
    def _calculate_overall_health(self) -> None:
        """Calculate overall system health"""
        if not self.components:
            self.overall_status = HealthStatus.UNKNOWN
            return
        
        statuses = [comp.status for comp in self.components.values()]
        
        if all(status == HealthStatus.HEALTHY for status in statuses):
            self.overall_status = HealthStatus.HEALTHY
        elif any(status == HealthStatus.UNHEALTHY for status in statuses):
            self.overall_status = HealthStatus.UNHEALTHY
        elif any(status == HealthStatus.DEGRADED for status in statuses):
            self.overall_status = HealthStatus.DEGRADED
        else:
            self.overall_status = HealthStatus.UNKNOWN
        
        self.last_overall_check = datetime.utcnow()
    
    def _get_health_summary(self) -> Dict[str, Any]:
        """Get health summary"""
        if not self.components:
            return {"message": "No components monitored"}
        
        status_counts = {}
        for status in HealthStatus:
            status_counts[status.value] = sum(
                1 for comp in self.components.values() 
                if comp.status == status
            )
        
        total_errors = sum(comp.error_count for comp in self.components.values())
        avg_uptime = sum(comp.uptime_seconds for comp in self.components.values()) / len(self.components)
        
        return {
            "total_components": len(self.components),
            "status_distribution": status_counts,
            "total_errors": total_errors,
            "average_uptime_seconds": avg_uptime,
            "overall_status": self.overall_status.value
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get current health status"""
        return {
            "overall_status": self.overall_status.value,
            "last_check": self.last_overall_check.isoformat(),
            "components": {
                name: {
                    "status": comp.status.value,
                    "last_check": comp.last_check.isoformat(),
                    "uptime_seconds": comp.uptime_seconds,
                    "error_count": comp.error_count
                }
                for name, comp in self.components.items()
            },
            "summary": self._get_health_summary(),
            "monitoring_active": self._running
        }
    
    async def get_readiness_status(self) -> Tuple[bool, Dict[str, Any]]:
        """Get readiness status for Kubernetes/container orchestration"""
        try:
            # Perform quick health check
            health_result = await self.perform_full_health_check()
            
            is_ready = (
                self.overall_status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED] and
                self.kafka_manager and
                self.kafka_manager._initialized and
                self.kafka_manager._running
            )
            
            return is_ready, {
                "ready": is_ready,
                "status": self.overall_status.value,
                "components": len(self.components),
                "last_check": self.last_overall_check.isoformat()
            }
            
        except Exception as e:
            return False, {
                "ready": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def get_liveness_status(self) -> Tuple[bool, Dict[str, Any]]:
        """Get liveness status for Kubernetes/container orchestration"""
        try:
            # Simple liveness check - just verify we can respond
            is_alive = (
                self._running and
                datetime.utcnow() - self.last_overall_check < timedelta(minutes=5)
            )
            
            return is_alive, {
                "alive": is_alive,
                "last_health_check": self.last_overall_check.isoformat(),
                "monitoring_active": self._running,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return False, {
                "alive": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
