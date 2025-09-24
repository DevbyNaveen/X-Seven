"""
DSPy Startup and Initialization
Handles DSPy system startup and health checks
"""

import logging
import asyncio
from typing import Dict, Any
from datetime import datetime

from .config import initialize_dspy, get_dspy_manager
from .enhanced_conversation_engine import DSPyEnhancedConversationEngine
from .training_data import TrainingDataManager

logger = logging.getLogger(__name__)


async def startup_dspy_system() -> Dict[str, Any]:
    """Initialize DSPy system on application startup"""
    startup_results = {
        "dspy_manager": False,
        "conversation_engine": False,
        "training_manager": False,
        "synthetic_data_generated": False,
        "errors": [],
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        logger.info("🚀 Starting DSPy system initialization...")
        
        # Step 1: Initialize DSPy manager
        try:
            if initialize_dspy():
                startup_results["dspy_manager"] = True
                logger.info("✅ DSPy manager initialized")
            else:
                startup_results["errors"].append("DSPy manager initialization failed")
                logger.error("❌ DSPy manager initialization failed")
        except Exception as e:
            startup_results["errors"].append(f"DSPy manager error: {str(e)}")
            logger.error(f"❌ DSPy manager error: {e}")
        
        # Step 2: Initialize conversation engine
        try:
            conversation_engine = DSPyEnhancedConversationEngine()
            startup_results["conversation_engine"] = True
            logger.info("✅ DSPy conversation engine initialized")
        except Exception as e:
            startup_results["errors"].append(f"Conversation engine error: {str(e)}")
            logger.error(f"❌ Conversation engine error: {e}")
        
        # Step 3: Initialize training manager
        try:
            training_manager = TrainingDataManager()
            startup_results["training_manager"] = True
            logger.info("✅ Training data manager initialized")
        except Exception as e:
            startup_results["errors"].append(f"Training manager error: {str(e)}")
            logger.error(f"❌ Training manager error: {e}")
        
        # Step 4: Generate initial synthetic training data
        try:
            if startup_results["training_manager"]:
                await _generate_initial_training_data(training_manager)
                startup_results["synthetic_data_generated"] = True
                logger.info("✅ Initial training data generated")
        except Exception as e:
            startup_results["errors"].append(f"Training data generation error: {str(e)}")
            logger.warning(f"⚠️ Training data generation error: {e}")
        
        # Overall success check
        critical_components = ["dspy_manager", "conversation_engine", "training_manager"]
        startup_results["success"] = all(startup_results[comp] for comp in critical_components)
        
        if startup_results["success"]:
            logger.info("🎉 DSPy system initialization completed successfully!")
        else:
            logger.warning("⚠️ DSPy system initialization completed with some issues")
        
        return startup_results
        
    except Exception as e:
        logger.error(f"❌ DSPy system initialization failed: {e}")
        startup_results["errors"].append(f"System initialization error: {str(e)}")
        startup_results["success"] = False
        return startup_results


async def _generate_initial_training_data(training_manager: TrainingDataManager):
    """Generate initial synthetic training data"""
    try:
        # Generate minimal training data for each type
        await training_manager.get_intent_training_data(min_examples=30)
        await training_manager.get_routing_training_data(min_examples=30)
        await training_manager.get_response_training_data(min_examples=30)
        
        logger.info("Generated initial synthetic training data")
        
    except Exception as e:
        logger.error(f"Failed to generate initial training data: {e}")
        raise


async def health_check_dspy_system() -> Dict[str, Any]:
    """Perform health check on DSPy system"""
    health_status = {
        "timestamp": datetime.now().isoformat(),
        "overall_status": "unknown",
        "components": {},
        "issues": []
    }
    
    try:
        # Check DSPy manager
        try:
            dspy_manager = get_dspy_manager()
            health_status["components"]["dspy_manager"] = {
                "status": "healthy" if dspy_manager._initialized else "unhealthy",
                "initialized": dspy_manager._initialized
            }
        except Exception as e:
            health_status["components"]["dspy_manager"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["issues"].append(f"DSPy manager: {str(e)}")
        
        # Check conversation engine
        try:
            conversation_engine = DSPyEnhancedConversationEngine()
            modules_ready = all([
                conversation_engine.intent_module is not None,
                conversation_engine.routing_module is not None,
                conversation_engine.response_module is not None
            ])
            
            health_status["components"]["conversation_engine"] = {
                "status": "healthy" if modules_ready else "degraded",
                "modules_ready": modules_ready,
                "optimization_available": conversation_engine.optimizer is not None
            }
            
            if not modules_ready:
                health_status["issues"].append("Some DSPy modules not ready")
                
        except Exception as e:
            health_status["components"]["conversation_engine"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["issues"].append(f"Conversation engine: {str(e)}")
        
        # Check training manager
        try:
            training_manager = TrainingDataManager()
            training_stats = training_manager.get_training_stats()
            
            has_training_data = any(
                stats["total_examples"] > 0 
                for stats in training_stats.values()
            )
            
            health_status["components"]["training_manager"] = {
                "status": "healthy" if has_training_data else "degraded",
                "training_data_available": has_training_data,
                "stats": training_stats
            }
            
            if not has_training_data:
                health_status["issues"].append("No training data available")
                
        except Exception as e:
            health_status["components"]["training_manager"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["issues"].append(f"Training manager: {str(e)}")
        
        # Determine overall status
        component_statuses = [
            comp.get("status", "unknown") 
            for comp in health_status["components"].values()
        ]
        
        if all(status == "healthy" for status in component_statuses):
            health_status["overall_status"] = "healthy"
        elif any(status == "unhealthy" for status in component_statuses):
            health_status["overall_status"] = "unhealthy"
        else:
            health_status["overall_status"] = "degraded"
        
        return health_status
        
    except Exception as e:
        logger.error(f"DSPy health check failed: {e}")
        health_status["overall_status"] = "unhealthy"
        health_status["issues"].append(f"Health check error: {str(e)}")
        return health_status


def get_dspy_system_info() -> Dict[str, Any]:
    """Get DSPy system information"""
    return {
        "version": "1.0.0",
        "components": [
            "DSPy Manager",
            "Enhanced Conversation Engine", 
            "Intent Detection Module",
            "Agent Routing Module",
            "Response Generation Module",
            "Training Data Manager",
            "Optimization Pipeline"
        ],
        "features": [
            "Automatic prompt optimization",
            "Intent detection with confidence scoring",
            "Intelligent agent routing",
            "Context-aware response generation",
            "Business-specific optimization",
            "Training data management",
            "Performance metrics tracking"
        ],
        "optimization_algorithms": [
            "MIPROv2 - Multi-step Instruction Proposal and Refinement Optimization",
            "BootstrapFewShot - Few-shot example generation",
            "COPRO - Constraint-guided Program Optimization"
        ],
        "supported_models": [
            "OpenAI GPT-4o-mini",
            "Groq Llama-3.3-70b-versatile", 
            "Anthropic Claude-3-Opus"
        ]
    }
