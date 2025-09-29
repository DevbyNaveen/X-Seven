"""
Circuit Breaker Implementation for Fault Tolerance
Provides circuit breaker pattern for external service dependencies
"""

import asyncio
import logging
import time
from typing import Any, Callable, Optional, Dict
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
import functools

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, requests fail fast
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5          # Failures before opening
    recovery_timeout: float = 60.0      # Seconds before attempting recovery
    expected_exception: type = Exception  # Exception type to catch
    success_threshold: int = 2          # Successes before closing
    name: str = "circuit_breaker"


class CircuitBreaker:
    """Circuit breaker for fault tolerance"""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self._lock = asyncio.Lock()
        self._metrics = {
            "total_calls": 0,
            "failed_calls": 0,
            "successful_calls": 0,
            "last_state_change": datetime.now(),
            "state_changes": 0
        }
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self._record_state_change()
                    logger.info(f"Circuit breaker {self.config.name} entering HALF_OPEN state")
                else:
                    raise Exception(f"Circuit breaker {self.config.name} is OPEN")
            
            try:
                result = await func(*args, **kwargs)
                await self._on_success()
                return result
                
            except self.config.expected_exception as e:
                await self._on_failure()
                raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery"""
        if self.last_failure_time is None:
            return True
        return (time.time() - self.last_failure_time) >= self.config.recovery_timeout
    
    async def _on_success(self):
        """Handle successful call"""
        self._metrics["total_calls"] += 1
        self._metrics["successful_calls"] += 1
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                self._record_state_change()
                logger.info(f"Circuit breaker {self.config.name} closed after successful recovery")
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0  # Reset on success
    
    async def _on_failure(self):
        """Handle failed call"""
        self._metrics["total_calls"] += 1
        self._metrics["failed_calls"] += 1
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.CLOSED and self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN
            self._record_state_change()
            logger.warning(f"Circuit breaker {self.config.name} opened due to {self.failure_count} failures")
        elif self.state == CircuitState.HALF_OPEN:
            # Failed in half-open state, go back to open
            self.state = CircuitState.OPEN
            self.success_count = 0
            self._record_state_change()
    
    def _record_state_change(self):
        """Record state change"""
        self._metrics["last_state_change"] = datetime.now()
        self._metrics["state_changes"] += 1
    
    def get_state(self) -> CircuitState:
        """Get current circuit state"""
        return self.state
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get circuit breaker metrics"""
        return {
            "name": self.config.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            **self._metrics
        }
    
    def reset(self):
        """Manually reset the circuit breaker"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self._record_state_change()
        logger.info(f"Circuit breaker {self.config.name} manually reset")


class CircuitBreakerManager:
    """Manages multiple circuit breakers"""
    
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
    
    def create_breaker(self, name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """Create and register a circuit breaker"""
        if name in self._breakers:
            return self._breakers[name]
        
        if config is None:
            config = CircuitBreakerConfig(name=name)
        
        breaker = CircuitBreaker(config)
        self._breakers[name] = breaker
        logger.info(f"Created circuit breaker: {name}")
        return breaker
    
    def get_breaker(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name"""
        return self._breakers.get(name)
    
    def get_all_breakers(self) -> Dict[str, CircuitBreaker]:
        """Get all circuit breakers"""
        return self._breakers.copy()
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall circuit breaker system health"""
        return {
            "total_breakers": len(self._breakers),
            "breakers": {
                name: breaker.get_metrics()
                for name, breaker in self._breakers.items()
            }
        }
    
    def reset_all(self):
        """Reset all circuit breakers"""
        for breaker in self._breakers.values():
            breaker.reset()


# Global circuit breaker manager
_circuit_manager: Optional[CircuitBreakerManager] = None


def get_circuit_manager() -> CircuitBreakerManager:
    """Get global circuit breaker manager"""
    global _circuit_manager
    if _circuit_manager is None:
        _circuit_manager = CircuitBreakerManager()
    return _circuit_manager


def circuit_breaker(name: str, **config_kwargs):
    """Decorator for applying circuit breaker to functions"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            manager = get_circuit_manager()
            breaker_config = CircuitBreakerConfig(name=name, **config_kwargs)
            breaker = manager.create_breaker(name, breaker_config)
            
            return await breaker.call(func, *args, **kwargs)
        
        return wrapper
    return decorator
