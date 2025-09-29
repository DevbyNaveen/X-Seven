"""
Service Registry with Health Monitoring
Provides service discovery and health-based routing
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json

logger = logging.getLogger(__name__)


class ServiceHealth(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ServiceInstance:
    """Represents a service instance with health information"""
    name: str
    instance_id: str
    host: str
    port: int
    health: ServiceHealth = ServiceHealth.UNKNOWN
    last_check: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    @property
    def is_healthy(self) -> bool:
        return self.health == ServiceHealth.HEALTHY
    
    @property
    def endpoint(self) -> str:
        return f"{self.host}:{self.port}"


@dataclass
class ServiceDefinition:
    """Defines a service with its dependencies and configuration"""
    name: str
    service_type: type
    dependencies: List[str] = field(default_factory=list)
    config_class: Optional[type] = None
    health_check: Optional[Callable] = None
    startup_timeout: int = 30
    shutdown_timeout: int = 10
    retry_count: int = 3
    retry_delay: float = 1.0


class ServiceRegistry:
    """Central service registry with health monitoring"""
    
    def __init__(self):
        self._services: Dict[str, List[ServiceInstance]] = {}
        self._definitions: Dict[str, ServiceDefinition] = {}
        self._health_checks: Dict[str, Callable] = {}
        self._monitoring_tasks: Dict[str, asyncio.Task] = {}
        self._event_callbacks: List[Callable] = []
        self._running = False
        
    async def start(self):
        """Start the service registry and health monitoring"""
        self._running = True
        logger.info("🚀 Starting Service Registry...")
        
        # Start health monitoring for all registered services
        for service_name in self._services:
            await self._start_health_monitoring(service_name)
            
        logger.info("✅ Service Registry started")
    
    async def stop(self):
        """Stop the service registry and cleanup"""
        self._running = False
        logger.info("🛑 Stopping Service Registry...")
        
        # Cancel all monitoring tasks
        for task in self._monitoring_tasks.values():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        self._monitoring_tasks.clear()
        logger.info("✅ Service Registry stopped")
    
    def register_service(self, definition: ServiceDefinition) -> None:
        """Register a service definition"""
        self._definitions[definition.name] = definition
        if definition.health_check:
            self._health_checks[definition.name] = definition.health_check
        logger.info(f"📋 Registered service: {definition.name}")
    
    def add_instance(self, instance: ServiceInstance) -> None:
        """Add a service instance"""
        if instance.name not in self._services:
            self._services[instance.name] = []
        
        # Remove existing instance with same ID
        self._services[instance.name] = [
            inst for inst in self._services[instance.name]
            if inst.instance_id != instance.instance_id
        ]
        
        self._services[instance.name].append(instance)
        
        if self._running:
            asyncio.create_task(self._start_health_monitoring(instance.name))
        
        logger.info(f"➕ Added instance: {instance.name}@{instance.endpoint}")
        self._notify_event("instance_added", instance)
    
    def remove_instance(self, service_name: str, instance_id: str) -> bool:
        """Remove a service instance"""
        if service_name not in self._services:
            return False
        
        original_count = len(self._services[service_name])
        self._services[service_name] = [
            inst for inst in self._services[service_name]
            if inst.instance_id != instance_id
        ]
        
        removed = original_count != len(self._services[service_name])
        if removed:
            logger.info(f"➖ Removed instance: {service_name}#{instance_id}")
            self._notify_event("instance_removed", {
                "service_name": service_name,
                "instance_id": instance_id
            })
        
        return removed
    
    def get_instances(self, service_name: str, healthy_only: bool = True) -> List[ServiceInstance]:
        """Get service instances, optionally filtered by health"""
        instances = self._services.get(service_name, [])
        if healthy_only:
            return [inst for inst in instances if inst.is_healthy]
        return instances
    
    def get_healthy_instance(self, service_name: str) -> Optional[ServiceInstance]:
        """Get a healthy instance for load balancing"""
        healthy = self.get_instances(service_name, healthy_only=True)
        if not healthy:
            return None
        
        # Simple round-robin selection
        return healthy[0]
    
    def get_service_definition(self, service_name: str) -> Optional[ServiceDefinition]:
        """Get service definition"""
        return self._definitions.get(service_name)
    
    def get_all_services(self) -> Dict[str, List[ServiceInstance]]:
        """Get all registered services"""
        return self._services.copy()
    
    def get_service_health(self, service_name: str) -> Dict[str, Any]:
        """Get comprehensive health information for a service"""
        instances = self.get_instances(service_name, healthy_only=False)
        
        if not instances:
            return {
                "service_name": service_name,
                "status": ServiceHealth.UNKNOWN,
                "instance_count": 0,
                "healthy_count": 0,
                "last_check": None
            }
        
        healthy_count = sum(1 for inst in instances if inst.is_healthy)
        
        # Overall health based on healthy ratio
        health_ratio = healthy_count / len(instances)
        if health_ratio >= 0.8:
            status = ServiceHealth.HEALTHY
        elif health_ratio >= 0.5:
            status = ServiceHealth.DEGRADED
        else:
            status = ServiceHealth.UNHEALTHY
        
        return {
            "service_name": service_name,
            "status": status,
            "instance_count": len(instances),
            "healthy_count": healthy_count,
            "health_ratio": health_ratio,
            "last_check": max(inst.last_check for inst in instances),
            "instances": [
                {
                    "instance_id": inst.instance_id,
                    "endpoint": inst.endpoint,
                    "health": inst.health.value,
                    "last_check": inst.last_check.isoformat(),
                    "metadata": inst.metadata
                }
                for inst in instances
            ]
        }
    
    def add_event_callback(self, callback: Callable) -> None:
        """Add event callback for service changes"""
        self._event_callbacks.append(callback)
    
    async def _start_health_monitoring(self, service_name: str) -> None:
        """Start health monitoring for a service"""
        if service_name in self._monitoring_tasks:
            return
        
        task = asyncio.create_task(self._monitor_service_health(service_name))
        self._monitoring_tasks[service_name] = task
    
    async def _monitor_service_health(self, service_name: str) -> None:
        """Monitor health of service instances"""
        health_check = self._health_checks.get(service_name)
        if not health_check:
            return
        
        while self._running:
            try:
                instances = self._services.get(service_name, [])
                for instance in instances:
                    try:
                        is_healthy = await health_check(instance)
                        instance.health = ServiceHealth.HEALTHY if is_healthy else ServiceHealth.UNHEALTHY
                        instance.last_check = datetime.now()
                    except Exception as e:
                        logger.warning(f"Health check failed for {service_name}@{instance.endpoint}: {e}")
                        instance.health = ServiceHealth.UNHEALTHY
                        instance.last_check = datetime.now()
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error monitoring {service_name}: {e}")
                await asyncio.sleep(30)  # Back off on error
    
    def _notify_event(self, event_type: str, data: Any) -> None:
        """Notify event callbacks"""
        for callback in self._event_callbacks:
            try:
                asyncio.create_task(callback(event_type, data))
            except Exception as e:
                logger.error(f"Error in event callback: {e}")
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health"""
        services = {}
        overall_status = ServiceHealth.HEALTHY
        
        for service_name in self._services:
            health = self.get_service_health(service_name)
            services[service_name] = health
            
            # Update overall status
            if health["status"] == ServiceHealth.UNHEALTHY:
                overall_status = ServiceHealth.UNHEALTHY
            elif health["status"] == ServiceHealth.DEGRADED and overall_status == ServiceHealth.HEALTHY:
                overall_status = ServiceHealth.DEGRADED
        
        return {
            "overall_status": overall_status.value,
            "timestamp": datetime.now().isoformat(),
            "total_services": len(services),
            "services": services
        }
