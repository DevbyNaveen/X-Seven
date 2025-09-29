"""
Service Mesh Integration Layer
Replaces the current ad-hoc service initialization with modern dependency management
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from .registry import ServiceRegistry, ServiceDefinition
from .container import ServiceContainer, ServiceLifecycle
from .orchestrator import StartupOrchestrator, ServiceStatus
from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from .health import HealthChecker, HealthStatus
from .config import ConfigManager

logger = logging.getLogger(__name__)


class ServiceMeshIntegration:
    """Main integration layer for service mesh"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.orchestrator = StartupOrchestrator()
        self.health_checker = HealthChecker()
        self._initialized = False
    
    async def initialize(self) -> Dict[str, Any]:
        """Initialize the service mesh and all services"""
        if self._initialized:
            return {"success": True, "message": "Already initialized"}
        
        start_time = datetime.now()
        
        try:
            logger.info("🚀 Initializing Service Mesh...")
            
            # Validate configuration
            validation_errors = self.config_manager.validate_config()
            if validation_errors:
                return {
                    "success": False,
                    "errors": validation_errors,
                    "message": "Configuration validation failed"
                }
            
            # Register all services with dependencies
            await self._register_services()
            
            # Start the orchestrator
            startup_results = await self.orchestrator.start_all()
            
            # Start health monitoring
            await self.health_checker.start_monitoring()
            
            duration = (datetime.now() - start_time).total_seconds()
            
            if startup_results["success"]:
                self._initialized = True
                logger.info(f"✅ Service Mesh initialized in {duration:.2f}s")
                return {
                    "success": True,
                    "duration": duration,
                    "services": startup_results.get("services", {}),
                    "health": await self.health_checker.get_system_health()
                }
            else:
                logger.error(f"❌ Service Mesh initialization failed")
                return startup_results
                
        except Exception as e:
            logger.error(f"❌ Service Mesh initialization error: {e}")
            return {
                "success": False,
                "error": str(e),
                "duration": (datetime.now() - start_time).total_seconds()
            }
    
    async def shutdown(self) -> Dict[str, Any]:
        """Gracefully shutdown the service mesh"""
        if not self._initialized:
            return {"success": True, "message": "Not initialized"}
        
        start_time = datetime.now()
        
        try:
            logger.info("🛑 Shutting down Service Mesh...")
            
            # Stop health monitoring
            await self.health_checker.stop_monitoring()
            
            # Stop all services
            shutdown_results = await self.orchestrator.stop_all()
            
            # Stop configuration monitoring
            self.config_manager.stop_file_monitoring()
            
            duration = (datetime.now() - start_time).total_seconds()
            
            self._initialized = False
            logger.info(f"✅ Service Mesh shutdown completed in {duration:.2f}s")
            
            return {
                "success": True,
                "duration": duration,
                "services": shutdown_results.get("services", {})
            }
            
        except Exception as e:
            logger.error(f"❌ Service Mesh shutdown error: {e}")
            return {
                "success": False,
                "error": str(e),
                "duration": (datetime.now() - start_time).total_seconds()
            }
    
    async def get_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        return {
            "initialized": self._initialized,
            "orchestrator_status": self.orchestrator.get_system_status(),
            "health_status": await self.health_checker.get_system_health(),
            "config_summary": self.config_manager.get_config_summary()
        }
    
    async def restart_service(self, service_name: str) -> Dict[str, Any]:
        """Restart a specific service"""
        try:
            success = await self.orchestrator.restart_service(service_name)
            return {
                "success": success,
                "service": service_name,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "service": service_name
            }
    
    async def _register_services(self):
        """Register all services with their dependencies"""
        config = self.config_manager.get_config()
        
        # Register Database Service
        self.orchestrator.register_service(
            name="database",
            service_class=DatabaseService,
            dependencies=[],
            health_check=self._check_database_health,
            lifecycle=ServiceLifecycle.SINGLETON,
            required=True
        )
        
        # Register Redis Service
        self.orchestrator.register_service(
            name="redis",
            service_class=RedisService,
            dependencies=[],
            health_check=self._check_redis_health,
            lifecycle=ServiceLifecycle.SINGLETON,
            required=True  # Redis is required for production
        )
        
        # Register Kafka Service
        self.orchestrator.register_service(
            name="kafka",
            service_class=KafkaService,
            dependencies=[],
            health_check=self._check_kafka_health,
            lifecycle=ServiceLifecycle.SINGLETON,
            required=True
        )
        
        # Register Temporal Service
        self.orchestrator.register_service(
            name="temporal",
            service_class=TemporalService,
            dependencies=[],
            health_check=self._check_temporal_health,
            lifecycle=ServiceLifecycle.SINGLETON,
            required=True  # Temporal is required for production
        )
        
        # Register CrewAI Service
        self.orchestrator.register_service(
            name="crewai",
            service_class=CrewAIService,
            dependencies=["database"],
            health_check=self._check_crewai_health,
            lifecycle=ServiceLifecycle.SINGLETON,
            required=True
        )
        
        # Register DSPy Service
        self.orchestrator.register_service(
            name="dspy",
            service_class=DSPyService,
            dependencies=["database"],
            health_check=self._check_dspy_health,
            lifecycle=ServiceLifecycle.SINGLETON,
            required=True
        )
        
        # Register Voice Service
        self.orchestrator.register_service(
            name="voice",
            service_class=VoiceService,
            dependencies=["dspy", "crewai", "temporal"],
            health_check=self._check_voice_health,
            lifecycle=ServiceLifecycle.SINGLETON,
            required=True  # Voice service is required for production
        )
    
    async def _check_database_health(self, instance) -> bool:
        """Check database health"""
        try:
            from app.config.database import get_supabase_client
            client = get_supabase_client()
            
            # Test connection by getting session information
            # This verifies basic connectivity to the database
            session = client.auth.get_session()
            
            # Additional verification - check if we can access a basic table
            # For instance, try a simple query to verify read access
            try:
                result = client.table('businesses').select('count').execute()
                if hasattr(result, 'data'):
                    logger.info(f"Database connection verified with table access")
            except Exception as e:
                # Table might not exist yet or permissions issue
                # Log but don't fail the health check just on this
                logger.warning(f"Table access check failed: {e}")
            
            # If we get here without exception, basic connectivity works
            return True
            
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False  # Report actual failure state
    
    async def _check_redis_health(self, instance) -> bool:
        """Check Redis health"""
        try:
            from app.config.settings import settings
            import redis.asyncio as redis
            client = redis.from_url(settings.REDIS_URL)
            return await client.ping()
        except Exception:
            return False
    
    async def _check_kafka_health(self, instance) -> bool:
        """Check Kafka health"""
        try:
            from app.core.kafka.manager import get_kafka_manager
            kafka_manager = await get_kafka_manager()
            
            # First verify initialization and running state
            if not kafka_manager._initialized:
                logger.error("Kafka manager not initialized")
                return False
                
            if not kafka_manager._running:
                logger.error("Kafka manager not running")
                return False
                
            # Verify consumers are active
            if len(kafka_manager.consumers) == 0:
                logger.error("No active Kafka consumers")
                return False
            
            # Full health check
            health = kafka_manager.get_health_status()
            healthy = health.get("status") == "healthy"
            
            if not healthy:
                logger.error(f"Kafka health check failed: {health}")
                
            return healthy
            
        except Exception as e:
            logger.error(f"Kafka health check failed with exception: {e}")
            return False
    
    async def _check_temporal_health(self, instance) -> bool:
        """Check Temporal health"""
        try:
            from app.workflows.temporal_integration import get_temporal_manager
            temporal_manager = get_temporal_manager()
            
            # First check if manager is properly initialized
            if not hasattr(temporal_manager, '_initialized') or not temporal_manager._initialized:
                logger.error("Temporal manager not properly initialized")
                return False
                
            # If disabled, report as unhealthy
            if hasattr(temporal_manager, '_disabled') and temporal_manager._disabled:
                logger.error("Temporal service is disabled due to connection issues")
                return False
            
            # Check connection to the Temporal server
            is_ready = await temporal_manager.is_ready()
            
            if not is_ready:
                logger.error("Temporal service is not ready")
                
            return is_ready
            
        except Exception as e:
            logger.error(f"Temporal health check failed with exception: {e}")
            return False
    
    async def _check_crewai_health(self, instance) -> bool:
        """Check CrewAI health"""
        try:
            from app.services.ai.crewai_orchestrator import get_crewai_orchestrator
            orchestrator = get_crewai_orchestrator()
            return len(orchestrator.agents) > 0
        except Exception:
            return False
    
    async def _check_dspy_health(self, instance) -> bool:
        """Check DSPy health"""
        try:
            from app.core.ai.dspy_enhanced_handler import DSPyEnhancedAIHandler
            handler = DSPyEnhancedAIHandler()
            status = handler.get_dspy_status()
            return status.get("dspy_initialized", False)
        except Exception:
            return False
    
    async def _check_voice_health(self, instance) -> bool:
        """Check Voice service health"""
        try:
            from app.core.voice.voice_pipeline import VoicePipeline
            pipeline = VoicePipeline()
            return await pipeline.initialize()
        except Exception:
            return False


