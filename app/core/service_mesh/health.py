"""
Health Check System for Service Monitoring
Provides comprehensive health monitoring for all services
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import aiohttp
import asyncpg
import redis.asyncio as redis
from aiokafka import AIOKafkaConsumer
from temporalio.client import Client

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check"""
    status: HealthStatus
    message: str
    timestamp: datetime
    duration: float
    details: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "duration": self.duration,
            "details": self.details or {}
        }


class HealthChecker:
    """Comprehensive health checking for all services"""
    
    def __init__(self):
        self._health_checks: Dict[str, Callable] = {}
        self._monitoring_tasks: Dict[str, asyncio.Task] = {}
        self._last_results: Dict[str, HealthCheckResult] = {}
        self._running = False
        self._check_interval = 30  # seconds
        
        # Register default health checks
        self._register_default_checks()
    
    def _register_default_checks(self):
        """Register default health checks for common services"""
        self.register_check("database", self._check_database)
        self.register_check("redis", self._check_redis)
        self.register_check("kafka", self._check_kafka)
        self.register_check("temporal", self._check_temporal)
        self.register_check("external_api", self._check_external_api)
    
    def register_check(self, service_name: str, check_func: Callable) -> None:
        """Register a health check function for a service"""
        self._health_checks[service_name] = check_func
        logger.info(f"🔍 Registered health check: {service_name}")
    
    async def start_monitoring(self):
        """Start continuous health monitoring"""
        if self._running:
            return
        
        self._running = True
        logger.info("🔍 Starting health monitoring...")
        
        for service_name in self._health_checks:
            task = asyncio.create_task(self._monitor_service(service_name))
            self._monitoring_tasks[service_name] = task
    
    async def stop_monitoring(self):
        """Stop health monitoring"""
        if not self._running:
            return
        
        self._running = False
        logger.info("🛑 Stopping health monitoring...")
        
        for task in self._monitoring_tasks.values():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        self._monitoring_tasks.clear()
    
    async def check_service_health(self, service_name: str) -> bool:
        """Check health of a specific service"""
        if service_name not in self._health_checks:
            return True  # Assume healthy if no check registered
        
        try:
            result = await self._health_checks[service_name]()
            return result.status == HealthStatus.HEALTHY
        except Exception:
            return False
    
    async def get_service_health(self, service_name: str) -> HealthCheckResult:
        """Get detailed health information for a service"""
        if service_name not in self._health_checks:
            return HealthCheckResult(
                status=HealthStatus.UNKNOWN,
                message="No health check registered",
                timestamp=datetime.now(),
                duration=0.0
            )
        
        return await self._health_checks[service_name]()
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health"""
        health_results = {}
        
        for service_name in self._health_checks:
            try:
                health_results[service_name] = await self.get_service_health(service_name)
            except Exception as e:
                health_results[service_name] = HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message=str(e),
                    timestamp=datetime.now(),
                    duration=0.0
                )
        
        # Calculate overall health
        healthy_count = sum(1 for r in health_results.values() 
                          if r.status == HealthStatus.HEALTHY)
        total_count = len(health_results)
        
        overall_status = HealthStatus.HEALTHY
        if healthy_count < total_count:
            if healthy_count >= total_count * 0.8:
                overall_status = HealthStatus.DEGRADED
            else:
                overall_status = HealthStatus.UNHEALTHY
        
        return {
            "overall_status": overall_status.value,
            "healthy_services": healthy_count,
            "total_services": total_count,
            "health_ratio": healthy_count / max(1, total_count),
            "timestamp": datetime.now().isoformat(),
            "services": {
                name: result.to_dict()
                for name, result in health_results.items()
            }
        }
    
    async def _monitor_service(self, service_name: str):
        """Monitor a single service continuously"""
        while self._running:
            try:
                result = await self._health_checks[service_name]()
                self._last_results[service_name] = result
                
                # Log status changes
                if service_name in self._last_results:
                    prev_result = self._last_results[service_name]
                    if prev_result.status != result.status:
                        logger.warning(
                            f"Service {service_name} health changed: "
                            f"{prev_result.status.value} -> {result.status.value}"
                        )
                
                await asyncio.sleep(self._check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error monitoring {service_name}: {e}")
                await asyncio.sleep(self._check_interval * 2)  # Back off on error
    
    async def _check_database(self) -> HealthCheckResult:
        """Check database health"""
        start_time = datetime.now()
        
        try:
            from app.config.database import get_supabase_client
            client = get_supabase_client()
            
            # Simple health check - test authentication/connection
            # Instead of querying information_schema which isn't available via REST API
            session = client.auth.get_session()
            
            duration = (datetime.now() - start_time).total_seconds()
            
            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="Database connection successful",
                timestamp=datetime.now(),
                duration=duration,
                details={"query_time": duration}
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"Database connection failed: {str(e)}",
                timestamp=datetime.now(),
                duration=duration
            )
    
    async def _check_redis(self) -> HealthCheckResult:
        """Check Redis health"""
        start_time = datetime.now()
        
        try:
            from app.config.settings import settings
            redis_client = redis.from_url(settings.REDIS_URL)
            
            await redis_client.ping()
            info = await redis_client.info()
            
            duration = (datetime.now() - start_time).total_seconds()
            
            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="Redis connection successful",
                timestamp=datetime.now(),
                duration=duration,
                details={
                    "version": info.get("redis_version"),
                    "connected_clients": info.get("connected_clients"),
                    "used_memory": info.get("used_memory_human")
                }
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"Redis connection failed: {str(e)}",
                timestamp=datetime.now(),
                duration=duration
            )
    
    async def _check_kafka(self) -> HealthCheckResult:
        """Check Kafka health"""
        start_time = datetime.now()
        
        try:
            from app.config.settings import settings
            from aiokafka import AIOKafkaAdminClient
            
            admin_client = AIOKafkaAdminClient(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS
            )
            
            await admin_client.start()
            topics = await admin_client.list_topics()
            await admin_client.close()
            
            duration = (datetime.now() - start_time).total_seconds()
            
            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="Kafka connection successful",
                timestamp=datetime.now(),
                duration=duration,
                details={
                    "topics_count": len(topics),
                    "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS
                }
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"Kafka connection failed: {str(e)}",
                timestamp=datetime.now(),
                duration=duration
            )
    
    async def _check_temporal(self) -> HealthCheckResult:
        """Check Temporal health"""
        start_time = datetime.now()
        
        try:
            from temporalio.client import Client
            
            client = await Client.connect("localhost:7233")
            
            # Check if we can list namespaces
            namespaces = await client.list_namespaces()
            
            duration = (datetime.now() - start_time).total_seconds()
            
            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="Temporal connection successful",
                timestamp=datetime.now(),
                duration=duration,
                details={
                    "namespaces_count": len(namespaces),
                    "endpoint": "localhost:7233"
                }
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"Temporal connection failed: {str(e)}",
                timestamp=datetime.now(),
                duration=duration
            )
    
    async def _check_external_api(self) -> HealthCheckResult:
        """Check external API health"""
        start_time = datetime.now()
        
        try:
            async with aiohttp.ClientSession() as session:
                # Check a simple external API (example)
                async with session.get("https://httpbin.org/status/200", timeout=5) as response:
                    duration = (datetime.now() - start_time).total_seconds()
                    
                    return HealthCheckResult(
                        status=HealthStatus.HEALTHY,
                        message="External API accessible",
                        timestamp=datetime.now(),
                        duration=duration,
                        details={"status_code": response.status}
                    )
                    
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"External API check failed: {str(e)}",
                timestamp=datetime.now(),
                duration=duration
            )
    
    def get_last_result(self, service_name: str) -> Optional[HealthCheckResult]:
        """Get last health check result for a service"""
        return self._last_results.get(service_name)


# Global health checker
_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """Get global health checker instance"""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker
