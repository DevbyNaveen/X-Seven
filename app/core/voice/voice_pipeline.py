"""
PipeCat Voice Pipeline Implementation

This module implements the core voice pipeline using PipeCat AI framework
with integration to X-Seven's existing services.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
import json

try:
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineTask
    from pipecat.services.elevenlabs import ElevenLabsTTSService
    from pipecat.services.openai import OpenAILLMService, OpenAISTTService
    from pipecat.transports.services.twilio import TwilioTransport
    from pipecat.transports.services.websocket import WebsocketTransport
    from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
    from pipecat.frames.frames import (
        Frame, AudioRawFrame, TextFrame, TranscriptionFrame,
        TTSStartedFrame, TTSStoppedFrame, LLMResponseStartFrame,
        LLMResponseEndFrame, UserStartedSpeakingFrame, UserStoppedSpeakingFrame
    )
    PIPECAT_AVAILABLE = True
except ImportError:
    PIPECAT_AVAILABLE = False
    # Create mock classes for development
    class Pipeline: pass
    class PipelineRunner: pass
    class PipelineTask: pass
    class ElevenLabsTTSService: pass
    class OpenAILLMService: pass
    class OpenAISTTService: pass
    class TwilioTransport: pass
    class WebsocketTransport: pass
    class OpenAILLMContext: pass
    class Frame: pass
    class AudioRawFrame: pass
    class TextFrame: pass
    class TranscriptionFrame: pass

from .pipecat_config import PipeCatConfig, get_pipecat_config, VoiceProvider, STTProvider, TransportType

logger = logging.getLogger(__name__)


class VoicePipelineMetrics:
    """Voice pipeline performance metrics."""
    
    def __init__(self):
        self.call_count = 0
        self.active_calls = 0
        self.total_duration = 0.0
        self.average_latency = 0.0
        self.error_count = 0
        self.last_error: Optional[str] = None
        self.start_time = datetime.now()
    
    def increment_calls(self):
        """Increment call counter."""
        self.call_count += 1
        self.active_calls += 1
    
    def decrement_calls(self):
        """Decrement active calls."""
        self.active_calls = max(0, self.active_calls - 1)
    
    def add_duration(self, duration: float):
        """Add call duration."""
        self.total_duration += duration
    
    def update_latency(self, latency: float):
        """Update average latency."""
        if self.call_count > 0:
            self.average_latency = ((self.average_latency * (self.call_count - 1)) + latency) / self.call_count
    
    def increment_errors(self, error: str):
        """Increment error counter."""
        self.error_count += 1
        self.last_error = error
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        uptime = (datetime.now() - self.start_time).total_seconds()
        return {
            "call_count": self.call_count,
            "active_calls": self.active_calls,
            "total_duration": self.total_duration,
            "average_duration": self.total_duration / max(1, self.call_count),
            "average_latency": self.average_latency,
            "error_count": self.error_count,
            "error_rate": self.error_count / max(1, self.call_count),
            "last_error": self.last_error,
            "uptime_seconds": uptime,
        }


class VoicePipeline:
    """
    Main voice pipeline class that orchestrates PipeCat AI components
    with X-Seven's existing services.
    """
    
    def __init__(self, config: Optional[PipeCatConfig] = None):
        self.config = config or get_pipecat_config()
        self.metrics = VoicePipelineMetrics()
        self.pipeline: Optional[Pipeline] = None
        self.runner: Optional[PipelineRunner] = None
        self.is_running = False
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        
        # Integration callbacks
        self.langgraph_callback: Optional[Callable] = None
        self.temporal_callback: Optional[Callable] = None
        self.crewai_callback: Optional[Callable] = None
        self.dspy_callback: Optional[Callable] = None
        
        logger.info("VoicePipeline initialized")
    
    def set_integration_callbacks(self,
                                langgraph_callback: Optional[Callable] = None,
                                temporal_callback: Optional[Callable] = None,
                                crewai_callback: Optional[Callable] = None,
                                dspy_callback: Optional[Callable] = None):
        """Set integration callbacks for X-Seven services."""
        self.langgraph_callback = langgraph_callback
        self.temporal_callback = temporal_callback
        self.crewai_callback = crewai_callback
        self.dspy_callback = dspy_callback
        logger.info("Integration callbacks configured")
    
    async def initialize(self) -> bool:
        """Initialize the voice pipeline."""
        if not PIPECAT_AVAILABLE:
            logger.error("PipeCat AI is not available. Please install: pip install pipecat-ai")
            return False
        
        try:
            # Validate configuration
            errors = self.config.validate()
            if errors:
                logger.error(f"Configuration validation failed: {errors}")
                return False
            
            # Create services based on configuration
            services = await self._create_services()
            if not services:
                logger.error("Failed to create voice services")
                return False
            
            # Create pipeline
            self.pipeline = Pipeline(services)
            
            # Create runner
            self.runner = PipelineRunner()
            
            logger.info("Voice pipeline initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize voice pipeline: {e}")
            self.metrics.increment_errors(str(e))
            return False
    
    async def _create_services(self) -> Optional[List[Any]]:
        """Create PipeCat services based on configuration."""
        services = []
        
        try:
            # Create transport
            transport = await self._create_transport()
            if transport:
                services.append(transport)
            
            # Create STT service
            stt_service = await self._create_stt_service()
            if stt_service:
                services.append(stt_service)
            
            # Create LLM service (with X-Seven integration)
            llm_service = await self._create_llm_service()
            if llm_service:
                services.append(llm_service)
            
            # Create TTS service
            tts_service = await self._create_tts_service()
            if tts_service:
                services.append(tts_service)
            
            return services if services else None
            
        except Exception as e:
            logger.error(f"Failed to create services: {e}")
            return None
    
    async def _create_transport(self) -> Optional[Any]:
        """Create transport service."""
        try:
            if self.config.transport_settings.type == TransportType.TWILIO:
                return TwilioTransport(
                    account_sid=self.config.transport_settings.account_sid,
                    auth_token=self.config.transport_settings.auth_token,
                    phone_number=self.config.transport_settings.phone_number
                )
            elif self.config.transport_settings.type == TransportType.WEBSOCKET:
                return WebsocketTransport(
                    host=self.config.transport_settings.host,
                    port=self.config.transport_settings.port
                )
            else:
                logger.warning(f"Unsupported transport type: {self.config.transport_settings.type}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to create transport: {e}")
            return None
    
    async def _create_stt_service(self) -> Optional[Any]:
        """Create speech-to-text service."""
        try:
            if self.config.stt_settings.provider == STTProvider.OPENAI_WHISPER:
                return OpenAISTTService(
                    model=self.config.stt_settings.model,
                    language=self.config.stt_settings.language,
                    temperature=self.config.stt_settings.temperature
                )
            else:
                logger.warning(f"Unsupported STT provider: {self.config.stt_settings.provider}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to create STT service: {e}")
            return None
    
    async def _create_llm_service(self) -> Optional[Any]:
        """Create LLM service with X-Seven integration."""
        try:
            # Create base OpenAI LLM service
            llm_service = OpenAILLMService(
                model=self.config.llm_settings.model,
                temperature=self.config.llm_settings.temperature,
                max_tokens=self.config.llm_settings.max_tokens
            )
            
            # Wrap with X-Seven integration
            return XSevenLLMWrapper(
                llm_service=llm_service,
                langgraph_callback=self.langgraph_callback,
                temporal_callback=self.temporal_callback,
                crewai_callback=self.crewai_callback,
                dspy_callback=self.dspy_callback
            )
            
        except Exception as e:
            logger.error(f"Failed to create LLM service: {e}")
            return None
    
    async def _create_tts_service(self) -> Optional[Any]:
        """Create text-to-speech service."""
        try:
            if self.config.voice_settings.provider == VoiceProvider.ELEVENLABS:
                return ElevenLabsTTSService(
                    voice_id=self.config.voice_settings.voice_id,
                    stability=self.config.voice_settings.stability,
                    similarity_boost=self.config.voice_settings.similarity_boost,
                    style=self.config.voice_settings.style,
                    use_speaker_boost=self.config.voice_settings.use_speaker_boost,
                    optimize_streaming_latency=self.config.voice_settings.optimize_streaming_latency,
                    output_format=self.config.voice_settings.output_format
                )
            else:
                logger.warning(f"Unsupported TTS provider: {self.config.voice_settings.provider}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to create TTS service: {e}")
            return None
    
    async def start(self) -> bool:
        """Start the voice pipeline."""
        if not self.pipeline or not self.runner:
            logger.error("Pipeline not initialized")
            return False
        
        try:
            # Create pipeline task
            task = PipelineTask(self.pipeline)
            
            # Start the runner
            await self.runner.run(task)
            
            self.is_running = True
            logger.info("Voice pipeline started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start voice pipeline: {e}")
            self.metrics.increment_errors(str(e))
            return False
    
    async def stop(self) -> bool:
        """Stop the voice pipeline."""
        try:
            if self.runner:
                await self.runner.stop()
            
            self.is_running = False
            logger.info("Voice pipeline stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop voice pipeline: {e}")
            return False
    
    async def process_voice_call(self, session_id: str, call_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process an incoming voice call."""
        start_time = datetime.now()
        self.metrics.increment_calls()
        
        try:
            # Store session data
            self.active_sessions[session_id] = {
                "start_time": start_time,
                "call_data": call_data,
                "status": "active"
            }
            
            # Process through pipeline
            result = await self._process_call_through_pipeline(session_id, call_data)
            
            # Calculate duration and update metrics
            duration = (datetime.now() - start_time).total_seconds()
            self.metrics.add_duration(duration)
            
            # Update session
            self.active_sessions[session_id]["status"] = "completed"
            self.active_sessions[session_id]["duration"] = duration
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing voice call {session_id}: {e}")
            self.metrics.increment_errors(str(e))
            
            # Update session
            if session_id in self.active_sessions:
                self.active_sessions[session_id]["status"] = "error"
                self.active_sessions[session_id]["error"] = str(e)
            
            return {
                "success": False,
                "error": str(e),
                "session_id": session_id
            }
        
        finally:
            self.metrics.decrement_calls()
    
    async def _process_call_through_pipeline(self, session_id: str, call_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process call through the PipeCat pipeline."""
        # This is a simplified version - actual implementation would depend on PipeCat's API
        logger.info(f"Processing call {session_id} through pipeline")
        
        # Simulate pipeline processing
        return {
            "success": True,
            "session_id": session_id,
            "message": "Call processed successfully",
            "timestamp": datetime.now().isoformat()
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get pipeline metrics."""
        return self.metrics.to_dict()
    
    def get_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Get active voice sessions."""
        return self.active_sessions.copy()
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific session."""
        return self.active_sessions.get(session_id)


class XSevenLLMWrapper:
    """
    Wrapper for LLM service that integrates with X-Seven's
    LangGraph, Temporal, CrewAI, and DSPy systems.
    """
    
    def __init__(self,
                 llm_service: Any,
                 langgraph_callback: Optional[Callable] = None,
                 temporal_callback: Optional[Callable] = None,
                 crewai_callback: Optional[Callable] = None,
                 dspy_callback: Optional[Callable] = None):
        self.llm_service = llm_service
        self.langgraph_callback = langgraph_callback
        self.temporal_callback = temporal_callback
        self.crewai_callback = crewai_callback
        self.dspy_callback = dspy_callback
        
        logger.info("XSevenLLMWrapper initialized")
    
    async def process_frame(self, frame: Any) -> Any:
        """Process frame through X-Seven integrations."""
        try:
            # Extract text from frame
            if hasattr(frame, 'text'):
                text = frame.text
                
                # Process through X-Seven integrations
                enhanced_response = await self._process_through_integrations(text)
                
                # Update frame with enhanced response
                if hasattr(frame, 'text'):
                    frame.text = enhanced_response
                
                return frame
            
            # Pass through if no text
            return await self.llm_service.process_frame(frame)
            
        except Exception as e:
            logger.error(f"Error in XSevenLLMWrapper: {e}")
            return await self.llm_service.process_frame(frame)
    
    async def _process_through_integrations(self, text: str) -> str:
        """Process text through X-Seven integrations."""
        try:
            # Start with original text
            processed_text = text
            
            # DSPy optimization (if available)
            if self.dspy_callback:
                try:
                    processed_text = await self.dspy_callback(processed_text)
                    logger.debug("Text processed through DSPy")
                except Exception as e:
                    logger.warning(f"DSPy processing failed: {e}")
            
            # LangGraph processing (if available)
            if self.langgraph_callback:
                try:
                    processed_text = await self.langgraph_callback(processed_text)
                    logger.debug("Text processed through LangGraph")
                except Exception as e:
                    logger.warning(f"LangGraph processing failed: {e}")
            
            # CrewAI processing (if available)
            if self.crewai_callback:
                try:
                    processed_text = await self.crewai_callback(processed_text)
                    logger.debug("Text processed through CrewAI")
                except Exception as e:
                    logger.warning(f"CrewAI processing failed: {e}")
            
            # Temporal workflow (if available)
            if self.temporal_callback:
                try:
                    await self.temporal_callback(processed_text)
                    logger.debug("Text processed through Temporal")
                except Exception as e:
                    logger.warning(f"Temporal processing failed: {e}")
            
            return processed_text
            
        except Exception as e:
            logger.error(f"Error in integration processing: {e}")
            return text  # Return original text on error
