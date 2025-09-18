"""
Self-Healing System - Automatic Recovery and Resilience
Provides comprehensive self-healing capabilities for the global AI system
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, Callable, Awaitable, List
from datetime import datetime, timedelta
import functools

class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    RECOVERING = "recovering"

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, requests blocked
    HALF_OPEN = "half_open"  # Testing recovery

@dataclass
class HealthMetrics:
    """Health metrics for monitoring agent status"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    average_response_time: float = 0.0
    consecutive_failures: int = 0
    consecutive_successes: int = 0

@dataclass
class CircuitBreaker:
    """Circuit breaker implementation for fault tolerance"""
    failure_threshold: int = 5
    recovery_timeout: int = 60  # seconds
    success_threshold: int = 3
    state: CircuitState = CircuitState.CLOSED
    last_failure_time: Optional[datetime] = None
    consecutive_successes: int = 0
    consecutive_failures: int = 0

    def can_execute(self) -> bool:
        """Check if request can be executed"""
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            if datetime.now() - self.last_failure_time > timedelta(seconds=self.recovery_timeout):
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        elif self.state == CircuitState.HALF_OPEN:
            return True
        return False

    def record_success(self):
        """Record successful execution"""
        self.consecutive_successes += 1
        self.consecutive_failures = 0
        self.last_failure_time = None

        if self.state == CircuitState.HALF_OPEN and self.consecutive_successes >= self.success_threshold:
            self.state = CircuitState.CLOSED
            self.consecutive_successes = 0

    def record_failure(self):
        """Record failed execution"""
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.last_failure_time = datetime.now()

        if self.consecutive_failures >= self.failure_threshold:
            self.state = CircuitState.OPEN