# Service implementations for the service mesh
class DatabaseService:
    """Database service wrapper"""
    
    def __init__(self):
        self.client = None
    
    async def initialize(self):
        from app.config.database import get_supabase_client
        self.client = get_supabase_client()
    
    async def shutdown(self):
        if self.client:
            # Cleanup database connections
            pass


class RedisService:
    """Redis service wrapper"""
    
    def __init__(self):
        self.client = None
    
    async def initialize(self):
        from app.config.settings import settings
        import redis.asyncio as redis
        self.client = redis.from_url(settings.REDIS_URL)
    
    async def shutdown(self):
        if self.client:
            await self.client.close()


class KafkaService:
    """Kafka service wrapper"""
    
    def __init__(self):
        self.manager = None
    
    async def initialize(self):
        from app.core.kafka.manager import get_kafka_manager
        self.manager = await get_kafka_manager()
        await self.manager.start()
    
    async def shutdown(self):
        if self.manager:
            await self.manager.stop()


class TemporalService:
    """Temporal service wrapper"""
    
    def __init__(self):
        self.manager = None
    
    async def initialize(self):
        from app.workflows.temporal_integration import get_temporal_manager
        self.manager = get_temporal_manager()
        await self.manager.initialize()
    
    async def shutdown(self):
        if self.manager:
            await self.manager.close()


