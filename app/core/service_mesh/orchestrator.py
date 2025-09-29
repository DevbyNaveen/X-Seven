"""
Startup Orchestrator for Coordinated Service Initialization
Handles complex service dependencies and startup sequences
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import networkx as nx
from .registry import ServiceRegistry, ServiceDefinition
from .container import ServiceContainer, ServiceLifecycle
from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from .health import HealthChecker

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    NOT_STARTED = "not_started"
    STARTING = "starting"
    RUNNING = "running"
    DEGRADED = "degraded"
    FAILED = "failed"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass
class ServiceDependency:
    """Represents a service dependency"""
    service_name: str
    required: bool = True
    health_check: bool = True
    timeout: float = 30.0


@dataclass
class StartupConfig:
    """Configuration for service startup"""
    max_concurrent_starts: int = 3
    health_check_interval: float = 5.0
    startup_timeout: float = 300.0
    retry_attempts: int = 3
    retry_delay: float = 2.0
    graceful_shutdown_timeout: float = 30.0


@dataclass
class ServiceState:
    """Current state of a service"""
    status: ServiceStatus = ServiceStatus.NOT_STARTED
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error: Optional[str] = None
    health_score: float = 0.0
    dependencies: Set[str] = field(default_factory=set)
    dependents: Set[str] = field(default_factory=set)


class StartupOrchestrator:
    """Coordinates complex service startup with dependency management"""
    
    def __init__(self, config: Optional[StartupConfig] = None):
        self.config = config or StartupConfig()
        self.registry = ServiceRegistry()
        self.container = ServiceContainer()
        self.health_checker = HealthChecker()
        self._service_states: Dict[str, ServiceState] = {}
        self._dependency_graph = nx.DiGraph()
        self._startup_semaphore = asyncio.Semaphore(self.config.max_concurrent_starts)
        self._running = False
        self._startup_order: List[str] = []
    
    def register_service(self, 
                        name: str,
                        service_class: type,
                        dependencies: List[str] = None,
                        health_check: Optional[Callable] = None,
                        config_class: Optional[type] = None,
                        lifecycle: ServiceLifecycle = ServiceLifecycle.SINGLETON,
                        required: bool = True) -> None:
        """Register a service with dependencies"""
        
        # Register with service registry
        definition = ServiceDefinition(
            name=name,
            service_type=service_class,
            dependencies=dependencies or [],
            config_class=config_class,
            health_check=health_check
        )
        self.registry.register_service(definition)
        
        # Register with container
        self.container.register(
            service_class,
            lifecycle=lifecycle,
            dependencies=dependencies,
            name=name
        )
        
        # Build dependency graph
        self._dependency_graph.add_node(name)
        for dep in dependencies or []:
            self._dependency_graph.add_edge(dep, name)
        
        # Initialize state
        self._service_states[name] = ServiceState(
            dependencies=set(dependencies or []),
            dependents=set()
        )
        
        # Update dependents
        for dep in dependencies or []:
            if dep in self._service_states:
                self._service_states[dep].dependents.add(name)
        
        logger.info(f"🎯 Registered service: {name} with dependencies: {dependencies or []}")
    
    async def start_all(self) -> Dict[str, Any]:
        """Start all services in dependency order"""
        logger.info("🚀 Starting service orchestration...")
        
        start_time = datetime.now()
        results = {
            "success": True,
            "services": {},
            "duration": 0,
            "errors": []
        }
        
        try:
            self._running = True
            
            # Calculate startup order using topological sort
            startup_order = self._calculate_startup_order()
            self._startup_order = startup_order
            
            logger.info(f"📋 Startup order: {startup_order}")
            
            # Start services in dependency order
            await self._start_services_sequentially(startup_order, results)
            
            # Wait for all services to be healthy
            await self._wait_for_healthy_services()
            
            # Start health monitoring
            await self._start_health_monitoring()
            
            duration = (datetime.now() - start_time).total_seconds()
            results["duration"] = duration
            
            if results["success"]:
                logger.info(f"✅ All services started successfully in {duration:.2f}s")
            else:
                logger.error(f"❌ Service startup failed after {duration:.2f}s")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Service orchestration failed: {e}")
            results["success"] = False
            results["errors"].append(str(e))
            
            # Attempt graceful shutdown
            await self.stop_all()
            return results
    
    async def stop_all(self) -> Dict[str, Any]:
        """Stop all services in reverse dependency order"""
        logger.info("🛑 Stopping all services...")
        
        stop_time = datetime.now()
        results = {
            "success": True,
            "services": {},
            "duration": 0
        }
        
        try:
            # Stop in reverse startup order
            stop_order = reversed(self._startup_order)
            
            tasks = []
            for service_name in stop_order:
                task = asyncio.create_task(self._stop_service(service_name))
                tasks.append(task)
            
            # Wait for all services to stop
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Stop container
            await self.container.stop_all()
            
            duration = (datetime.now() - stop_time).total_seconds()
            results["duration"] = duration
            
            logger.info(f"✅ All services stopped in {duration:.2f}s")
            self._running = False
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Service shutdown failed: {e}")
            results["success"] = False
            return results
    
    async def restart_service(self, service_name: str) -> bool:
        """Restart a specific service"""
        logger.info(f"🔄 Restarting service: {service_name}")
        
        try:
            # Stop the service
            await self._stop_service(service_name)
            
            # Start the service and its dependents
            affected_services = [service_name] + list(self._get_affected_services(service_name))
            await self._start_services_sequentially(affected_services, {})
            
            logger.info(f"✅ Service {service_name} restarted successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to restart service {service_name}: {e}")
            return False
    
    def get_service_status(self, service_name: str) -> Dict[str, Any]:
        """Get detailed status for a service"""
        if service_name not in self._service_states:
            return {"error": "Service not found"}
        
        state = self._service_states[service_name]
        return {
            "name": service_name,
            "status": state.status.value,
            "start_time": state.start_time.isoformat() if state.start_time else None,
            "duration": (datetime.now() - state.start_time).total_seconds() if state.start_time else 0,
            "health_score": state.health_score,
            "error": state.error,
            "dependencies": list(state.dependencies),
            "dependents": list(state.dependents)
        }
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status"""
        running_services = sum(1 for state in self._service_states.values() 
                             if state.status == ServiceStatus.RUNNING)
        failed_services = sum(1 for state in self._service_states.values() 
                            if state.status == ServiceStatus.FAILED)
        
        return {
            "total_services": len(self._service_states),
            "running_services": running_services,
            "failed_services": failed_services,
            "health_ratio": running_services / max(1, len(self._service_states)),
            "services": {
                name: self.get_service_status(name)
                for name in self._service_states
            }
        }
    
    def _calculate_startup_order(self) -> List[str]:
        """Calculate optimal startup order using topological sort"""
        try:
            # Use networkx for topological sorting
            if nx.is_directed_acyclic_graph(self._dependency_graph):
                return list(nx.topological_sort(self._dependency_graph))
            else:
                # Handle cycles - use simple dependency resolution
                logger.warning("Circular dependencies detected, using basic ordering")
                return list(self._service_states.keys())
        except Exception as e:
            logger.error(f"Error calculating startup order: {e}")
            return list(self._service_states.keys())
    
    async def _start_services_sequentially(self, service_order: List[str], results: Dict[str, Any]) -> None:
        """Start services in dependency order with concurrency limits"""
        
        for service_name in service_order:
            if not self._running:
                break
            
            async with self._startup_semaphore:
                try:
                    await self._start_service(service_name, results)
                except Exception as e:
                    logger.error(f"❌ Failed to start {service_name}: {e}")
                    results["errors"].append(f"{service_name}: {str(e)}")
                    
                    if self._is_critical_service(service_name):
                        results["success"] = False
                        raise
    
    async def _start_service(self, service_name: str, results: Dict[str, Any]) -> None:
        """Start a single service"""
        state = self._service_states[service_name]
        
        if state.status != ServiceStatus.NOT_STARTED:
            return
        
        logger.info(f"🚀 Starting service: {service_name}")
        state.status = ServiceStatus.STARTING
        state.start_time = datetime.now()
        
        try:
            # Create circuit breaker for this service
            breaker_config = CircuitBreakerConfig(
                name=f"{service_name}_startup",
                failure_threshold=2,
                recovery_timeout=30
            )
            breaker = self._get_circuit_breaker_manager().create_breaker(
                f"{service_name}_startup", breaker_config
            )
            
            # Start service with circuit breaker protection
            await breaker.call(self._initialize_service, service_name)
            
            state.status = ServiceStatus.RUNNING
            state.health_score = 1.0
            results["services"][service_name] = {
                "status": "success",
                "duration": (datetime.now() - state.start_time).total_seconds()
            }
            
            logger.info(f"✅ Service {service_name} started successfully")
            
        except Exception as e:
            state.status = ServiceStatus.FAILED
            state.error = str(e)
            results["services"][service_name] = {
                "status": "failed",
                "error": str(e),
                "duration": (datetime.now() - state.start_time).total_seconds()
            }
            logger.error(f"❌ Service {service_name} failed to start: {e}")
    
    async def _initialize_service(self, service_name: str) -> None:
        """Initialize a single service"""
        # Get service instance from container
        definition = self.registry.get_service_definition(service_name)
        if definition:
            service_class = definition.service_type
            await self.container.get_service(service_class, name=service_name)
    
    async def _stop_service(self, service_name: str) -> None:
        """Stop a single service"""
        state = self._service_states[service_name]
        
        if state.status not in [ServiceStatus.RUNNING, ServiceStatus.DEGRADED]:
            return
        
        logger.info(f"🛑 Stopping service: {service_name}")
        state.status = ServiceStatus.STOPPING
        state.end_time = datetime.now()
        
        try:
            # Graceful shutdown
            await asyncio.sleep(0.1)  # Allow cleanup
            state.status = ServiceStatus.STOPPED
            logger.info(f"✅ Service {service_name} stopped")
            
        except Exception as e:
            logger.error(f"❌ Error stopping service {service_name}: {e}")
    
    async def _wait_for_healthy_services(self) -> None:
        """Wait for required services to become healthy"""
        max_wait = self.config.startup_timeout
        start_time = datetime.now()
        
        while (datetime.now() - start_time).total_seconds() < max_wait:
            unhealthy_services = []
            for service_name, state in self._service_states.items():
                if state.status == ServiceStatus.RUNNING:
                    # Only wait for required services to be healthy
                    definition = self.registry.get_service_definition(service_name)
                    if definition and getattr(definition, 'required', True):
                        # Check health
                        is_healthy = await self._check_service_health(service_name)
                        if not is_healthy:
                            unhealthy_services.append(service_name)
            
            if not unhealthy_services:
                break
            
            logger.info(f"⏳ Waiting for services to become healthy: {unhealthy_services}")
            await asyncio.sleep(self.config.health_check_interval)
    
    async def _check_service_health(self, service_name: str) -> bool:
        """Check if a service is healthy"""
        try:
            # Use health checker if available
            return await self.health_checker.check_service_health(service_name)
        except Exception:
            return True  # Assume healthy if no specific check
    
    async def _start_health_monitoring(self) -> None:
        """Start continuous health monitoring"""
        logger.info("🔍 Starting health monitoring...")
        await self.health_checker.start_monitoring()
    
    def _get_affected_services(self, service_name: str) -> Set[str]:
        """Get all services that depend on the given service"""
        affected = set()
        
        def add_dependents(name: str):
            for dependent in self._service_states[name].dependents:
                affected.add(dependent)
                add_dependents(dependent)
        
        add_dependents(service_name)
        return affected
    
    def _is_critical_service(self, service_name: str) -> bool:
        """Check if a service is critical for startup"""
        # Core services are always critical
        critical_services = {
            "database", "redis", "kafka", "temporal"
        }
        return service_name.lower() in critical_services
    
    def _get_circuit_breaker_manager(self):
        """Get circuit breaker manager"""
        from .circuit_breaker import get_circuit_manager
        return get_circuit_manager()


# Global orchestrator instance
_orchestrator: Optional[StartupOrchestrator] = None


def get_startup_orchestrator() -> StartupOrchestrator:
    """Get global startup orchestrator"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = StartupOrchestrator()
    return _orchestrator