class SelfHealingManager:
    """
    Central coordinator for self-healing across all AI agents
    Provides automatic recovery, monitoring, and fault tolerance
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.health_monitor = HealthMonitor()
        self.recovery_strategies = RecoveryStrategies()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.fallback_strategies: Dict[str, Callable] = {}
        self.agent_health: Dict[str, HealthStatus] = {}
        self.recovery_tasks: Dict[str, asyncio.Task] = {}

    def register_agent(self, agent_name: str, agent_instance: Any):
        """Register an agent for self-healing monitoring"""
        self.circuit_breakers[agent_name] = CircuitBreaker()
        self.agent_health[agent_name] = HealthStatus.HEALTHY
        self.health_monitor.register_agent(agent_name)

        # Register fallback strategies
        if hasattr(agent_instance, '_fallback_strategies'):
            self.fallback_strategies[agent_name] = agent_instance._fallback_strategies

        self.logger.info(f"✅ Registered agent '{agent_name}' for self-healing")

    async def execute_with_healing(self, agent_name: str, operation: Callable[[], Awaitable[Any]],
                                 fallback_operation: Optional[Callable[[], Awaitable[Any]]] = None) -> Any:
        """
        Execute operation with comprehensive self-healing protection

        Args:
            agent_name: Name of the agent executing the operation
            operation: The main operation to execute
            fallback_operation: Optional fallback if main operation fails

        Returns:
            Result of operation or fallback
        """
        circuit_breaker = self.circuit_breakers.get(agent_name)
        if not circuit_breaker:
            # Agent not registered, execute normally
            return await operation()

        # Check circuit breaker
        if not circuit_breaker.can_execute():
            self.logger.warning(f"🚫 Circuit breaker OPEN for {agent_name}, using fallback")
            return await self._execute_fallback(agent_name, operation, fallback_operation)

        start_time = time.time()
        try:
            # Execute with retry mechanism
            result = await self._execute_with_retry(agent_name, operation)

            # Record success
            execution_time = time.time() - start_time
            self.health_monitor.record_success(agent_name, execution_time)
            circuit_breaker.record_success()
            self.agent_health[agent_name] = HealthStatus.HEALTHY

            return result

        except Exception as e:
            # Record failure
            execution_time = time.time() - start_time
            self.health_monitor.record_failure(agent_name, str(e), execution_time)
            circuit_breaker.record_failure()

            # Update health status
            self._update_health_status(agent_name)

            # Trigger recovery if needed
            if self.agent_health[agent_name] in [HealthStatus.UNHEALTHY, HealthStatus.DEGRADED]:
                await self._trigger_recovery(agent_name)

            # Try fallback
            self.logger.error(f"💥 Operation failed for {agent_name}: {e}")
            return await self._execute_fallback(agent_name, operation, fallback_operation)

    async def _execute_with_retry(self, agent_name: str, operation: Callable[[], Awaitable[Any]]) -> Any:
        """Execute operation with exponential backoff retry"""
        max_retries = 3
        base_delay = 1.0

        for attempt in range(max_retries + 1):
            try:
                return await operation()
            except Exception as e:
                if attempt == max_retries:
                    raise e

                delay = base_delay * (2 ** attempt)
                self.logger.warning(f"⚠️ Retry {attempt + 1}/{max_retries} for {agent_name} after {delay}s: {e}")
                await asyncio.sleep(delay)

    async def _execute_fallback(self, agent_name: str, original_operation: Callable[[], Awaitable[Any]],
                              fallback_operation: Optional[Callable[[], Awaitable[Any]]] = None) -> Any:
        """Execute fallback operation when main operation fails"""

        # Try custom fallback first
        if fallback_operation:
            try:
                self.logger.info(f"🔄 Using custom fallback for {agent_name}")
                return await fallback_operation()
            except Exception as e:
                self.logger.error(f"💥 Custom fallback failed for {agent_name}: {e}")

        # Try registered fallback strategy
        if agent_name in self.fallback_strategies:
            try:
                self.logger.info(f"🔄 Using registered fallback for {agent_name}")
                return await self.fallback_strategies[agent_name]()
            except Exception as e:
                self.logger.error(f"💥 Registered fallback failed for {agent_name}: {e}")

        # Use default fallback
        self.logger.warning(f"🔄 Using default fallback for {agent_name}")
        return await self._default_fallback(agent_name, original_operation)

    async def _default_fallback(self, agent_name: str, operation: Callable[[], Awaitable[Any]]) -> Any:
        """Default fallback when all else fails"""
        if "intent" in agent_name.lower():
            return {"intent": "other", "confidence": 0.1, "reasoning": "Fallback due to system issues"}
        elif "slot" in agent_name.lower():
            return {"status": "error", "message": "Unable to process request right now"}
        elif "rag" in agent_name.lower():
            return {"answer": "I'm having trouble retrieving information. Please try again.", "confidence": 0.0}
        elif "execution" in agent_name.lower():
            return {"success": False, "message": "Service temporarily unavailable"}
        else:
            return {"error": "Service temporarily unavailable, please try again"}

    def _update_health_status(self, agent_name: str):
        """Update agent health status based on recent performance"""
        metrics = self.health_monitor.get_metrics(agent_name)
        if not metrics:
            return

        success_rate = metrics.successful_requests / max(metrics.total_requests, 1)

        if success_rate >= 0.95:
            self.agent_health[agent_name] = HealthStatus.HEALTHY
        elif success_rate >= 0.80:
            self.agent_health[agent_name] = HealthStatus.DEGRADED
        else:
            self.agent_health[agent_name] = HealthStatus.UNHEALTHY

    async def _trigger_recovery(self, agent_name: str):
        """Trigger recovery process for unhealthy agent"""
        if agent_name in self.recovery_tasks and not self.recovery_tasks[agent_name].done():
            return  # Recovery already in progress

        self.logger.info(f"🚑 Triggering recovery for {agent_name}")
        self.agent_health[agent_name] = HealthStatus.RECOVERING

        # Start recovery task
        task = asyncio.create_task(self._recovery_process(agent_name))
        self.recovery_tasks[agent_name] = task

    async def _recovery_process(self, agent_name: str):
        """Recovery process for unhealthy agent"""
        try:
            # Reset circuit breaker
            if agent_name in self.circuit_breakers:
                self.circuit_breakers[agent_name].state = CircuitState.HALF_OPEN
                self.circuit_breakers[agent_name].consecutive_failures = 0

            # Wait for recovery period
            await asyncio.sleep(30)

            # Test recovery with a simple operation
            await self._test_recovery(agent_name)

            self.logger.info(f"✅ Recovery completed for {agent_name}")

        except Exception as e:
            self.logger.error(f"💥 Recovery failed for {agent_name}: {e}")
            self.agent_health[agent_name] = HealthStatus.UNHEALTHY

    async def _test_recovery(self, agent_name: str):
        """Test if agent has recovered"""
        # Simple health check - this would be customized per agent
        self.health_monitor.record_success(agent_name, 0.1)
        self.agent_health[agent_name] = HealthStatus.HEALTHY

    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status"""
        total_agents = len(self.agent_health)
        healthy_count = sum(1 for status in self.agent_health.values() if status == HealthStatus.HEALTHY)
        degraded_count = sum(1 for status in self.agent_health.values() if status == HealthStatus.DEGRADED)
        unhealthy_count = sum(1 for status in self.agent_health.values() if status == HealthStatus.UNHEALTHY)

        overall_status = HealthStatus.HEALTHY
        if unhealthy_count > 0:
            overall_status = HealthStatus.UNHEALTHY
        elif degraded_count > 0:
            overall_status = HealthStatus.DEGRADED

        return {
            "overall_status": overall_status.value,
            "agents": {
                "total": total_agents,
                "healthy": healthy_count,
                "degraded": degraded_count,
                "unhealthy": unhealthy_count
            },
            "circuit_breakers": {
                name: {
                    "state": cb.state.value,
                    "consecutive_failures": cb.consecutive_failures,
                    "last_failure": cb.last_failure_time.isoformat() if cb.last_failure_time else None
                }
                for name, cb in self.circuit_breakers.items()
            },
            "timestamp": datetime.now().isoformat()
        }

