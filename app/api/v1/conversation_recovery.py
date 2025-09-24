"""
Conversation Recovery and Resilience Management
Handles error recovery, circuit breakers, and system resilience
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import logging

from app.api.v1.redis_persistence import RedisPersistenceManager
from app.api.v1.conversation_flow_engine import ConversationFlowEngine
from app.api.v1.crewai_langgraph_integration import CrewAILangGraphIntegrator

logger = logging.getLogger(__name__)


class RecoveryStrategy(Enum):
    """Recovery strategies for conversation failures"""
    RETRY_SAME_AGENT = "retry_same_agent"
    SWITCH_TO_FALLBACK = "switch_to_fallback"
    RESET_CONVERSATION = "reset_conversation"
    CREATE_NEW_CONVERSATION = "create_new_conversation"
    ESCALATE_TO_HUMAN = "escalate_to_human"


@dataclass
class RecoveryAttempt:
    """Record of a recovery attempt"""
    conversation_id: str
    strategy: RecoveryStrategy
    timestamp: datetime
    success: bool
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConversationRecoveryManager:
    """Manages conversation error recovery and resilience"""
    
    def __init__(self, redis_manager: RedisPersistenceManager,
                 flow_engine: ConversationFlowEngine,
                 integrator: CrewAILangGraphIntegrator):
        self.redis_manager = redis_manager
        self.flow_engine = flow_engine
        self.integrator = integrator
        
        # Recovery configuration
        self.max_retry_attempts = 3
        self.retry_delay_seconds = 2
        self.recovery_timeout_seconds = 30
        
        # Track recovery attempts
        self.recovery_history: Dict[str, List[RecoveryAttempt]] = {}
        
        logger.info("✅ Conversation Recovery Manager initialized")
    
    async def handle_conversation_error(self, conversation_id: str, error: Exception,
                                      context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle conversation error with appropriate recovery strategy"""
        try:
            logger.warning(f"Handling error in conversation {conversation_id}: {error}")
            
            # Determine recovery strategy
            strategy = await self._determine_recovery_strategy(conversation_id, error, context)
            
            # Execute recovery
            recovery_result = await self._execute_recovery_strategy(
                conversation_id, strategy, error, context
            )
            
            # Record recovery attempt
            await self._record_recovery_attempt(
                conversation_id, strategy, recovery_result["success"], 
                str(error), recovery_result.get("metadata", {})
            )
            
            return recovery_result
            
        except Exception as recovery_error:
            logger.error(f"Recovery failed for conversation {conversation_id}: {recovery_error}")
            return {
                "success": False,
                "strategy": "none",
                "error": str(recovery_error),
                "response": "I'm experiencing technical difficulties. Please try starting a new conversation."
            }
    
    async def _determine_recovery_strategy(self, conversation_id: str, error: Exception,
                                         context: Dict[str, Any]) -> RecoveryStrategy:
        """Determine the best recovery strategy based on error and context"""
        
        # Get recovery history for this conversation
        attempts = self.recovery_history.get(conversation_id, [])
        recent_attempts = [a for a in attempts if 
                          (datetime.now() - a.timestamp).seconds < 300]  # Last 5 minutes
        
        # If too many recent attempts, escalate
        if len(recent_attempts) >= self.max_retry_attempts:
            return RecoveryStrategy.CREATE_NEW_CONVERSATION
        
        # Analyze error type
        error_str = str(error).lower()
        
        if "timeout" in error_str or "connection" in error_str:
            # Network/timeout issues - retry same agent
            return RecoveryStrategy.RETRY_SAME_AGENT
        
        elif "agent" in error_str or "crewai" in error_str:
            # Agent-specific issues - switch to fallback
            return RecoveryStrategy.SWITCH_TO_FALLBACK
        
        elif "state" in error_str or "context" in error_str:
            # State corruption - reset conversation
            return RecoveryStrategy.RESET_CONVERSATION
        
        elif len(recent_attempts) == 0:
            # First attempt - try same agent
            return RecoveryStrategy.RETRY_SAME_AGENT
        
        else:
            # Multiple failures - create new conversation
            return RecoveryStrategy.CREATE_NEW_CONVERSATION
    
    async def _execute_recovery_strategy(self, conversation_id: str, strategy: RecoveryStrategy,
                                       error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the selected recovery strategy"""
        
        try:
            if strategy == RecoveryStrategy.RETRY_SAME_AGENT:
                return await self._retry_same_agent(conversation_id, context)
            
            elif strategy == RecoveryStrategy.SWITCH_TO_FALLBACK:
                return await self._switch_to_fallback_agent(conversation_id, context)
            
            elif strategy == RecoveryStrategy.RESET_CONVERSATION:
                return await self._reset_conversation(conversation_id, context)
            
            elif strategy == RecoveryStrategy.CREATE_NEW_CONVERSATION:
                return await self._create_new_conversation(conversation_id, context)
            
            elif strategy == RecoveryStrategy.ESCALATE_TO_HUMAN:
                return await self._escalate_to_human(conversation_id, context)
            
            else:
                raise ValueError(f"Unknown recovery strategy: {strategy}")
                
        except Exception as e:
            logger.error(f"Recovery strategy {strategy} failed: {e}")
            return {
                "success": False,
                "strategy": strategy.value,
                "error": str(e),
                "response": "Recovery attempt failed. Please try again."
            }
    
    async def _retry_same_agent(self, conversation_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Retry with the same agent after a brief delay"""
        logger.info(f"Retrying same agent for conversation {conversation_id}")
        
        # Brief delay before retry
        await asyncio.sleep(self.retry_delay_seconds)
        
        try:
            # Get the last user message
            state = await self.flow_engine.get_conversation_state(conversation_id)
            if not state or not state.messages:
                raise ValueError("No conversation state or messages found")
            
            user_messages = [msg for msg in state.messages if msg.get("role") == "user"]
            if not user_messages:
                raise ValueError("No user messages found")
            
            last_message = user_messages[-1]["content"]
            
            # Retry processing
            result = await self.integrator.process_message_with_agent(
                conversation_id, last_message, state.user_id
            )
            
            if "error" not in result:
                return {
                    "success": True,
                    "strategy": RecoveryStrategy.RETRY_SAME_AGENT.value,
                    "response": result.get("response", "Request processed successfully."),
                    "agent_used": result.get("agent_used"),
                    "metadata": {"retry_successful": True}
                }
            else:
                raise Exception(result["error"])
                
        except Exception as e:
            return {
                "success": False,
                "strategy": RecoveryStrategy.RETRY_SAME_AGENT.value,
                "error": str(e),
                "response": "Retry failed. Attempting alternative approach."
            }
    
    async def _switch_to_fallback_agent(self, conversation_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Switch to fallback agent"""
        logger.info(f"Switching to fallback agent for conversation {conversation_id}")
        
        try:
            # Switch to GeneralPurposeAgent
            success = await self.integrator.switch_agent(conversation_id, "GeneralPurposeAgent")
            if not success:
                raise Exception("Failed to switch agent")
            
            # Get the last user message and retry
            state = await self.flow_engine.get_conversation_state(conversation_id)
            if not state or not state.messages:
                raise ValueError("No conversation state found")
            
            user_messages = [msg for msg in state.messages if msg.get("role") == "user"]
            if not user_messages:
                raise ValueError("No user messages found")
            
            last_message = user_messages[-1]["content"]
            
            # Process with fallback agent
            result = await self.integrator.process_message_with_agent(
                conversation_id, last_message, state.user_id
            )
            
            if "error" not in result:
                return {
                    "success": True,
                    "strategy": RecoveryStrategy.SWITCH_TO_FALLBACK.value,
                    "response": result.get("response", "I've switched to a general assistant to help you."),
                    "agent_used": "GeneralPurposeAgent",
                    "metadata": {"fallback_agent_used": True}
                }
            else:
                raise Exception(result["error"])
                
        except Exception as e:
            return {
                "success": False,
                "strategy": RecoveryStrategy.SWITCH_TO_FALLBACK.value,
                "error": str(e),
                "response": "Unable to switch to fallback agent."
            }
    
    async def _reset_conversation(self, conversation_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Reset conversation state while preserving essential context"""
        logger.info(f"Resetting conversation {conversation_id}")
        
        try:
            # Get current state
            state = await self.flow_engine.get_conversation_state(conversation_id)
            if not state:
                raise ValueError("Conversation state not found")
            
            # Preserve essential context
            essential_context = {
                "user_id": state.user_id,
                "business_id": state.business_id,
                "conversation_type": state.conversation_type,
                "user_preferences": context.get("user_preferences", {}),
                "reset_at": datetime.now().isoformat(),
                "reset_reason": "error_recovery"
            }
            
            # Reset conversation with preserved context
            await self.flow_engine.update_conversation_context(
                conversation_id, essential_context
            )
            
            # Clear problematic state
            state.current_stage = "greeting"
            state.context = essential_context
            state.turn_count = 0
            
            return {
                "success": True,
                "strategy": RecoveryStrategy.RESET_CONVERSATION.value,
                "response": "I've reset our conversation. How can I help you?",
                "agent_used": "flow_engine",
                "metadata": {"conversation_reset": True}
            }
            
        except Exception as e:
            return {
                "success": False,
                "strategy": RecoveryStrategy.RESET_CONVERSATION.value,
                "error": str(e),
                "response": "Unable to reset conversation."
            }
    
    async def _create_new_conversation(self, conversation_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new conversation to replace the failed one"""
        logger.info(f"Creating new conversation to replace {conversation_id}")
        
        try:
            # Get current state for context transfer
            state = await self.flow_engine.get_conversation_state(conversation_id)
            
            # Create new conversation
            new_conversation_id = await self.integrator.create_enhanced_conversation(
                conversation_type=context.get("conversation_type", "global"),
                initial_context={
                    "transferred_from": conversation_id,
                    "transfer_reason": "error_recovery",
                    "user_preferences": context.get("user_preferences", {}),
                    "transfer_timestamp": datetime.now().isoformat()
                },
                user_id=context.get("user_id"),
                business_id=context.get("business_id")
            )
            
            # End the old conversation
            await self.flow_engine.end_conversation(conversation_id)
            
            return {
                "success": True,
                "strategy": RecoveryStrategy.CREATE_NEW_CONVERSATION.value,
                "response": "I've started a fresh conversation for you. How can I help you today?",
                "agent_used": "GeneralPurposeAgent",
                "new_conversation_id": new_conversation_id,
                "metadata": {
                    "new_conversation_created": True,
                    "old_conversation_id": conversation_id
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "strategy": RecoveryStrategy.CREATE_NEW_CONVERSATION.value,
                "error": str(e),
                "response": "Unable to create new conversation."
            }
    
    async def _escalate_to_human(self, conversation_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Escalate to human support"""
        logger.info(f"Escalating conversation {conversation_id} to human support")
        
        try:
            # Mark conversation for human review
            await self.flow_engine.update_conversation_context(
                conversation_id,
                {
                    "escalated_to_human": True,
                    "escalation_timestamp": datetime.now().isoformat(),
                    "escalation_reason": "multiple_recovery_failures"
                }
            )
            
            # Could trigger notification to support team here
            
            return {
                "success": True,
                "strategy": RecoveryStrategy.ESCALATE_TO_HUMAN.value,
                "response": "I'm having difficulty processing your request. A human support representative will be with you shortly.",
                "agent_used": "human_escalation",
                "metadata": {"escalated_to_human": True}
            }
            
        except Exception as e:
            return {
                "success": False,
                "strategy": RecoveryStrategy.ESCALATE_TO_HUMAN.value,
                "error": str(e),
                "response": "Unable to escalate to human support."
            }
    
    async def _record_recovery_attempt(self, conversation_id: str, strategy: RecoveryStrategy,
                                     success: bool, error_message: str, metadata: Dict[str, Any]):
        """Record recovery attempt for analysis"""
        attempt = RecoveryAttempt(
            conversation_id=conversation_id,
            strategy=strategy,
            timestamp=datetime.now(),
            success=success,
            error_message=error_message,
            metadata=metadata
        )
        
        if conversation_id not in self.recovery_history:
            self.recovery_history[conversation_id] = []
        
        self.recovery_history[conversation_id].append(attempt)
        
        # Also save to Redis for persistence
        await self.redis_manager.cache_set(
            f"recovery_history:{conversation_id}",
            [
                {
                    "strategy": a.strategy.value,
                    "timestamp": a.timestamp.isoformat(),
                    "success": a.success,
                    "error_message": a.error_message,
                    "metadata": a.metadata
                }
                for a in self.recovery_history[conversation_id]
            ],
            ttl=86400  # 24 hours
        )
    
    async def get_recovery_history(self, conversation_id: str) -> List[RecoveryAttempt]:
        """Get recovery history for a conversation"""
        return self.recovery_history.get(conversation_id, [])
    
    async def get_system_recovery_stats(self) -> Dict[str, Any]:
        """Get system-wide recovery statistics"""
        total_attempts = sum(len(attempts) for attempts in self.recovery_history.values())
        successful_attempts = sum(
            sum(1 for attempt in attempts if attempt.success)
            for attempts in self.recovery_history.values()
        )
        
        strategy_counts = {}
        for attempts in self.recovery_history.values():
            for attempt in attempts:
                strategy = attempt.strategy.value
                strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
        
        return {
            "total_recovery_attempts": total_attempts,
            "successful_recoveries": successful_attempts,
            "recovery_success_rate": successful_attempts / total_attempts if total_attempts > 0 else 0,
            "strategy_usage": strategy_counts,
            "conversations_with_recovery": len(self.recovery_history),
            "timestamp": datetime.now().isoformat()
        }


class ConversationResilienceManager:
    """Manages system resilience and circuit breaker patterns"""
    
    def __init__(self, recovery_manager: ConversationRecoveryManager):
        self.recovery_manager = recovery_manager
        
        # Circuit breaker state
        self.circuit_breaker_open = False
        self.circuit_breaker_opened_at: Optional[datetime] = None
        self.circuit_breaker_timeout = 300  # 5 minutes
        
        # System health tracking
        self.error_count = 0
        self.error_threshold = 10
        self.error_window_seconds = 60
        self.error_timestamps: List[datetime] = []
        
        # Load tracking
        self.current_load = 0
        self.max_load = 1000
        
        logger.info("✅ Conversation Resilience Manager initialized")
    
    async def check_system_health(self) -> Dict[str, Any]:
        """Check overall system health"""
        now = datetime.now()
        
        # Clean old error timestamps
        self.error_timestamps = [
            ts for ts in self.error_timestamps 
            if (now - ts).seconds < self.error_window_seconds
        ]
        
        # Check circuit breaker status
        circuit_status = "closed"
        if self.circuit_breaker_open:
            if self.circuit_breaker_opened_at and \
               (now - self.circuit_breaker_opened_at).seconds > self.circuit_breaker_timeout:
                # Try to close circuit breaker
                await self.handle_circuit_breaker_recovery()
                circuit_status = "half_open"
            else:
                circuit_status = "open"
        
        # Determine overall status
        error_rate = len(self.error_timestamps) / self.error_window_seconds
        load_percentage = (self.current_load / self.max_load) * 100
        
        if circuit_status == "open":
            status = "circuit_breaker"
        elif error_rate > 0.1:  # More than 0.1 errors per second
            status = "degraded"
        elif load_percentage > 90:
            status = "overloaded"
        else:
            status = "healthy"
        
        # Check Redis health
        redis_health = await self.recovery_manager.redis_manager.health_check()
        
        return {
            "status": status,
            "last_check": now,
            "redis_health": redis_health,
            "engine_status": "operational",
            "issues": self._get_current_issues(),
            "load": self.current_load,
            "max_load": self.max_load,
            "error_rate": error_rate,
            "circuit_breaker": circuit_status
        }
    
    async def record_error(self, error: Exception):
        """Record system error for health tracking"""
        self.error_timestamps.append(datetime.now())
        
        # Check if we should open circuit breaker
        if len(self.error_timestamps) >= self.error_threshold:
            await self._open_circuit_breaker()
    
    async def _open_circuit_breaker(self):
        """Open circuit breaker to prevent cascade failures"""
        if not self.circuit_breaker_open:
            self.circuit_breaker_open = True
            self.circuit_breaker_opened_at = datetime.now()
            logger.warning("🚨 Circuit breaker opened due to high error rate")
    
    async def handle_circuit_breaker_recovery(self):
        """Attempt to recover from circuit breaker state"""
        if self.circuit_breaker_open:
            # Test system health
            health = await self.check_system_health()
            
            if health["redis_health"]["status"] == "healthy" and len(self.error_timestamps) < 3:
                self.circuit_breaker_open = False
                self.circuit_breaker_opened_at = None
                logger.info("✅ Circuit breaker closed - system recovered")
    
    async def update_conversation_load(self, current_conversations: int):
        """Update current conversation load"""
        self.current_load = current_conversations
    
    def _get_current_issues(self) -> List[str]:
        """Get list of current system issues"""
        issues = []
        
        if self.circuit_breaker_open:
            issues.append("Circuit breaker is open")
        
        if len(self.error_timestamps) > 5:
            issues.append("High error rate detected")
        
        if self.current_load > self.max_load * 0.9:
            issues.append("System approaching capacity")
        
        return issues
    
    async def get_resilience_metrics(self) -> Dict[str, Any]:
        """Get resilience metrics"""
        return {
            "circuit_breaker_open": self.circuit_breaker_open,
            "circuit_breaker_opened_at": self.circuit_breaker_opened_at.isoformat() if self.circuit_breaker_opened_at else None,
            "recent_errors": len(self.error_timestamps),
            "error_threshold": self.error_threshold,
            "current_load": self.current_load,
            "max_load": self.max_load,
            "load_percentage": (self.current_load / self.max_load) * 100,
            "timestamp": datetime.now().isoformat()
        }
