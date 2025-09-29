"""
Dependency Injection Container
Manages service lifecycles and dependencies
"""

import asyncio
import logging
from typing import Any, Dict, Optional, Type, Callable, List
from enum import Enum
from dataclasses import dataclass
from contextlib import asynccontextmanager
import inspect

logger = logging.getLogger(__name__)


class ServiceLifecycle(Enum):
    SINGLETON = "singleton"      # One instance for entire application
    TRANSIENT = "transient"      # New instance per request
    SCOPED = "scoped"           # One instance per scope/context


@dataclass
class ServiceRegistration:
    """Service registration information"""
    service_type: Type
    implementation_type: Optional[Type] = None
    factory: Optional[Callable] = None
    lifecycle: ServiceLifecycle = ServiceLifecycle.SINGLETON
    dependencies: List[str] = None
    instance: Any = None
    is_initialized: bool = False


class ServiceContainer:
    """Dependency injection container for service management"""
    
    def __init__(self):
        self._services: Dict[str, ServiceRegistration] = {}
        self._singletons: Dict[str, Any] = {}
        self._scoped_instances: Dict[str, Dict[str, Any]] = {}
        self._running = False
        self._startup_order: List[str] = []
        self._shutdown_callbacks: List[Callable] = []
    
    def register(self, 
                 service_type: Type,
                 implementation_type: Optional[Type] = None,
                 factory: Optional[Callable] = None,
                 lifecycle: ServiceLifecycle = ServiceLifecycle.SINGLETON,
                 dependencies: Optional[List[str]] = None,
                 name: Optional[str] = None) -> None:
        """Register a service with the container"""
        
        service_name = name or service_type.__name__
        
        if factory and implementation_type:
            raise ValueError("Cannot specify both factory and implementation_type")
        
        if not factory and not implementation_type:
            implementation_type = service_type
        
        registration = ServiceRegistration(
            service_type=service_type,
            implementation_type=implementation_type,
            factory=factory,
            lifecycle=lifecycle,
            dependencies=dependencies or []
        )
        
        self._services[service_name] = registration
        logger.info(f"📦 Registered service: {service_name} ({lifecycle.value})")
    
    def register_singleton(self, service_type: Type, implementation_type: Optional[Type] = None, **kwargs) -> None:
        """Register a singleton service"""
        self.register(service_type, implementation_type, lifecycle=ServiceLifecycle.SINGLETON, **kwargs)
    
    def register_transient(self, service_type: Type, implementation_type: Optional[Type] = None, **kwargs) -> None:
        """Register a transient service"""
        self.register(service_type, implementation_type, lifecycle=ServiceLifecycle.TRANSIENT, **kwargs)
    
    def register_scoped(self, service_type: Type, implementation_type: Optional[Type] = None, **kwargs) -> None:
        """Register a scoped service"""
        self.register(service_type, implementation_type, lifecycle=ServiceLifecycle.SCOPED, **kwargs)
    
    def register_instance(self, instance: Any, name: Optional[str] = None) -> None:
        """Register an existing instance as singleton"""
        service_name = name or type(instance).__name__
        registration = ServiceRegistration(
            service_type=type(instance),
            instance=instance,
            lifecycle=ServiceLifecycle.SINGLETON,
            is_initialized=True
        )
        self._services[service_name] = registration
        self._singletons[service_name] = instance
        logger.info(f"📦 Registered instance: {service_name}")
    
    async def get_service(self, service_type: Type, name: Optional[str] = None, scope_id: Optional[str] = None) -> Any:
        """Get a service instance"""
        service_name = name or service_type.__name__
        
        if service_name not in self._services:
            raise KeyError(f"Service '{service_name}' not registered")
        
        registration = self._services[service_name]
        
        if registration.lifecycle == ServiceLifecycle.SINGLETON:
            return await self._get_singleton(service_name, registration)
        elif registration.lifecycle == ServiceLifecycle.TRANSIENT:
            return await self._create_instance(registration)
        elif registration.lifecycle == ServiceLifecycle.SCOPED:
            return await self._get_scoped_instance(service_name, registration, scope_id)
        else:
            raise ValueError(f"Unknown lifecycle: {registration.lifecycle}")
    
    async def _get_singleton(self, service_name: str, registration: ServiceRegistration) -> Any:
        """Get or create singleton instance"""
        if service_name in self._singletons:
            return self._singletons[service_name]
        
        instance = await self._create_instance(registration)
        self._singletons[service_name] = instance
        return instance
    
    async def _get_scoped_instance(self, service_name: str, registration: ServiceRegistration, scope_id: Optional[str]) -> Any:
        """Get or create scoped instance"""
        if scope_id is None:
            raise ValueError("Scope ID required for scoped services")
        
        if scope_id not in self._scoped_instances:
            self._scoped_instances[scope_id] = {}
        
        if service_name not in self._scoped_instances[scope_id]:
            instance = await self._create_instance(registration)
            self._scoped_instances[scope_id][service_name] = instance
        
        return self._scoped_instances[scope_id][service_name]
    
    async def _create_instance(self, registration: ServiceRegistration) -> Any:
        """Create a new service instance"""
        try:
            # Resolve dependencies
            dependencies = {}
            for dep_name in registration.dependencies:
                dep_instance = await self.get_service(type, name=dep_name)
                dependencies[dep_name] = dep_instance
            
            # Create instance
            if registration.factory:
                if asyncio.iscoroutinefunction(registration.factory):
                    instance = await registration.factory(**dependencies)
                else:
                    instance = registration.factory(**dependencies)
            elif registration.implementation_type:
                # Check if constructor expects dependencies
                sig = inspect.signature(registration.implementation_type.__init__)
                params = list(sig.parameters.keys())[1:]  # Skip 'self'
                
                kwargs = {}
                for param in params:
                    if param in dependencies:
                        kwargs[param] = dependencies[param]
                
                instance = registration.implementation_type(**kwargs)
            else:
                instance = registration.service_type()
            
            # Initialize if needed
            if hasattr(instance, 'initialize') and not registration.is_initialized:
                if asyncio.iscoroutinefunction(instance.initialize):
                    await instance.initialize()
                else:
                    instance.initialize()
            
            registration.is_initialized = True
            return instance
            
        except Exception as e:
            logger.error(f"Failed to create instance for {registration.service_type}: {e}")
            raise
    
    async def start_all(self) -> None:
        """Start all singleton services"""
        logger.info("🚀 Starting all services...")
        
        # Calculate startup order based on dependencies
        startup_order = self._calculate_startup_order()
        
        for service_name in startup_order:
            try:
                registration = self._services[service_name]
                if registration.lifecycle == ServiceLifecycle.SINGLETON:
                    await self.get_service(type, name=service_name)
                    logger.info(f"✅ Started service: {service_name}")
            except Exception as e:
                logger.error(f"❌ Failed to start service {service_name}: {e}")
                raise
        
        self._running = True
        logger.info("✅ All services started successfully")
    
    async def stop_all(self) -> None:
        """Stop all services and cleanup"""
        logger.info("🛑 Stopping all services...")
        
        # Run shutdown callbacks
        for callback in self._shutdown_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                logger.error(f"Error in shutdown callback: {e}")
        
        # Cleanup singletons
        for service_name, instance in list(self._singletons.items()):
            try:
                if hasattr(instance, 'shutdown'):
                    if asyncio.iscoroutinefunction(instance.shutdown):
                        await instance.shutdown()
                    else:
                        instance.shutdown()
                logger.info(f"✅ Stopped service: {service_name}")
            except Exception as e:
                logger.error(f"Error stopping service {service_name}: {e}")
        
        # Cleanup scoped instances
        for scope_instances in self._scoped_instances.values():
            for service_name, instance in scope_instances.items():
                try:
                    if hasattr(instance, 'shutdown'):
                        if asyncio.iscoroutinefunction(instance.shutdown):
                            await instance.shutdown()
                        else:
                            instance.shutdown()
                except Exception as e:
                    logger.error(f"Error stopping scoped service {service_name}: {e}")
        
        self._singletons.clear()
        self._scoped_instances.clear()
        self._running = False
        logger.info("✅ All services stopped")
    
    def _calculate_startup_order(self) -> List[str]:
        """Calculate service startup order based on dependencies"""
        visited = set()
        result = []
        
        def visit(service_name: str):
            if service_name in visited:
                return
            
            visited.add(service_name)
            
            # Visit dependencies first
            registration = self._services.get(service_name)
            if registration:
                for dep_name in registration.dependencies:
                    if dep_name in self._services:
                        visit(dep_name)
            
            result.append(service_name)
        
        for service_name in self._services:
            visit(service_name)
        
        return result
    
    def add_shutdown_callback(self, callback: Callable) -> None:
        """Add shutdown callback"""
        self._shutdown_callbacks.append(callback)
    
    def create_scope(self, scope_id: str) -> "ServiceScope":
        """Create a new service scope"""
        return ServiceScope(self, scope_id)
    
    def get_registered_services(self) -> List[str]:
        """Get list of registered service names"""
        return list(self._services.keys())
    
    def get_service_info(self, service_name: str) -> Dict[str, Any]:
        """Get information about a service"""
        if service_name not in self._services:
            return {}
        
        registration = self._services[service_name]
        return {
            "name": service_name,
            "type": str(registration.service_type),
            "lifecycle": registration.lifecycle.value,
            "dependencies": registration.dependencies,
            "is_initialized": registration.is_initialized,
            "singleton_instance": service_name in self._singletons
        }


class ServiceScope:
    """Scoped service context"""
    
    def __init__(self, container: ServiceContainer, scope_id: str):
        self.container = container
        self.scope_id = scope_id
    
    async def get_service(self, service_type: Type, name: Optional[str] = None) -> Any:
        """Get service within this scope"""
        return await self.container.get_service(service_type, name, self.scope_id)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Cleanup scoped instances
        if self.scope_id in self.container._scoped_instances:
            del self.container._scoped_instances[self.scope_id]


# Global service container
_container: Optional[ServiceContainer] = None


def get_service_container() -> ServiceContainer:
    """Get global service container"""
    global _container
    if _container is None:
        _container = ServiceContainer()
    return _container
