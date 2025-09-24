"""
LangGraph Conversation API
Provides REST API endpoints for LangGraph conversation management
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from dataclasses import dataclass

from .conversation_flow_engine import ConversationFlowEngine, ConversationConfig
from .redis_persistence import RedisPersistenceManager
from .crewai_langgraph_integration import CrewAILangGraphIntegrator
from .conversation_recovery import ConversationRecoveryManager, ConversationResilienceManager
from .chat_flow_router import get_chat_flow_router, ChatFlowType
from ..workflows.temporal_integration import get_temporal_manager

# Import Kafka integration
from app.core.kafka.integration import (
    get_kafka_service_integrator,
    publish_conversation_started,
    publish_conversation_message,
    publish_ai_response_generated
)

# Import DSPy integration
from app.core.dspy.enhanced_conversation_engine import DSPyEnhancedConversationEngine
from app.core.ai.dspy_enhanced_handler import DSPyEnhancedAIHandler
from app.core.dspy.config import initialize_dspy

# Initialize components
conversation_config = ConversationConfig(
    max_turns=50,
    timeout_seconds=300,
    enable_persistence=True,
    enable_recovery=True,
    fallback_agent="GeneralPurposeAgent"
)

redis_manager = RedisPersistenceManager()
conversation_engine = ConversationFlowEngine(conversation_config)
integrator = CrewAILangGraphIntegrator()
recovery_manager = ConversationRecoveryManager(redis_manager, conversation_engine, integrator)
resilience_manager = ConversationResilienceManager(recovery_manager)
chat_flow_router = get_chat_flow_router()
temporal_manager = get_temporal_manager()

# Initialize DSPy components
initialize_dspy()
dspy_conversation_engine = DSPyEnhancedConversationEngine(conversation_config)
dspy_ai_handler = DSPyEnhancedAIHandler()

# FastAPI router
router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


# Pydantic models for request/response
class ConversationCreateRequest(BaseModel):
    """Request model for creating a conversation"""
    conversation_type: str = Field(default="general", description="Type of conversation")
    initial_context: Dict[str, Any] = Field(default_factory=dict, description="Initial context")
    user_id: Optional[str] = Field(None, description="User ID")


class ConversationMessageRequest(BaseModel):
    """Request model for sending a message"""
    message: str = Field(..., description="User message")
    user_id: Optional[str] = Field(None, description="User ID")
    use_dspy: bool = Field(default=True, description="Use DSPy-enhanced processing")


class ConversationResponse(BaseModel):
    """Response model for conversation operations"""
    conversation_id: str
    response: str
    agent_used: str
    turn_count: int
    status: str
    context: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    dspy_metadata: Optional[Dict[str, Any]] = Field(default=None, description="DSPy processing metadata")


class ConversationHistoryResponse(BaseModel):
    """Response model for conversation history"""
    conversation_id: str
    messages: List[Dict[str, Any]]
    agent_history: List[str]
    created_at: datetime
    updated_at: datetime


class AgentInfoResponse(BaseModel):
    """Response model for agent information"""
    name: str
    description: str
    capabilities: List[str]


class RecoveryInfoResponse(BaseModel):
    """Response model for recovery information"""
    success: bool
    strategy: str
    message: str
    new_conversation_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SystemHealthResponse(BaseModel):
    """Response model for system health"""
    status: str
    last_check: datetime
    redis_health: Dict[str, Any]
    engine_status: str
    issues: List[str]
    load: int
    max_load: int


# API Endpoints

@router.post("/create", response_model=ConversationResponse)
async def create_conversation(request: ConversationCreateRequest):
    """Create a new conversation with enhanced routing"""

    try:
        # Check system health before creating conversation
        health = await resilience_manager.check_system_health()
        if health["status"] == "circuit_breaker":
            raise HTTPException(status_code=503, detail="System temporarily unavailable")

        # Update conversation load
        await resilience_manager.update_conversation_load(
            len(await redis_manager.get_conversation_list())
        )

        # Determine conversation type and route appropriately
        chat_request = {
            "flow_type": request.conversation_type,
            "initial_context": request.initial_context,
            "user_id": request.user_id,
            "message": "Hello! I'm ready to start our conversation."
        }
        
        # Route through chat flow router for enhanced handling
        response = await chat_flow_router.route_chat_request(chat_request)
        
        # Create conversation using integrator with enhanced context
        conversation_id = await integrator.create_enhanced_conversation(
            conversation_type=request.conversation_type,
            initial_context=request.initial_context,
            user_id=request.user_id
        )

        # Get enhanced context
        context = await integrator.get_conversation_context(conversation_id)

        # Publish conversation started event to Kafka
        try:
            await publish_conversation_started(
                conversation_id=conversation_id,
                user_id=request.user_id or "anonymous",
                metadata={
                    "conversation_type": request.conversation_type,
                    "initial_context": request.initial_context,
                    "agent_used": response.get("agent_used", "GeneralPurposeAgent"),
                    "flow_type": response.get("flow_type")
                }
            )
        except Exception as kafka_error:
            # Log but don't fail the request if Kafka is unavailable
            logger.warning(f"Failed to publish conversation started event: {kafka_error}")

        return ConversationResponse(
            conversation_id=conversation_id,
            response=response.get("response", "Hello! I'm ready to assist you. What can I help you with?"),
            agent_used=response.get("agent_used", "GeneralPurposeAgent"),
            turn_count=0,
            status="active",
            context=context or {},
            metadata={
                "created": True, 
                "type": request.conversation_type,
                "flow_type": response.get("flow_type"),
                "routing_metadata": response.get("routing_metadata", {})
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create conversation: {str(e)}")


@router.post("/{conversation_id}/message", response_model=ConversationResponse)
async def send_message(conversation_id: str, request: ConversationMessageRequest):
    """Send a message in an existing conversation with enhanced routing"""

    try:
        # Check if conversation exists
        existing_context = await integrator.get_conversation_context(conversation_id)
        if not existing_context:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Prepare enhanced chat request
        chat_request = {
            "conversation_id": conversation_id,
            "message": request.message,
            "user_id": request.user_id,
            "flow_type": existing_context.get("conversation_type", "global"),
            "business_id": existing_context.get("business_id"),
            "user_role": existing_context.get("user_role"),
            "context": existing_context
        }
        
        # Route through chat flow router for enhanced processing
        try:
            result = await chat_flow_router.route_chat_request(chat_request)
        except Exception as router_error:
            # Fallback to direct integration if router fails
            logger.warning(f"Chat router failed, using direct integration: {router_error}")
            result = await integrator.process_message_with_agent(
                conversation_id, request.message, request.user_id
            )

        if "error" in result:
            # Handle error with recovery
            recovery_result = await recovery_manager.handle_conversation_error(
                conversation_id, Exception(result["error"]), existing_context
            )

            if recovery_result["success"]:
                return ConversationResponse(
                    conversation_id=recovery_result.get("new_conversation_id", conversation_id),
                    response=recovery_result["response"],
                    agent_used=recovery_result.get("agent_used", "GeneralPurposeAgent"),
                    turn_count=existing_context.get("turn_count", 0) + 1,
                    status="recovered",
                    context=existing_context,
                    metadata={"recovery": True, "strategy": recovery_result.get("strategy")}
                )
            else:
                raise HTTPException(status_code=500, detail=recovery_result["error"])

        # Publish conversation message and AI response events to Kafka
        try:
            # Publish user message event
            await publish_conversation_message(
                conversation_id=conversation_id,
                user_id=request.user_id or "anonymous",
                message_content=request.message,
                message_type="user",
                metadata={
                    "flow_type": existing_context.get("conversation_type", "global"),
                    "business_id": existing_context.get("business_id"),
                    "user_role": existing_context.get("user_role")
                }
            )
            
            # Publish AI response event
            await publish_ai_response_generated(
                model_name=result.get("agent_used", "unknown"),
                response_data={
                    "prompt": request.message,
                    "response": result.get("response", ""),
                    "tokens_used": result.get("tokens_used"),
                    "response_time_ms": result.get("response_time_ms"),
                    "cost_usd": result.get("cost_usd"),
                    "flow_type": result.get("flow_type"),
                    "chat_type": result.get("chat_type")
                },
                user_id=request.user_id or "anonymous",
                conversation_id=conversation_id
            )
        except Exception as kafka_error:
            # Log but don't fail the request if Kafka is unavailable
            logger.warning(f"Failed to publish conversation events: {kafka_error}")

        # Enhanced response with additional metadata
        response_data = {
            "conversation_id": result.get("conversation_id", conversation_id),
            "response": result.get("response", ""),
            "agent_used": result.get("agent_used", "unknown"),
            "turn_count": result.get("turn_count", 0),
            "status": result.get("status", "processed"),
            "context": result.get("context", {}),
            "metadata": {
                **result.get("metadata", {}),
                "flow_type": result.get("flow_type"),
                "chat_type": result.get("chat_type"),
                "routing_metadata": result.get("routing_metadata", {}),
                "workflow_triggered": result.get("context", {}).get("workflow_triggered", False)
            }
        }
        
        return ConversationResponse(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process message: {str(e)}")


@router.post("/{conversation_id}/message/dspy", response_model=ConversationResponse)
async def send_message_dspy_enhanced(conversation_id: str, request: ConversationMessageRequest):
    """Send a message using DSPy-enhanced processing"""
    
    try:
        # Check if conversation exists
        existing_context = await integrator.get_conversation_context(conversation_id)
        if not existing_context:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Use DSPy-enhanced processing
        from app.core.ai.types import ChatContext
        chat_context_map = {
            "dedicated": ChatContext.DEDICATED,
            "dashboard": ChatContext.DASHBOARD,
            "global": ChatContext.GLOBAL
        }
        
        conversation_type = existing_context.get("conversation_type", "dedicated")
        chat_context = chat_context_map.get(conversation_type, ChatContext.DEDICATED)
        
        # Process with DSPy
        dspy_result = await dspy_ai_handler.process_message_with_dspy(
            message=request.message,
            session_id=conversation_id,
            business_id=existing_context.get("business_id"),
            user_id=request.user_id,
            chat_context=chat_context,
            additional_context=existing_context
        )
        
        # Publish events to Kafka
        try:
            await publish_conversation_message(
                conversation_id=conversation_id,
                user_id=request.user_id or "anonymous",
                message_content=request.message,
                message_type="user",
                metadata={
                    "dspy_enhanced": True,
                    "flow_type": conversation_type,
                    "business_id": existing_context.get("business_id")
                }
            )
            
            await publish_ai_response_generated(
                model_name="dspy_enhanced",
                response_data={
                    "prompt": request.message,
                    "response": dspy_result.get("message", ""),
                    "confidence": dspy_result.get("dspy_metadata", {}).get("response_confidence", 0.0),
                    "intent": dspy_result.get("dspy_metadata", {}).get("intent", {}).get("intent", "unknown"),
                    "dspy_optimized": True
                },
                user_id=request.user_id or "anonymous",
                conversation_id=conversation_id
            )
        except Exception as kafka_error:
            logger.warning(f"Failed to publish DSPy conversation events: {kafka_error}")
        
        # Format response
        return ConversationResponse(
            conversation_id=conversation_id,
            response=dspy_result.get("message", ""),
            agent_used="DSPy-Enhanced",
            turn_count=existing_context.get("turn_count", 0) + 1,
            status="processed",
            context=existing_context,
            metadata={
                "dspy_enhanced": True,
                "processing_method": "dspy_optimized"
            },
            dspy_metadata=dspy_result.get("dspy_metadata", {})
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DSPy-enhanced message processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"DSPy processing failed: {str(e)}")


@router.get("/{conversation_id}/history", response_model=ConversationHistoryResponse)
async def get_conversation_history(conversation_id: str):
    """Get conversation history"""

    try:
        context = await integrator.get_conversation_context(conversation_id)
        if not context:
            raise HTTPException(status_code=404, detail="Conversation not found")

        history = await conversation_engine.get_conversation_history(conversation_id)

        return ConversationHistoryResponse(
            conversation_id=conversation_id,
            messages=history,
            agent_history=context.get("agent_history", []),
            created_at=context.get("created_at", datetime.now()),
            updated_at=context.get("updated_at", datetime.now())
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")


@router.post("/{conversation_id}/switch-agent")
async def switch_agent(conversation_id: str, agent_name: str):
    """Switch to a different agent in the conversation"""

    try:
        success = await integrator.switch_agent(conversation_id, agent_name)
        if not success:
            raise HTTPException(status_code=400, detail="Invalid agent or conversation")

        context = await integrator.get_conversation_context(conversation_id)

        return {
            "success": True,
            "conversation_id": conversation_id,
            "new_agent": agent_name,
            "context": context
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to switch agent: {str(e)}")


@router.get("/agents", response_model=List[AgentInfoResponse])
async def get_available_agents():
    """Get information about available agents"""

    try:
        agents = await integrator.get_available_agents()
        return [AgentInfoResponse(**agent) for agent in agents]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get agents: {str(e)}")


@router.post("/{conversation_id}/end")
async def end_conversation(conversation_id: str):
    """End a conversation"""

    try:
        success = await conversation_engine.end_conversation(conversation_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to end conversation")

        return {
            "success": True,
            "conversation_id": conversation_id,
            "message": "Conversation ended successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to end conversation: {str(e)}")


@router.post("/{conversation_id}/recover")
async def recover_conversation(conversation_id: str):
    """Manually trigger conversation recovery"""

    try:
        # Get current context
        context = await integrator.get_conversation_context(conversation_id)
        if not context:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Trigger recovery
        recovery_result = await recovery_manager.handle_conversation_error(
            conversation_id, Exception("Manual recovery requested"), context
        )

        return RecoveryInfoResponse(**recovery_result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recovery failed: {str(e)}")


@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health():
    """Get system health status"""

    try:
        health = await resilience_manager.check_system_health()
        return SystemHealthResponse(**health)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/stats")
async def get_conversation_stats():
    """Get enhanced conversation system statistics"""

    try:
        # Get Redis stats
        redis_stats = await redis_manager.get_conversation_stats()

        # Get recovery stats
        recovery_stats = await recovery_manager.get_system_recovery_stats()

        # Get resilience metrics
        resilience_metrics = await resilience_manager.get_resilience_metrics()
        
        # Get Temporal workflow metrics
        temporal_metrics = await temporal_manager.get_workflow_metrics()
        
        # Get chat flow statistics
        chat_flow_stats = {
            "available_flow_types": ["dedicated", "dashboard", "global"],
            "active_handlers": 3,
            "routing_enabled": True
        }

        # Get DSPy stats
        dspy_stats = dspy_ai_handler.get_performance_metrics()
        dspy_status = dspy_conversation_engine.get_optimization_status()
        
        return {
            "redis_stats": redis_stats,
            "recovery_stats": recovery_stats,
            "resilience_metrics": resilience_metrics,
            "temporal_metrics": temporal_metrics,
            "chat_flow_stats": chat_flow_stats,
            "dspy_stats": dspy_stats,
            "dspy_optimization_status": dspy_status,
            "system_status": "dspy_enhanced_integration_active",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.get("/recovery-history/{conversation_id}")
async def get_recovery_history(conversation_id: str):
    """Get recovery history for a conversation"""

    try:
        history = await recovery_manager.get_recovery_history(conversation_id)
        return {
            "conversation_id": conversation_id,
            "recovery_attempts": [
                {
                    "strategy": attempt.strategy.value,
                    "timestamp": attempt.timestamp.isoformat(),
                    "success": attempt.success,
                    "error_message": attempt.error_message,
                    "metadata": attempt.metadata
                }
                for attempt in history
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get recovery history: {str(e)}")


# Background task for health monitoring
async def health_monitoring_task():
    """Enhanced background task for monitoring system health"""
    while True:
        try:
            # Check system resilience
            await resilience_manager.check_system_health()
            await resilience_manager.handle_circuit_breaker_recovery()
            
            # Clean up expired Redis keys
            await redis_manager.cleanup_expired_keys()
            
            # Clean up completed workflows
            await temporal_manager.cleanup_completed_workflows()
            
            await asyncio.sleep(30)  # Check every 30 seconds
        except Exception as e:
            logger.error(f"Health monitoring error: {e}")
            await asyncio.sleep(60)  # Wait longer on error


# Enhanced chat flow endpoints

@router.post("/chat/dedicated")
async def dedicated_chat(request: Dict[str, Any]):
    """Direct endpoint for dedicated business chat"""
    request["flow_type"] = "dedicated"
    return await chat_flow_router.route_chat_request(request)

@router.post("/chat/dashboard")
async def dashboard_chat(request: Dict[str, Any]):
    """Direct endpoint for dashboard management chat"""
    request["flow_type"] = "dashboard"
    return await chat_flow_router.route_chat_request(request)

@router.post("/chat/global")
async def global_chat(request: Dict[str, Any]):
    """Direct endpoint for global assessment chat"""
    request["flow_type"] = "global"
    return await chat_flow_router.route_chat_request(request)

@router.get("/workflows/active")
async def get_active_workflows():
    """Get active Temporal workflows"""
    try:
        workflows = await temporal_manager.get_active_workflows()
        return {
            "active_workflows": workflows,
            "count": len(workflows),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get workflows: {str(e)}")

@router.post("/workflows/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: str, reason: str = "User requested"):
    """Cancel a running workflow"""
    try:
        success = await temporal_manager.cancel_workflow(workflow_id, reason)
        return {
            "success": success,
            "workflow_id": workflow_id,
            "reason": reason,
            "cancelled_at": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel workflow: {str(e)}")


# DSPy Integration Endpoints

@router.post("/dspy/optimize")
async def optimize_dspy_system(background_tasks: BackgroundTasks, force: bool = False):
    """Trigger DSPy system optimization"""
    try:
        # Check if optimization is already in progress
        status = dspy_conversation_engine.get_optimization_status()
        if status["optimization_in_progress"]:
            raise HTTPException(status_code=409, detail="Optimization already in progress")
        
        # Start optimization in background
        background_tasks.add_task(_run_dspy_optimization, force)
        
        return {
            "success": True,
            "message": "DSPy optimization started in background",
            "estimated_duration": "10-20 minutes",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start optimization: {str(e)}")


async def _run_dspy_optimization(force: bool = False):
    """Background task for DSPy optimization"""
    try:
        logger.info("🚀 Starting DSPy system optimization...")
        result = await dspy_conversation_engine.optimize_modules(force_optimization=force)
        
        if result.get("success"):
            logger.info("✅ DSPy optimization completed successfully")
        else:
            logger.error(f"❌ DSPy optimization failed: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"❌ DSPy optimization background task failed: {e}")


@router.get("/dspy/status")
async def get_dspy_system_status():
    """Get DSPy system status and metrics"""
    try:
        handler_status = dspy_ai_handler.get_dspy_status()
        engine_status = dspy_conversation_engine.get_optimization_status()
        performance_metrics = dspy_ai_handler.get_performance_metrics()
        
        return {
            "handler_status": handler_status,
            "engine_status": engine_status,
            "performance_metrics": performance_metrics,
            "system_ready": handler_status.get("dspy_initialized", False),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get DSPy status: {str(e)}")


@router.post("/dspy/test")
async def test_dspy_modules(test_message: str = "Hello, I'd like to make a reservation"):
    """Test DSPy modules with a sample message"""
    try:
        # Test intent detection
        intent_result = dspy_conversation_engine.intent_module.forward(
            message=test_message,
            conversation_history="",
            business_context="Restaurant business"
        )
        
        # Test agent routing
        routing_result = dspy_conversation_engine.routing_module.forward(
            intent=intent_result.intent,
            business_context="Restaurant business",
            conversation_type="dedicated",
            user_message=test_message,
            available_agents=["RestaurantAgent", "GeneralPurposeAgent"]
        )
        
        # Test response generation
        response_result = dspy_conversation_engine.response_module.forward(
            user_message=test_message,
            conversation_history="",
            business_context="Restaurant business",
            agent_context="Restaurant specialist",
            intent=intent_result.intent
        )
        
        return {
            "test_message": test_message,
            "intent_detection": {
                "intent": intent_result.intent,
                "confidence": intent_result.confidence,
                "reasoning": intent_result.reasoning
            },
            "agent_routing": {
                "selected_agent": routing_result.selected_agent,
                "confidence": routing_result.confidence,
                "reasoning": routing_result.routing_reason
            },
            "response_generation": {
                "response": response_result.response,
                "confidence": response_result.confidence,
                "action_items": response_result.action_items
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DSPy module test failed: {str(e)}")


# Start background monitoring
@router.on_event("startup")
async def startup_event():
    """Start background tasks on startup"""
    # Initialize Temporal manager
    try:
        await temporal_manager.initialize()
        logger.info("✅ Temporal manager initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Temporal: {e}")
    
    # Start health monitoring
    asyncio.create_task(health_monitoring_task())
    logger.info("✅ Enhanced conversation API startup completed")
