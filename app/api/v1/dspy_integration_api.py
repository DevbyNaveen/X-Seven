"""
DSPy Integration API
REST endpoints for DSPy optimization and management
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field

from app.core.dspy.config import get_dspy_manager, initialize_dspy
from app.core.dspy.enhanced_conversation_engine import DSPyEnhancedConversationEngine
from app.core.dspy.optimizers import DSPyOptimizer, OptimizationConfig
from app.core.dspy.training_data import TrainingDataManager
from app.core.ai.dspy_enhanced_handler import DSPyEnhancedAIHandler

logger = logging.getLogger(__name__)

# Initialize components
dspy_manager = get_dspy_manager()
conversation_engine = DSPyEnhancedConversationEngine()
training_manager = TrainingDataManager()
ai_handler = DSPyEnhancedAIHandler()

# FastAPI router
router = APIRouter(prefix="/api/v1/dspy", tags=["dspy"])


# Pydantic models
class DSPyMessageRequest(BaseModel):
    """Request model for DSPy-enhanced message processing"""
    message: str = Field(..., description="User message")
    session_id: str = Field(..., description="Session ID")
    business_id: Optional[int] = Field(None, description="Business ID")
    user_id: Optional[str] = Field(None, description="User ID")
    chat_context: str = Field(default="dedicated", description="Chat context type")
    additional_context: Optional[Dict[str, Any]] = Field(default_factory=dict)


class DSPyOptimizationRequest(BaseModel):
    """Request model for DSPy optimization"""
    modules: List[str] = Field(default=["intent_detection", "agent_routing", "response_generation"])
    force_optimization: bool = Field(default=False, description="Force re-optimization")
    max_examples: int = Field(default=100, description="Maximum training examples")
    optimization_budget: float = Field(default=10.0, description="Budget in USD")


class TrainingDataRequest(BaseModel):
    """Request model for adding training data"""
    data_type: str = Field(..., description="Type of training data")
    examples: List[Dict[str, Any]] = Field(..., description="Training examples")


class DSPyResponse(BaseModel):
    """Response model for DSPy operations"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# API Endpoints

