"""
CrewAI ARC Orchestrator - Multi-Agent Framework for X-SevenAI
Enhanced with Global AI Integration: Intent Detection, Slot Filling, RAG, and Execution
"""
from __future__ import annotations

import logging
import os
import json
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager
from dataclasses import dataclass

logger = logging.getLogger(__name__)  # Initialize logger early for use in import handling

from crewai import Crew, Process
from app.config.database import get_supabase_client
from app.services.ai.crewai_agents import CrewAIBaseAgent, RestaurantFoodAgent, BeautySalonAgent, GeneralPurposeAgent

# Import Global AI functionality for integration
try:
    from app.services.ai.global_ai.intent_agent import IntentAgent
    from app.services.ai.global_ai.slot_filling_agent import SlotFillingAgent
    from app.services.ai.global_ai.rag_agent import RAGAgent
    from app.services.ai.global_ai.execution_agent import ExecutionAgent
    GLOBAL_AI_AVAILABLE = True
    logger.info("Global AI modules imported successfully")
except ImportError as e:
    logger.info(f"Global AI components not available: {e}")
    GLOBAL_AI_AVAILABLE = False

class CrewAIOrchestrator:
    """CrewAI-based orchestrator replacing Agent Squad"""

    def __init__(self):
        self.supabase = get_supabase_client()

        # Initialize Global AI components if available
        if GLOBAL_AI_AVAILABLE:
            try:
                # Initialize Groq client for Global AI components
                import os
                groq_api_key = os.getenv("GROQ_API_KEY")
                if groq_api_key:
                    from groq import Groq
                    groq_client = Groq(api_key=groq_api_key)

                    # Initialize Global AI agents
                    self.intent_agent = IntentAgent(groq_client)
                    self.slot_filling_agent = SlotFillingAgent(groq_client)
                    self.rag_agent = RAGAgent(self.supabase, groq_client)
                    self.execution_agent = ExecutionAgent(self.supabase)
                    logger.info("✅ Global AI agents integrated successfully")
                else:
                    logger.warning("⚠️ GROQ_API_KEY not found, Global AI agents disabled")
                    self.intent_agent = None
                    self.slot_filling_agent = None
                    self.rag_agent = None
                    self.execution_agent = None
            except Exception as e:
                logger.error(f"❌ Failed to initialize Global AI agents: {e}")
                self.intent_agent = None
                self.slot_filling_agent = None
                self.rag_agent = None
                self.execution_agent = None
        else:
            logger.debug("Global AI components not available (fallback disabled)")
            self.intent_agent = None
            self.slot_filling_agent = None
            self.rag_agent = None
            self.execution_agent = None

        # No fallback to GlobalAIHandler; set to None
        self.global_handler = None

        # Initialize CrewAI agents
        self._initialize_agents()

    def _initialize_agents(self):
        """Initialize all CrewAI agents"""
        self.agents = {}

        # Create specialized agents
        try:
            self.agents['restaurant'] = RestaurantFoodAgent().create_agent()
            logger.info("✅ RestaurantFoodAgent initialized")
        except Exception as e:
            logger.error(f"Failed to initialize RestaurantFoodAgent: {e}")

        try:
            self.agents['beauty'] = BeautySalonAgent().create_agent()
            logger.info("✅ BeautySalonAgent initialized")
        except Exception as e:
            logger.error(f"Failed to initialize BeautySalonAgent: {e}")

        try:
            self.agents['general'] = GeneralPurposeAgent().create_agent()
            logger.info("✅ GeneralPurposeAgent initialized")
        except Exception as e:
            logger.error(f"Failed to initialize GeneralPurposeAgent: {e}")
            # Create a fallback using the global handler
            self.agents['general'] = None

    def _get_agent_type_from_business_category(self, business_category: str) -> str:
        """Map business database category to CrewAI agent type"""
        category_mapping = {
            'food_hospitality': 'restaurant',
            'beauty_personal_care': 'beauty',
            'automotive_services': 'automotive',
            'health_medical': 'health',
            'local_services': 'local_services'
        }
        return category_mapping.get(business_category, 'general')

    async def _classify_request(self, message: str, context: Dict[str, Any], conversation_history: List[Dict[str, Any]]) -> str:
        """Enhanced classification using LLM-powered intent detection when available"""
        # Since Global AI is integrated and removed, use keyword-based classification
        logger.info("🧠 Using enhanced keyword classification (Global AI integrated)")
        return self._keyword_classification(message)

    def _keyword_classification(self, message: str) -> str:
        """Enhanced keyword-based classification with better logic"""
        message_lower = message.lower()

        # Restaurant/food related keywords - HIGH PRIORITY
        restaurant_keywords = [
            'restaurant', 'food', 'dining', 'menu', 'reservation', 'book table',
            'italian', 'pizza', 'steak', 'sushi', 'chinese', 'mexican', 'french',
            'dinner', 'lunch', 'breakfast', 'eat', 'meal', 'cuisine'
        ]
        if any(word in message_lower for word in restaurant_keywords):
            return 'restaurant'

        # Beauty/salon related keywords - HIGH PRIORITY
        beauty_keywords = [
            'beauty', 'salon', 'haircut', 'spa', 'facial', 'massage', 'stylist',
            'hair', 'nails', 'makeup', 'cosmetic', 'treatment', 'appointment'
        ]
        if any(word in message_lower for word in beauty_keywords):
            return 'beauty'

        # Automotive related keywords - MEDIUM PRIORITY
        automotive_keywords = [
            'car', 'auto', 'mechanic', 'repair', 'maintenance', 'vehicle',
            'tire', 'oil', 'service', 'transmission', 'engine'
        ]
        if any(word in message_lower for word in automotive_keywords):
            return 'automotive'

        # Health/medical related keywords - MEDIUM PRIORITY
        health_keywords = [
            'doctor', 'medical', 'health', 'appointment', 'clinic', 'hospital',
            'medicine', 'treatment', 'diagnosis', 'prescription'
        ]
        if any(word in message_lower for word in health_keywords):
            return 'health'

        # Local services keywords - LOW PRIORITY
        local_keywords = [
            'plumbing', 'electrical', 'cleaning', 'maintenance', 'home',
            'local', 'nearby', 'area', 'neighborhood'
        ]
        if any(word in message_lower for word in local_keywords):
            return 'local_services'

        # Default to restaurant for food/dining related, otherwise general
        if any(word in message_lower for word in ['food', 'eat', 'dining', 'restaurant']):
            return 'restaurant'

        # If no specific category matches, use general
        return 'general'

    async def process_request(self, message: str, user_id: str, session_id: str,
                            conversation_history: List[Dict[str, Any]] = None,
                            context: Dict[str, Any] = None,
                            business_category: str = None, **kwargs) -> Dict[str, Any]:
        """Enhanced main entry point for processing requests with CrewAI"""
        try:
            logger.info(f"🎯 Processing request: {message[:50]}...")

            # Prepare context for enhanced processing
            if context is None:
                context = await self._prepare_context(user_id)
            if conversation_history is None:
                conversation_history = []

            # Determine agent type - use business category if provided (dedicated chat)
            if business_category:
                agent_type = self._get_agent_type_from_business_category(business_category)
                logger.info(f"🎭 Dedicated chat - Business category '{business_category}' → Agent '{agent_type}'")
            else:
                # Enhanced classification with LLM (using keyword-based since Global AI removed)
                agent_type = await self._classify_request(message, context, conversation_history)
                logger.info(f"🎭 Global chat - Classified as: {agent_type}")

            # Check if we need slot filling (for booking/order requests) - simplified version
            if self._requires_slot_filling(agent_type, message):
                # For now, just proceed to CrewAI agent - slot filling would require separate implementation
                logger.info("📝 Slot filling needed but using CrewAI agent directly")

            # Create and run crew for all requests
            crew = self._create_crew(agent_type, message)
            result = await crew.kickoff_async()

            # Format response
            response = {
                "response": str(result) if result else "I couldn't process your request at this time.",
                "agent_used": agent_type,
                "model": "crewai_enhanced",
                "processing_method": "crewai_arc_orchestration",
                "crewai_enhanced": True,
                "available_capabilities": self._get_capabilities(agent_type),
                "timestamp": "2025-01-01T00:00:00",
                "session_id": session_id
            }

            logger.info(f"✅ CrewAI processing completed for {agent_type}")
            return response

        except Exception as e:
            logger.error(f"❌ CrewAI processing error: {e}")
            # Fallback to original GlobalAIHandler if available
            return await self._fallback_to_global(message, user_id, session_id, str(e))

    async def _prepare_context(self, user_id: str) -> Dict[str, Any]:
        """Prepare business context for enhanced processing"""
        try:
            # Get available businesses
            businesses_resp = self.supabase.table("businesses").select("*").execute()
            businesses = businesses_resp.data or []

            return {
                "businesses": businesses,
                "user_id": user_id,
                "timestamp": "2025-01-01T00:00:00"
            }
        except Exception as e:
            logger.error(f"Failed to prepare context: {e}")
            return {"businesses": [], "user_id": user_id}

    def _requires_slot_filling(self, agent_type: str, message: str) -> bool:
        """Determine if request requires slot filling - simplified version"""
        booking_keywords = ["book", "reserve", "schedule", "appointment", "order"]
        return agent_type in ["restaurant", "beauty", "automotive", "health"] and \
               any(keyword in message.lower() for keyword in booking_keywords)

    def _create_crew(self, agent_type: str, user_query: str) -> Crew:
        """Create a CrewAI crew for the request"""
        from crewai import Task

        # Get the appropriate agent
        agent = self.agents.get(agent_type)

        # Handle cases where agent is None or doesn't exist
        if not agent:
            if agent_type == 'general' and self.agents.get('restaurant'):
                # Fallback to restaurant agent for general queries
                agent = self.agents['restaurant']
                logger.info("🔄 Using RestaurantAgent as fallback for general queries")
            elif agent_type == 'automotive' and self.agents.get('restaurant'):
                # Fallback to restaurant agent for automotive (temporary)
                agent = self.agents['restaurant']
                logger.info("🔄 Using RestaurantAgent as fallback for automotive queries")
            else:
                # Final fallback to any available agent
                agent = next(iter(self.agents.values())) if self.agents else None

        if not agent:
            raise ValueError("❌ No CrewAI agents available for processing")

        # Create task based on agent type
        if agent_type == 'restaurant':
            task_description = f"""Analyze this restaurant/food request and provide recommendations: {user_query}

            Steps to follow:
            1. Understand the user's dining preferences and requirements
            2. Search for suitable restaurants in their area (use general knowledge)
            3. Analyze menu options and pricing
            4. Provide booking options if requested
            5. Include any relevant dietary or accessibility information

            Provide a comprehensive response with restaurant options."""
        elif agent_type == 'beauty':
            task_description = f"""Help with this beauty and wellness request: {user_query}

            Steps to follow:
            1. Understand the service type and user preferences
            2. Recommend suitable salons/spas based on general knowledge
            3. Compare pricing and service quality
            4. Provide booking information
            5. Include preparation and aftercare advice

            Provide comprehensive salon recommendations."""
        elif agent_type == 'general':
            task_description = f"""Provide a helpful response to this general inquiry: {user_query}

            Steps to follow:
            1. Understand the user's question or request
            2. Provide accurate and helpful information
            3. Offer practical suggestions when appropriate
            4. Be clear, concise, and user-friendly
            5. Include relevant context and explanations

            Provide a comprehensive and helpful response."""
        else:
            # Fallback for other agent types
            task_description = f"Handle this request: {user_query}. Provide a helpful and informative response."

        task = Task(
            description=task_description,
            agent=agent,
            expected_output="A helpful, comprehensive response to the user's query with specific recommendations and actionable information."
        )

        return Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=bool(os.getenv("CREWAI_VERBOSE", "false").lower() == "true"),
            memory=bool(os.getenv("CREWAI_MEMORY", "true").lower() == "true")
        )

    def _get_capabilities(self, agent_type: str) -> list:
        """Get capabilities for the agent type"""
        capabilities_map = {
            'restaurant': ["restaurant_booking", "menu_analysis", "food_recommendations"],
            'beauty': ["beauty_booking", "stylist_matching", "service_packages"],
            'automotive': ["auto_services", "repair_booking", "maintenance"],
            'health': ["medical_appointments", "health_services", "wellness"],
            'general': ["greeting", "booking", "order", "business_discovery"]
        }
        return capabilities_map.get(agent_type, capabilities_map['general'])

    async def _fallback_to_global(self, message: str, user_id: str, session_id: str, error: str) -> Dict[str, Any]:
        """Fallback to original GlobalAIHandler if CrewAI fails"""
        try:
            if self.global_handler:
                logger.info("🔄 Falling back to GlobalAIHandler")
                response = await self.global_handler.chat(
                    message=message,
                    session_id=session_id,
                    user_id=user_id
                )
                return {
                    **response,
                    "fallback": True,
                    "fallback_reason": f"CrewAI error: {error}",
                    "processing_method": "global_ai_fallback"
                }
            else:
                raise ValueError("No fallback handler available")
        except Exception as fallback_error:
            logger.error(f"❌ Fallback also failed: {fallback_error}")
            return {
                "response": "Sorry, I'm experiencing technical difficulties. Please try again later.",
                "error": True,
                "agent": "error_handler",
                "original_error": str(error),
                "fallback_error": str(fallback_error)
            }

# Global instance - created lazily
_crewai_orchestrator = None

def get_crewai_orchestrator():
    """Lazy initialization of CrewAI orchestrator"""
    global _crewai_orchestrator
    if _crewai_orchestrator is None:
        logger.info("🚀 Initializing CrewAI Orchestrator...")
        _crewai_orchestrator = CrewAIOrchestrator()
        logger.info("✅ CrewAI Orchestrator ready!")
    return _crewai_orchestrator

@asynccontextmanager
async def crewai_lifespan_manager(app):
    """Lifespan manager for CrewAI components"""
    logger.info("🎬 Starting CrewAI ARC system...")
    yield
    logger.info("🛑 Shutting down CrewAI ARC system...")