class CrewAIService:
    """CrewAI service wrapper"""
    
    def __init__(self):
        self.orchestrator = None
    
    async def initialize(self):
        from app.services.ai.crewai_orchestrator import get_crewai_orchestrator
        self.orchestrator = get_crewai_orchestrator()
    
    async def shutdown(self):
        # CrewAI orchestrator doesn't need explicit shutdown
        pass


class DSPyService:
    """DSPy service wrapper"""
    
    def __init__(self):
        self.initialized = False
    
    async def initialize(self):
        from app.core.dspy.startup import startup_dspy_system
        await startup_dspy_system()
        self.initialized = True
    
    async def shutdown(self):
        # DSPy doesn't need explicit shutdown
        pass


class VoiceService:
    """Voice service wrapper"""
    
    def __init__(self):
        self.pipeline = None
    
    async def initialize(self):
        from app.core.voice.integration_manager import initialize_voice_integration
        success = await initialize_voice_integration()
        if success:
            from app.core.voice.voice_pipeline import VoicePipeline
            self.pipeline = VoicePipeline()
            await self.pipeline.initialize()
    
    async def shutdown(self):
        if self.pipeline:
            await self.pipeline.stop()


# Global service mesh integration
_service_mesh: Optional[ServiceMeshIntegration] = None


async def get_service_mesh() -> ServiceMeshIntegration:
    """Get global service mesh integration"""
    global _service_mesh
    if _service_mesh is None:
        _service_mesh = ServiceMeshIntegration()
    return _service_mesh
