"""
Voice Integration Manager

Manages the integration between PipeCat AI and X-Seven's existing
LangGraph, Temporal, CrewAI, and DSPy systems.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
import json

from .voice_pipeline import VoicePipeline
from .pipecat_config import PipeCatConfig, get_pipecat_config

logger = logging.getLogger(__name__)


class VoiceIntegrationManager:
    """
    Manages the integration between PipeCat voice pipeline and X-Seven services.
    """
    
    def __init__(self, config: Optional[PipeCatConfig] = None):
        self.config = config or get_pipecat_config()
        self.voice_pipeline: Optional[VoicePipeline] = None
        self.is_initialized = False
        
        # Integration components
        self.langgraph_integration: Optional['LangGraphVoiceIntegration'] = None
        self.temporal_integration: Optional['TemporalVoiceIntegration'] = None
        self.crewai_integration: Optional['CrewAIVoiceIntegration'] = None
        self.dspy_integration: Optional['DSPyVoiceIntegration'] = None
        
        logger.info("VoiceIntegrationManager initialized")
    
    async def initialize(self) -> bool:
        """Initialize all voice integrations."""
        try:
            # Initialize voice pipeline
            self.voice_pipeline = VoicePipeline(self.config)
            pipeline_success = await self.voice_pipeline.initialize()
            
            if not pipeline_success:
                logger.error("Failed to initialize voice pipeline")
                return False
            
            # Initialize integrations
            await self._initialize_integrations()
            
            # Set up integration callbacks
            self._setup_integration_callbacks()
            
            self.is_initialized = True
            logger.info("Voice integration manager initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize voice integration manager: {e}")
            return False
    
    async def _initialize_integrations(self):
        """Initialize individual integration components."""
        try:
            # LangGraph integration
            if self.config.enable_langgraph_integration:
                self.langgraph_integration = LangGraphVoiceIntegration()
                await self.langgraph_integration.initialize()
                logger.info("LangGraph voice integration initialized")
            
            # Temporal integration
            if self.config.enable_temporal_integration:
                self.temporal_integration = TemporalVoiceIntegration()
                await self.temporal_integration.initialize()
                logger.info("Temporal voice integration initialized")
            
            # CrewAI integration
            if self.config.enable_crewai_integration:
                self.crewai_integration = CrewAIVoiceIntegration()
                await self.crewai_integration.initialize()
                logger.info("CrewAI voice integration initialized")
            
            # DSPy integration
            if self.config.enable_dspy_integration:
                self.dspy_integration = DSPyVoiceIntegration()
                await self.dspy_integration.initialize()
                logger.info("DSPy voice integration initialized")
                
        except Exception as e:
            logger.error(f"Error initializing integrations: {e}")
    
    def _setup_integration_callbacks(self):
        """Set up callbacks for voice pipeline integrations."""
        if not self.voice_pipeline:
            return
        
        # Create callback functions
        langgraph_callback = None
        if self.langgraph_integration:
            langgraph_callback = self.langgraph_integration.process_voice_message
        
        temporal_callback = None
        if self.temporal_integration:
            temporal_callback = self.temporal_integration.start_voice_workflow
        
        crewai_callback = None
        if self.crewai_integration:
            crewai_callback = self.crewai_integration.coordinate_voice_agents
        
        dspy_callback = None
        if self.dspy_integration:
            dspy_callback = self.dspy_integration.optimize_voice_response
        
        # Set callbacks in voice pipeline
        self.voice_pipeline.set_integration_callbacks(
            langgraph_callback=langgraph_callback,
            temporal_callback=temporal_callback,
            crewai_callback=crewai_callback,
            dspy_callback=dspy_callback
        )
        
        logger.info("Integration callbacks configured")
    
    async def start(self) -> bool:
        """Start the voice integration system."""
        if not self.is_initialized:
            logger.error("Voice integration manager not initialized")
            return False
        
        if not self.voice_pipeline:
            logger.error("Voice pipeline not available")
            return False
        
        try:
            # Start voice pipeline
            success = await self.voice_pipeline.start()
            if success:
                logger.info("Voice integration system started successfully")
            return success
            
        except Exception as e:
            logger.error(f"Failed to start voice integration system: {e}")
            return False
    
    async def stop(self) -> bool:
        """Stop the voice integration system."""
        try:
            if self.voice_pipeline:
                await self.voice_pipeline.stop()
            
            logger.info("Voice integration system stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop voice integration system: {e}")
            return False
    
    async def process_voice_call(self, session_id: str, call_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a voice call through the integrated system."""
        if not self.voice_pipeline:
            return {
                "success": False,
                "error": "Voice pipeline not available",
                "session_id": session_id
            }
        
        return await self.voice_pipeline.process_voice_call(session_id, call_data)
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get the status of the voice integration system."""
        status = {
            "initialized": self.is_initialized,
            "pipeline_running": self.voice_pipeline.is_running if self.voice_pipeline else False,
            "integrations": {
                "langgraph": self.langgraph_integration is not None,
                "temporal": self.temporal_integration is not None,
                "crewai": self.crewai_integration is not None,
                "dspy": self.dspy_integration is not None,
            },
            "metrics": self.voice_pipeline.get_metrics() if self.voice_pipeline else {},
            "active_sessions": len(self.voice_pipeline.get_active_sessions()) if self.voice_pipeline else 0,
        }
        
        return status


class LangGraphVoiceIntegration:
    """Integration with LangGraph for voice conversation flows."""
    
    def __init__(self):
        self.conversation_engine = None
        self.is_initialized = False
        
    async def initialize(self):
        """Initialize LangGraph integration."""
        try:
            # Import LangGraph components
            from app.api.v1.langgraph_conversation_api import ConversationEngine
            self.conversation_engine = ConversationEngine()
            self.is_initialized = True
            logger.info("LangGraph voice integration initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize LangGraph integration: {e}")
    
    async def process_voice_message(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Process voice message through LangGraph conversation flow."""
        if not self.is_initialized or not self.conversation_engine:
            return message
        
        try:
            # Create session context for voice
            voice_context = {
                "channel": "voice",
                "input_type": "speech",
                "requires_voice_optimization": True,
                **(context or {})
            }
            
            # Process through LangGraph
            response = await self.conversation_engine.process_message(
                message=message,
                context=voice_context
            )
            
            # Extract response text
            if isinstance(response, dict) and "message" in response:
                return response["message"]
            elif isinstance(response, str):
                return response
            else:
                return str(response)
                
        except Exception as e:
            logger.error(f"Error in LangGraph voice processing: {e}")
            return message