class HealthMonitor:
    """Monitor health metrics for all agents"""

    def __init__(self):
        self.metrics: Dict[str, HealthMetrics] = {}
        self.logger = logging.getLogger(__name__)

    def register_agent(self, agent_name: str):
        """Register agent for monitoring"""
        self.metrics[agent_name] = HealthMetrics()

    def record_success(self, agent_name: str, response_time: float):
        """Record successful operation"""
        if agent_name not in self.metrics:
            return

        metrics = self.metrics[agent_name]
        metrics.total_requests += 1
        metrics.successful_requests += 1
        metrics.last_success = datetime.now()
        metrics.consecutive_failures = 0
        metrics.consecutive_successes += 1

        # Update average response time
        if metrics.average_response_time == 0:
            metrics.average_response_time = response_time
        else:
            metrics.average_response_time = (metrics.average_response_time + response_time) / 2

    def record_failure(self, agent_name: str, error: str, response_time: float):
        """Record failed operation"""
        if agent_name not in self.metrics:
            return

        metrics = self.metrics[agent_name]
        metrics.total_requests += 1
        metrics.failed_requests += 1
        metrics.last_failure = datetime.now()
        metrics.consecutive_successes = 0
        metrics.consecutive_failures += 1

        self.logger.warning(f"❌ Agent {agent_name} failure: {error}")

    def get_metrics(self, agent_name: str) -> Optional[HealthMetrics]:
        """Get health metrics for agent"""
        return self.metrics.get(agent_name)

class RecoveryStrategies:
    """Collection of recovery strategies for different failure scenarios"""

    def __init__(self):
        self.strategies: Dict[str, Callable] = {}

    def register_strategy(self, failure_type: str, strategy: Callable):
        """Register recovery strategy for specific failure type"""
        self.strategies[failure_type] = strategy

    async def recover(self, failure_type: str, context: Dict[str, Any]) -> bool:
        """Execute recovery strategy"""
        if failure_type in self.strategies:
            try:
                return await self.strategies[failure_type](context)
            except Exception as e:
                logging.error(f"Recovery strategy failed for {failure_type}: {e}")
                return False
        return False

# Global self-healing manager instance
self_healing_manager = SelfHealingManager()

def with_self_healing(agent_name: str, fallback_operation: Optional[Callable] = None):
    """
    Decorator to add self-healing capabilities to agent methods

    Args:
        agent_name: Name identifier for the agent
        fallback_operation: Optional fallback function to call on failure
    """
    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            async def operation():
                return await func(*args, **kwargs)

            async def fallback():
                if fallback_operation:
                    return await fallback_operation(*args, **kwargs)
                return None

            return await self_healing_manager.execute_with_healing(
                agent_name, operation, fallback if fallback_operation else None
            )

        return wrapper
    return decorator