@router.post("/chat", response_model=Dict[str, Any])
async def dspy_enhanced_chat(request: DSPyMessageRequest):
    """Process message using DSPy-enhanced pipeline"""
    try:
        # Map chat context string to enum
        from app.core.ai.types import ChatContext
        chat_context_map = {
            "dedicated": ChatContext.DEDICATED,
            "dashboard": ChatContext.DASHBOARD,
            "global": ChatContext.GLOBAL
        }
        chat_context = chat_context_map.get(request.chat_context, ChatContext.DEDICATED)
        
        # Process message
        result = await ai_handler.process_message_with_dspy(
            message=request.message,
            session_id=request.session_id,
            business_id=request.business_id,
            user_id=request.user_id,
            chat_context=chat_context,
            additional_context=request.additional_context
        )
        
        return result
        
    except Exception as e:
        logger.error(f"DSPy chat processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"DSPy chat processing failed: {str(e)}")


@router.post("/optimize", response_model=DSPyResponse)
async def optimize_dspy_modules(request: DSPyOptimizationRequest, background_tasks: BackgroundTasks):
    """Trigger DSPy module optimization"""
    try:
        # Check if optimization is already in progress
        status = conversation_engine.get_optimization_status()
        if status["optimization_in_progress"]:
            raise HTTPException(status_code=409, detail="Optimization already in progress")
        
        # Start optimization in background
        background_tasks.add_task(
            _run_optimization,
            request.modules,
            request.force_optimization,
            request.max_examples,
            request.optimization_budget
        )
        
        return DSPyResponse(
            success=True,
            message="DSPy optimization started in background",
            data={
                "modules": request.modules,
                "estimated_duration": "10-20 minutes",
                "budget": request.optimization_budget
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start DSPy optimization: {e}")
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")


async def _run_optimization(modules: List[str], force: bool, max_examples: int, budget: float):
    """Background task for running optimization"""
    try:
        logger.info(f"🚀 Starting DSPy optimization for modules: {modules}")
        
        # Update optimization config
        opt_config = OptimizationConfig(
            max_training_examples=max_examples,
            optimization_budget=budget
        )
        
        optimizer = DSPyOptimizer(opt_config)
        
        # Get modules to optimize
        modules_to_optimize = {}
        if "intent_detection" in modules:
            modules_to_optimize["intent_detection"] = conversation_engine.intent_module
        if "agent_routing" in modules:
            modules_to_optimize["agent_routing"] = conversation_engine.routing_module
        if "response_generation" in modules:
            modules_to_optimize["response_generation"] = conversation_engine.response_module
        
        # Run optimization
        result = await optimizer.optimize_full_pipeline(modules_to_optimize)
        
        # Update conversation engine modules
        if "intent_detection" in result:
            conversation_engine.intent_module = result["intent_detection"]
        if "agent_routing" in result:
            conversation_engine.routing_module = result["agent_routing"]
        if "response_generation" in result:
            conversation_engine.response_module = result["response_generation"]
        
        conversation_engine.modules_optimized = True
        
        logger.info("✅ DSPy optimization completed successfully")
        
    except Exception as e:
        logger.error(f"❌ DSPy optimization failed: {e}")


@router.get("/status", response_model=Dict[str, Any])
async def get_dspy_status():
    """Get DSPy system status"""
    try:
        # Get comprehensive status
        dspy_status = ai_handler.get_dspy_status()
        optimization_status = conversation_engine.get_optimization_status()
        training_stats = training_manager.get_training_stats()
        
        return {
            "dspy_system": dspy_status,
            "optimization": optimization_status,
            "training_data": training_stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get DSPy status: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


@router.get("/metrics", response_model=Dict[str, Any])
async def get_dspy_metrics():
    """Get DSPy performance metrics"""
    try:
        performance_metrics = ai_handler.get_performance_metrics()
        optimization_stats = conversation_engine.optimizer.get_optimization_stats() if conversation_engine.optimizer else {}
        
        return {
            "performance": performance_metrics,
            "optimization_history": optimization_stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get DSPy metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Metrics retrieval failed: {str(e)}")


@router.post("/training-data", response_model=DSPyResponse)
async def add_training_data(request: TrainingDataRequest):
    """Add training data for DSPy optimization"""
    try:
        valid_types = ["intent_detection", "agent_routing", "response_generation"]
        if request.data_type not in valid_types:
            raise HTTPException(status_code=400, detail=f"Invalid data type. Must be one of: {valid_types}")
        
        # Add training examples
        for example in request.examples:
            training_manager.add_training_example(request.data_type, example)
        
        return DSPyResponse(
            success=True,
            message=f"Added {len(request.examples)} training examples for {request.data_type}",
            data={
                "data_type": request.data_type,
                "examples_added": len(request.examples)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add training data: {e}")
        raise HTTPException(status_code=500, detail=f"Training data addition failed: {str(e)}")


@router.get("/training-data/{data_type}", response_model=Dict[str, Any])
async def get_training_data(data_type: str, limit: int = 50):
    """Get training data for a specific type"""
    try:
        valid_types = ["intent_detection", "agent_routing", "response_generation"]
        if data_type not in valid_types:
            raise HTTPException(status_code=400, detail=f"Invalid data type. Must be one of: {valid_types}")
        
        # Get training data
        if data_type == "intent_detection":
            data = await training_manager.get_intent_training_data(limit)
        elif data_type == "agent_routing":
            data = await training_manager.get_routing_training_data(limit)
        elif data_type == "response_generation":
            data = await training_manager.get_response_training_data(limit)
        
        return {
            "data_type": data_type,
            "examples": data[:limit],
            "total_count": len(data),
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get training data: {e}")
        raise HTTPException(status_code=500, detail=f"Training data retrieval failed: {str(e)}")


@router.post("/generate-training-data", response_model=DSPyResponse)
async def generate_synthetic_training_data(data_type: str, num_examples: int = 50):
    """Generate synthetic training data"""
    try:
        valid_types = ["intent_detection", "agent_routing", "response_generation"]
        if data_type not in valid_types:
            raise HTTPException(status_code=400, detail=f"Invalid data type. Must be one of: {valid_types}")
        
        if num_examples > 200:
            raise HTTPException(status_code=400, detail="Maximum 200 examples allowed")
        
        # Generate synthetic data
        if data_type == "intent_detection":
            data = await training_manager.get_intent_training_data(num_examples)
        elif data_type == "agent_routing":
            data = await training_manager.get_routing_training_data(num_examples)
        elif data_type == "response_generation":
            data = await training_manager.get_response_training_data(num_examples)
        
        return DSPyResponse(
            success=True,
            message=f"Generated {len(data)} synthetic training examples for {data_type}",
            data={
                "data_type": data_type,
                "examples_generated": len(data)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate training data: {e}")
        raise HTTPException(status_code=500, detail=f"Training data generation failed: {str(e)}")


@router.post("/test-module", response_model=Dict[str, Any])
async def test_dspy_module(module_name: str, test_input: Dict[str, Any]):
    """Test a specific DSPy module"""
    try:
        valid_modules = ["intent_detection", "agent_routing", "response_generation"]
        if module_name not in valid_modules:
            raise HTTPException(status_code=400, detail=f"Invalid module. Must be one of: {valid_modules}")
        
        # Test the module
        if module_name == "intent_detection":
            result = conversation_engine.intent_module.forward(
                message=test_input.get("message", ""),
                conversation_history=test_input.get("conversation_history", ""),
                business_context=test_input.get("business_context", "")
            )
            
            return {
                "module": module_name,
                "input": test_input,
                "output": {
                    "intent": result.intent,
                    "confidence": result.confidence,
                    "reasoning": result.reasoning,
                    "requires_booking": result.requires_booking,
                    "business_category": result.business_category
                },
                "timestamp": datetime.now().isoformat()
            }
        
        elif module_name == "agent_routing":
            result = conversation_engine.routing_module.forward(
                intent=test_input.get("intent", "general"),
                business_context=test_input.get("business_context", ""),
                conversation_type=test_input.get("conversation_type", "general"),
                user_message=test_input.get("user_message", ""),
                available_agents=test_input.get("available_agents", [])
            )
            
            return {
                "module": module_name,
                "input": test_input,
                "output": {
                    "selected_agent": result.selected_agent,
                    "routing_reason": result.routing_reason,
                    "confidence": result.confidence,
                    "fallback_agent": result.fallback_agent
                },
                "timestamp": datetime.now().isoformat()
            }
        
        elif module_name == "response_generation":
            result = conversation_engine.response_module.forward(
                user_message=test_input.get("user_message", ""),
                conversation_history=test_input.get("conversation_history", ""),
                business_context=test_input.get("business_context", ""),
                agent_context=test_input.get("agent_context", ""),
                intent=test_input.get("intent", "general")
            )
            
            return {
                "module": module_name,
                "input": test_input,
                "output": {
                    "response": result.response,
                    "action_items": result.action_items,
                    "confidence": result.confidence,
                    "requires_human": result.requires_human
                },
                "timestamp": datetime.now().isoformat()
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Module test failed: {e}")
        raise HTTPException(status_code=500, detail=f"Module test failed: {str(e)}")


@router.post("/reset-optimization", response_model=DSPyResponse)
async def reset_optimization():
    """Reset DSPy optimization state"""
    try:
        # Reset optimization state
        conversation_engine.modules_optimized = False
        conversation_engine.optimization_in_progress = False
        
        # Clear optimization history
        if conversation_engine.optimizer:
            conversation_engine.optimizer.optimization_history = []
        
        return DSPyResponse(
            success=True,
            message="DSPy optimization state reset successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to reset optimization: {e}")
        raise HTTPException(status_code=500, detail=f"Reset failed: {str(e)}")


@router.get("/health", response_model=Dict[str, Any])
async def dspy_health_check():
    """DSPy system health check"""
    try:
        health_status = {
            "dspy_manager_initialized": dspy_manager._initialized,
            "conversation_engine_ready": conversation_engine is not None,
            "training_manager_ready": training_manager is not None,
            "ai_handler_ready": ai_handler is not None,
            "modules_status": {
                "intent_detection": conversation_engine.intent_module is not None,
                "agent_routing": conversation_engine.routing_module is not None,
                "response_generation": conversation_engine.response_module is not None
            },
            "optimization_available": conversation_engine.optimizer is not None,
            "timestamp": datetime.now().isoformat()
        }
        
        # Overall health
        all_ready = all([
            health_status["dspy_manager_initialized"],
            health_status["conversation_engine_ready"],
            health_status["training_manager_ready"],
            health_status["ai_handler_ready"],
            all(health_status["modules_status"].values())
        ])
        
        health_status["overall_status"] = "healthy" if all_ready else "degraded"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "overall_status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# Startup event
@router.on_event("startup")
async def startup_dspy_system():
    """Initialize DSPy system on startup"""
    try:
        # Initialize DSPy
        if not initialize_dspy():
            logger.error("❌ Failed to initialize DSPy system")
            return
        
        logger.info("✅ DSPy Integration API initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ DSPy startup failed: {e}")