class TemporalVoiceIntegration:
    """Integration with Temporal for voice workflow orchestration."""
    
    def __init__(self):
        self.temporal_manager = None
        self.is_initialized = False
    
    async def initialize(self):
        """Initialize Temporal integration with readiness check."""
        try:
            from app.workflows.temporal_integration import get_temporal_manager
            self.temporal_manager = get_temporal_manager()
            # Ensure the Temporal manager is initialized (connects to server)
            await self.temporal_manager.initialize()
            # Verify server availability
            if not await self.temporal_manager.is_ready():
                logger.warning("⚠️ Temporal server unavailable – TemporalVoiceIntegration disabled")
                self.is_initialized = False
                self.temporal_manager = None
                return
            self.is_initialized = True
            logger.info("✅ Temporal voice integration initialized and ready")
        except Exception as e:
            logger.error(f"Failed to initialize Temporal integration: {e}")
            self.is_initialized = False
            self.temporal_manager = None
    
    async def start_voice_workflow(self, message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Start a Temporal workflow for voice processing."""
        if not self.is_initialized or not self.temporal_manager:
            return {"success": False, "error": "Temporal not initialized"}
        
        try:
            # Create voice workflow context
            workflow_context = {
                "type": "voice_interaction",
                "message": message,
                "timestamp": datetime.now().isoformat(),
                **(context or {})
            }
            
            # Start workflow
            workflow_id = f"voice_workflow_{datetime.now().timestamp()}"
            result = await self.temporal_manager.start_workflow(
                workflow_id=workflow_id,
                workflow_type="voice_processing",
                context=workflow_context
            )
            
            return {
                "success": True,
                "workflow_id": workflow_id,
                "result": result
            }
            
        except Exception as e:
            logger.error(f"Error starting Temporal voice workflow: {e}")
            return {"success": False, "error": str(e)}


class CrewAIVoiceIntegration:
    """Integration with CrewAI for multi-agent voice coordination."""
    
    def __init__(self):
        self.crew_orchestrator = None
        self.is_initialized = False
    
    async def initialize(self):
        """Initialize CrewAI integration."""
        try:
            from app.api.v1.crewai_langgraph_integration import CrewAIOrchestrator
            self.crew_orchestrator = CrewAIOrchestrator()
            self.is_initialized = True
            logger.info("CrewAI voice integration initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize CrewAI integration: {e}")
    
    async def coordinate_voice_agents(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Coordinate multiple agents for voice response."""
        if not self.is_initialized or not self.crew_orchestrator:
            return message
        
        try:
            # Create voice-specific agent context
            agent_context = {
                "input_type": "voice",
                "response_format": "conversational",
                "optimize_for_speech": True,
                **(context or {})
            }
            
            # Process through CrewAI
            result = await self.crew_orchestrator.process_with_crew(
                message=message,
                context=agent_context
            )
            
            # Extract response
            if isinstance(result, dict) and "response" in result:
                return result["response"]
            elif isinstance(result, str):
                return result
            else:
                return str(result)
                
        except Exception as e:
            logger.error(f"Error in CrewAI voice coordination: {e}")
            return message


class DSPyVoiceIntegration:
    """Integration with DSPy for voice-optimized responses."""
    
    def __init__(self):
        self.dspy_system = None
        self.voice_modules = {}
        self.is_initialized = False
    
    async def initialize(self):
        """Initialize DSPy integration."""
        try:
            from app.core.dspy.manager import DSPyManager
            self.dspy_system = DSPyManager()
            
            # Initialize voice-specific modules
            await self._initialize_voice_modules()
            
            self.is_initialized = True
            logger.info("DSPy voice integration initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize DSPy integration: {e}")
    
    async def _initialize_voice_modules(self):
        """Initialize voice-specific DSPy modules."""
        try:
            # Voice response optimization module
            self.voice_modules["response_optimizer"] = await self._create_voice_response_module()
            
            # Voice intent detection module
            self.voice_modules["intent_detector"] = await self._create_voice_intent_module()
            
            # Voice conversation summary module
            self.voice_modules["conversation_summarizer"] = await self._create_voice_summary_module()
            
            logger.info("DSPy voice modules initialized")
            
        except Exception as e:
            logger.error(f"Error initializing DSPy voice modules: {e}")
    
    async def _create_voice_response_module(self):
        """Create voice response optimization module."""
        # This would create a DSPy module optimized for voice responses
        # Placeholder implementation
        return {
            "type": "voice_response_optimizer",
            "description": "Optimizes responses for natural speech delivery"
        }
    
    async def _create_voice_intent_module(self):
        """Create voice intent detection module."""
        # This would create a DSPy module for voice intent detection
        # Placeholder implementation
        return {
            "type": "voice_intent_detector",
            "description": "Detects intents from voice input with speech-specific optimizations"
        }
    
    async def _create_voice_summary_module(self):
        """Create voice conversation summary module."""
        # This would create a DSPy module for voice conversation summarization
        # Placeholder implementation
        return {
            "type": "voice_conversation_summarizer",
            "description": "Summarizes voice conversations for context preservation"
        }
    
    async def optimize_voice_response(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Optimize response for voice delivery using DSPy."""
        if not self.is_initialized or not self.voice_modules:
            return message
        
        try:
            # Voice-specific optimizations
            optimized_message = message
            
            # Apply voice response optimization
            if "response_optimizer" in self.voice_modules:
                optimized_message = await self._apply_voice_optimization(
                    optimized_message, context
                )
            
            # Apply conversational formatting
            optimized_message = self._format_for_speech(optimized_message)
            
            return optimized_message
            
        except Exception as e:
            logger.error(f"Error in DSPy voice optimization: {e}")
            return message
    
    async def _apply_voice_optimization(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Apply DSPy voice optimization."""
        # Placeholder for actual DSPy optimization
        # This would use trained DSPy modules to optimize the response
        
        # Simple optimizations for voice
        optimized = message
        
        # Make more conversational
        if not optimized.endswith(('.', '!', '?')):
            optimized += '.'
        
        # Add natural speech patterns
        if len(optimized) > 200:
            # Break long responses into shorter sentences
            sentences = optimized.split('. ')
            if len(sentences) > 3:
                optimized = '. '.join(sentences[:3]) + '.'
        
        return optimized
    
    def _format_for_speech(self, message: str) -> str:
        """Format message for natural speech delivery."""
        # Convert abbreviations to full words
        replacements = {
            "AI": "A I",
            "API": "A P I",
            "URL": "U R L",
            "HTTP": "H T T P",
            "JSON": "J S O N",
            "&": "and",
            "@": "at",
            "%": "percent",
        }
        
        formatted = message
        for abbrev, full in replacements.items():
            formatted = formatted.replace(abbrev, full)
        
        return formatted


# Global integration manager instance
_integration_manager: Optional[VoiceIntegrationManager] = None


def get_voice_integration_manager() -> VoiceIntegrationManager:
    """Get the global voice integration manager instance."""
    global _integration_manager
    if _integration_manager is None:
        _integration_manager = VoiceIntegrationManager()
    return _integration_manager


async def initialize_voice_integration() -> bool:
    """Initialize the voice integration system."""
    manager = get_voice_integration_manager()
    return await manager.initialize()


async def start_voice_integration() -> bool:
    """Start the voice integration system."""
    manager = get_voice_integration_manager()
    return await manager.start()


async def stop_voice_integration() -> bool:
    """Stop the voice integration system."""
    manager = get_voice_integration_manager()
    return await manager.stop()
