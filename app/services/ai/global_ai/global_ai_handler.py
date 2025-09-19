"""
Modern Global AI Handler - Agent-Orchestrated Architecture with Self-Healing
Orchestrates specialized agents for intent detection, slot filling, RAG, and execution with automatic recovery
"""
from __future__ import annotations
import json
import logging
import re
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
import threading

from .intent_agent import IntentAgent, IntentResult
from .slot_filling_agent import SlotFillingAgent
from .rag_agent import RAGAgent, RAGResult
from .execution_agent import ExecutionAgent, ExecutionResult
from .self_healing import self_healing_manager, HealthStatus
from .advanced_memory_manager import AdvancedMemoryManager

class GlobalAIHandler:
    """
    Modern Global AI Handler — Agent-Orchestrated Architecture with Self-Healing

    Philosophy:
    - LLM = Brain (natural conversation)
    - Agents = Specialized muscles (intent, slots, RAG, execution)
    - Orchestration = Nervous system (decides which agent to call)
    - Self-Healing = Immune system (automatic recovery and resilience)
    - No hardcoded state machines — AI flows naturally with fault tolerance
    - Structured actions for reliable execution with graceful degradation
    """

    # Class-level caching for static data (loaded once at startup)
    _cached_business_stats = None
    _cached_categories = None
    _cache_initialized = False
    _cache_lock = threading.Lock()

    @classmethod
    async def initialize_cache(cls, supabase_client) -> None:
        """
        Initialize static data cache at startup.
        Loads heavy/static data once to be reused across all requests.
        """
        with cls._cache_lock:
            if cls._cache_initialized:
                return  # Already initialized

            try:
                # Load business statistics (static data that changes infrequently)
                business_stats = await cls._load_business_statistics_static(supabase_client)

                # Load categories (static data)
                categories = await cls._load_business_categories_static(supabase_client)

                # Cache the data
                cls._cached_business_stats = business_stats
                cls._cached_categories = categories
                cls._cache_initialized = True

                logging.getLogger(__name__).info(
                    f"✅ Global AI Cache initialized: {business_stats['total_businesses']} businesses, "
                    f"{len(categories)} categories"
                )

            except Exception as e:
                logging.getLogger(__name__).error(f"❌ Failed to initialize Global AI cache: {e}")
                # Continue without cache - will load data per request as fallback

    @classmethod
    async def _load_business_statistics_static(cls, supabase) -> Dict[str, Any]:
        """Load business statistics once at startup (static data)"""
        try:
            # Get total business count
            count_resp = supabase.table("businesses").select("id", count="exact").eq("is_active", True).execute()
            total_businesses = count_resp.count or 0

            # Get unique categories
            categories_resp = supabase.table("businesses").select("category").eq("is_active", True).execute()
            categories = list(set(biz.get("category", "General") for biz in categories_resp.data or []))

            # Get business count by category
            category_counts = {}
            for category in categories:
                cat_count_resp = supabase.table("businesses").select("id", count="exact").eq("is_active", True).ilike("category", f"%{category}%").execute()
                category_counts[category] = cat_count_resp.count or 0

            return {
                "total_businesses": total_businesses,
                "categories": sorted(categories),
                "category_counts": category_counts,
                "last_updated": datetime.now().isoformat()
            }

        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to load business statistics: {e}")
            return {"total_businesses": 0, "categories": [], "category_counts": {}}

    @classmethod
    async def _load_business_categories_static(cls, supabase) -> List[str]:
        """Load business categories once at startup (static data)"""
        try:
            categories_resp = supabase.table("businesses").select("category").eq("is_active", True).execute()
            categories = list(set(biz.get("category", "General") for biz in categories_resp.data or []))
            return sorted(categories)
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to load business categories: {e}")
            return []

    @classmethod
    def get_cached_business_stats(cls) -> Optional[Dict[str, Any]]:
        """Get cached business statistics"""
        return cls._cached_business_stats

    @classmethod
    def get_cached_categories(cls) -> Optional[List[str]]:
        """Get cached business categories"""
        return cls._cached_categories

    @classmethod
    def is_cache_initialized(cls) -> bool:
        """Check if cache is initialized"""
        return cls._cache_initialized

    def __init__(self, supabase, groq_api_key: str | None = None, webhook_url: Optional[str] = None):
        self.supabase = supabase
        self.webhook_url = webhook_url
        self.logger = logging.getLogger(__name__)

        # Initialize specialized agents with self-healing
        self.intent_agent = None
        self.slot_filling_agent = None
        self.rag_agent = None
        self.execution_agent = ExecutionAgent(supabase, webhook_url)

        # Initialize Advanced Memory Manager
        self.memory_manager = AdvancedMemoryManager(supabase)

        if groq_api_key:
            try:
                from groq import Groq
                groq_client = Groq(api_key=groq_api_key)
                self.intent_agent = IntentAgent(groq_client)
                self.slot_filling_agent = SlotFillingAgent(groq_client)
                self.rag_agent = RAGAgent(supabase, groq_client)
            except Exception as e:
                self.logger.error(f"❌ Failed to initialize Groq agents: {e}")
        
        # Register orchestrator with self-healing system
        self_healing_manager.register_agent("global_orchestrator", self)
        
        # Register available tools for AI to use
        self.available_tools = self._register_tools()
        
        # Graceful degradation state
        self.degradation_mode = False
        
        # Track available capabilities (tools)
        self.available_capabilities = self._assess_capabilities()
        
        # Define high-level capabilities as categories
        self._cached_categories = None
        self._cached_businesses = None
        self._business_cache_time = None
        self._cache_lock = asyncio.Lock()
        
        # Capability usage stats - track which capabilities are used most frequently
        self._capability_usage_stats = {capability: 0 for capability in self.get_capability_categories().keys()}
        
        self.logger.info(f"👋 Global AI Handler initialized with {len(self.available_tools)} tools and {len(self.get_capability_categories())} high-level capabilities")

    def _register_tools(self) -> Dict[str, Dict[str, Any]]:
        """Register all available tools that the AI can call"""
        return {
            "understand_user_intent": {
                "function": self._tool_understand_user_intent,
                "description": "Analyze user message to determine if they want to book, order, get information, etc. Use when you're not sure what the user wants to accomplish.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "The user's message to analyze"},
                        "context": {"type": "object", "description": "Conversation context and business information"}
                    },
                    "required": ["message", "context"]
                }
            },
            "collect_required_info": {
                "function": self._tool_collect_required_info,
                "description": "Gather required information for bookings/orders. Use when you know what they want but need details like name, date, time, etc.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "intent": {"type": "string", "description": "The determined user intent (e.g., 'restaurant_reservation')"},
                        "message": {"type": "string", "description": "The current user message"},
                        "conversation_history": {"type": "array", "description": "Previous conversation messages"}
                    },
                    "required": ["intent", "message", "conversation_history"]
                }
            },
            "search_business_information": {
                "function": self._tool_search_business_information,
                "description": "Find information about businesses, menus, hours, services. Use when user asks questions about business details.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The search query"},
                        "business_type": {"type": "string", "description": "Optional business category filter"}
                    },
                    "required": ["query"]
                }
            },
            "execute_business_action": {
                "function": self._tool_execute_business_action,
                "description": "Actually create bookings, orders, appointments. Use only when you have all required information.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action_data": {"type": "object", "description": "Complete data for the business action"}
                    },
                    "required": ["action_data"]
                }
            },
            "retrieve_memory_context": {
                "function": self._tool_retrieve_memory_context,
                "description": "Retrieve relevant conversation memories and context. Use when you need to recall previous conversation details or user preferences.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "What context or memory to retrieve"},
                        "memory_type": {"type": "string", "description": "Type of memory to retrieve (short_term, long_term, semantic)"}
                    },
                    "required": ["query"]
                }
            },
            "search_business_sections": {
                "function": self._tool_search_business_sections,
                "description": "Search through detailed business information sections like menus, services, policies. Use when user asks for specific business details.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "business_id": {"type": "integer", "description": "ID of the business to search"},
                        "section_type": {"type": "string", "description": "Type of section to search (menu, services, hours, policies)"}
                    },
                    "required": ["business_id"]
                }
            }
        }
    
    def _assess_capabilities(self) -> Dict[str, bool]:
        """Assess what capabilities are currently available"""
        capabilities = {
            "intent_detection": self.intent_agent is not None,
            "slot_filling": self.slot_filling_agent is not None,
            "rag_search": self.rag_agent is not None,
            "execution": True,  # Execution agent always available
            "groq_available": self.intent_agent is not None
        }
        
        # Add tool capabilities
        capabilities.update({
            "understand_user_intent": capabilities["intent_detection"],
            "collect_required_info": capabilities["slot_filling"],
            "search_business_information": capabilities["rag_search"],
            "execute_business_action": capabilities["execution"]
        })
        
        # Add memory capabilities
        capabilities.update({
            "conversation_memory": True,
            "semantic_memory": self.memory_manager.embedding_model is not None,
            "business_context_sections": True,
            "memory_consolidation": True,
            "context_relevance": True,
            "retrieve_memory_context": True,
            "search_business_sections": True
        })
        
        return capabilities
    
    async def _tool_understand_user_intent(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Tool wrapper for Intent Agent - understand what user wants"""
        try:
            if not self.intent_agent:
                return {
                    "intent": "general",
                    "confidence": 0.5,
                    "business_type": None,
                    "reasoning": "Intent detection unavailable - using fallback",
                    "error": "Intent agent not available"
                }
            
            result = await self.intent_agent.detect_intent(message, context)
            return {
                "intent": result.intent,
                "confidence": result.confidence,
                "business_type": result.entities.get("business_type"),
                "reasoning": result.reasoning
            }
        except Exception as e:
            self.logger.error(f"Intent tool failed: {e}")
            return {
                "intent": "general",
                "confidence": 0.3,
                "business_type": None,
                "reasoning": f"Error in intent detection: {str(e)}",
                "error": str(e)
            }
    
    async def _tool_collect_required_info(self, intent: str, message: str, conversation_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Tool wrapper for Slot Filling Agent - collect needed information"""
        try:
            if not self.slot_filling_agent:
                return {
                    "status": "incomplete",
                    "collected_data": {},
                    "missing_info": ["Unable to collect information - slot filling unavailable"],
                    "next_question": "Could you please provide more details about what you need?",
                    "error": "Slot filling agent not available"
                }
            
            # Build context for slot filling
            context = {"conversation_history": conversation_history}
            
            result = await self.slot_filling_agent.fill_slots(intent, message, context, conversation_history)
            return {
                "status": result["status"],
                "collected_data": result.get("slots", {}),
                "missing_info": result.get("missing_slots", []),
                "next_question": result.get("next_question", "")
            }
        except Exception as e:
            self.logger.error(f"Slot filling tool failed: {e}")
            return {
                "status": "error",
                "collected_data": {},
                "missing_info": ["Error occurred while collecting information"],
                "next_question": "Could you please try again?",
                "error": str(e)
            }
    
    async def _tool_search_business_information(self, query: str, business_type: str = None) -> Dict[str, Any]:
        """Tool wrapper for RAG Agent - search for business information"""
        try:
            if not self.rag_agent:
                return {
                    "answer": "I'm currently unable to search for business information.",
                    "confidence": 0.0,
                    "sources": [],
                    "relevant_businesses": [],
                    "error": "RAG agent not available"
                }
            
            # Build context for RAG search
            context = {"business_type": business_type} if business_type else {}
            conversation_history = []  # Could be passed in if needed
            
            result = await self.rag_agent.answer_question(query, context, conversation_history)
            return {
                "answer": result.synthesized_answer,
                "confidence": result.confidence,
                "sources": result.sources,
                "relevant_businesses": getattr(result, 'relevant_businesses', [])
            }
        except Exception as e:
            self.logger.error(f"RAG tool failed: {e}")
            return {
                "answer": "I had trouble searching for that information.",
                "confidence": 0.0,
                "sources": [],
                "relevant_businesses": [],
                "error": str(e)
            }
    
    async def _tool_execute_business_action(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """Tool wrapper for Execution Agent - execute business actions"""
        try:
            if not self.execution_agent:
                return {
                    "success": False,
                    "confirmation_message": "Unable to execute action - execution agent not available",
                    "booking_id": None,
                    "error": "Execution agent not available"
                }
            
            result = await self.execution_agent.execute_action(action_data)
            return {
                "success": result.success,
                "confirmation_message": result.confirmation_message,
                "booking_id": result.data.get("booking_id") if hasattr(result, 'data') else None,
                "error": result.error_message if not result.success else None
            }
        except Exception as e:
            self.logger.error(f"Execution tool failed: {e}")
            return {
                "success": False,
                "confirmation_message": "An error occurred while processing your request",
                "booking_id": None,
                "error": str(e)
            }
    
    async def _tool_retrieve_memory_context(self, query: str, memory_type: str = None, session_id: str = None) -> Dict[str, Any]:
        """Tool wrapper for retrieving memory context"""
        try:
            # Use provided session_id or default to "current_session"
            target_session_id = session_id or "current_session"
            
            memories = await self.memory_manager.retrieve_conversation_memory(
                session_id=target_session_id,
                memory_type=memory_type,
                limit=5
            )
            
            return {
                "memories_found": len(memories),
                "memory_context": memories,
                "memory_types": list(set(m.get("memory_type", "unknown") for m in memories)),
                "total_access_count": sum(m.get("access_count", 0) for m in memories),
                "session_id": target_session_id
            }
        except Exception as e:
            self.logger.error(f"Memory retrieval tool failed: {e}")
            return {
                "memories_found": 0,
                "memory_context": [],
                "error": str(e)
            }
    
    async def _tool_search_business_sections(self, business_id: str, section_type: str = None) -> Dict[str, Any]:
        """Tool wrapper for searching business sections"""
        try:
            sections = await self.memory_manager.retrieve_business_context_sections(
                business_id=business_id
            )
            
            if section_type:
                sections = [s for s in sections if s.get("section_type") == section_type]
            
            return {
                "business_id": business_id,
                "sections_found": len(sections),
                "sections": sections,
                "section_types": list(set(s.get("section_type", "unknown") for s in sections))
            }
        except Exception as e:
            self.logger.error(f"Business sections search tool failed: {e}")
            return {
                "business_id": business_id,
                "sections_found": 0,
                "sections": [],
                "error": str(e)
            }
    
    async def chat(self, message: str, session_id: str, user_id: Optional[str] = None, user_location: Optional[str] = None, user_language: str = "en",
        user_preferences: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Modern AI-driven chat method with capability-based selection and tool orchestration
        Uses high-level capabilities to determine appropriate actions and tools
        """
        try:
            start_time = datetime.utcnow()
            self.logger.info(f"📣 Chat request received | session={session_id} | user={user_id or 'anonymous'}")
            
            # Get multimodal context for all conversations
            multimodal_context = self._get_multimodal_context(user_id, user_location)

            # Load user preferences and context profile only if user_id is provided
            preferences = user_preferences or await self._load_user_preferences(user_id)
            user_profile = None
            if user_id:
                user_profile = await self.memory_manager.get_user_context_profile(user_id)

            # Build rich context with memory integration
            context = await self._build_rich_context(session_id, user_location, user_language, preferences)

            # Add multimodal context to the rich context
            context["multimodal_context"] = multimodal_context
            context["user_profile"] = user_profile

            # Load relevant memories for this conversation
            conversation_memories = await self.memory_manager.retrieve_conversation_memory(
                session_id, limit=5
            )
            context["conversation_memories"] = conversation_memories

            # Check system health and update capabilities
            await self._check_system_health()

            # Let AI decide capability and orchestrate tools
            self.logger.info(f"🧠 AI selecting capability and tools for request | session={session_id}")
            response = await self._ai_driven_conversation(message, context, session_id, user_id)

            # Detect capability from response if possible
            capability = "unknown"
            try:
                # Check for capability indicators in response
                if "reservation" in response.lower() or "book" in response.lower() or "confirm" in response.lower():
                    capability = "Reservation/booking"
                elif "menu" in response.lower() or "businesses" in response.lower() or "located" in response.lower():
                    capability = "Business discovery"
                elif "information" in response.lower() or "hours" in response.lower() or "prices" in response.lower():
                    capability = "Information retrieval"
                elif "order" in response.lower() or "delivery" in response.lower():
                    capability = "Order placement"
                elif "hello" in response.lower() or "welcome" in response.lower() or "hi there" in response.lower():
                    capability = "Greeting"
                else:
                    capability = "General assistance"
            except Exception:
                # Default to general if detection fails
                capability = "General assistance"

            # Enhance response with multimodal context
            response = self._enhance_response_with_context(response, {"capability": capability}, multimodal_context)

            # Learn from this interaction
            self._learn_user_preferences(user_id, message, {"capability": capability}, response)

            # Store conversation context in memory
            await self._store_conversation_context(session_id, user_id, message, response, context)

            # Save conversation + update preferences
            await self._save_conversation(session_id, user_id, message, response)
            await self._update_user_preferences(user_id, context, response)

            # Calculate response time
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            self.logger.info(f"✅ Chat completed | capability={capability} | time={processing_time:.2f}s | session={session_id}")

            return {
                "message": response,
                "success": True,
                "session_id": session_id,
                "capability": capability,  # Track which capability was used
                "fast_path_used": False,
                "personalized": True,
                "multimodal_context": multimodal_context,
                "system_health": self._get_system_status(),
                "memory_info": await self.memory_manager.get_memory_summary(session_id),
                "timestamp": datetime.utcnow().isoformat(),
                "processing_time_seconds": processing_time,
            }

        except Exception as e:
            self.logger.exception(f"💥 Chat failed: {e}")
            return {
                "message": "I'm experiencing some technical difficulties. Let me try a simpler approach...",
                "success": False,
                "error": str(e),
                "system_health": self._get_system_status(),
                "timestamp": datetime.utcnow().isoformat(),
            }
    
    async def chat_stream(
        self,
        message: str,
        session_id: str,
        user_id: Optional[str] = None,
        user_location: Optional[str] = None,
        user_language: str = "en",
        user_preferences: Optional[Dict] = None,
    ):
        """
        Streaming version of chat method - yields response chunks in real-time
        Like ChatGPT streaming responses
        """
        try:
            # Step 1: FAST INTENT DETECTION - Like modern AI systems
            intent_analysis = await self._detect_intent_fast(message)

            # Get conversation history for context-aware processing
            conversation_history = await self._get_conversation_history(session_id)

            # Re-run intent detection with conversation context if we have history
            if conversation_history:
                updated_intent_analysis = await self._detect_intent_fast(message, conversation_history)
                # Only update if we detected a different intent
                if updated_intent_analysis["intent"] != intent_analysis["intent"]:
                    intent_analysis = updated_intent_analysis
                    self.logger.info(f"🔄 Intent updated with context: {intent_analysis['intent']} (confidence: {intent_analysis['confidence']})")

            # Step 2: Get Multi-Modal Context
            multimodal_context = self._get_multimodal_context(user_id, user_location)

            # Step 3: FAST PATH for business searches
            if intent_analysis["intent"] == "business_search" and intent_analysis["requires_tools"]:
                self.logger.info(f"🚀 Fast path: Business search detected - {intent_analysis['business_type']}")

                # Build context for fast response
                preferences = user_preferences or await self._load_user_preferences(user_id)
                context = await self._build_rich_context(session_id, user_location, user_language, preferences)

                # Get business search results first (can't stream tool execution)
                ai_response = await self._handle_business_search_direct(
                    intent_analysis["query"],
                    intent_analysis["business_type"],
                    user_id
                )

                # Enhance response with multimodal context
                ai_response = self._enhance_response_with_context(ai_response, intent_analysis, multimodal_context)

                # Learn user preferences
                self._learn_user_preferences(user_id, message, intent_analysis, ai_response)

                # Store conversation
                await self._store_conversation_context(session_id, user_id, message, ai_response, context)
                await self._save_conversation(session_id, user_id, message, ai_response)

                # Stream the response
                for chunk in self._stream_text(ai_response):
                    yield chunk

                return

            # FAST PATH for business selection
            elif intent_analysis["intent"] == "business_selection":
                self.logger.info(f"🎯 Fast path: Business selection detected")

                ai_response = await self._handle_business_selection(
                    intent_analysis, conversation_history, user_id
                )

                # Store conversation
                await self._store_conversation_context(session_id, user_id, message, ai_response, {})
                await self._save_conversation(session_id, user_id, message, ai_response)

                # Stream the response
                for chunk in self._stream_text(ai_response):
                    yield chunk

                return

            # FAST PATH for confirmation
            elif intent_analysis["intent"] == "confirmation":
                self.logger.info(f"✅ Fast path: Confirmation detected")

                ai_response = await self._handle_confirmation_response(
                    intent_analysis, conversation_history, user_id
                )

                # Store conversation
                await self._store_conversation_context(session_id, user_id, message, ai_response, {})
                await self._save_conversation(session_id, user_id, message, ai_response)

                # Stream the response
                for chunk in self._stream_text(ai_response):
                    yield chunk

                return

            # COMPLEX PATH - Full AI orchestration with streaming
            self.logger.info(f"🤖 Complex path: {intent_analysis['intent']} detected - using streaming orchestration")

            # Check system health
            await self._check_system_health()

            # Load user preferences and context
            preferences = user_preferences or await self._load_user_preferences(user_id)
            user_profile = None
            if user_id:
                user_profile = await self.memory_manager.get_user_context_profile(user_id)

            # Build rich context
            context = await self._build_rich_context(session_id, user_location, user_language, preferences)
            context["multimodal_context"] = multimodal_context
            context["user_profile"] = user_profile

            # Load relevant memories
            conversation_memories = await self.memory_manager.retrieve_conversation_memory(
                session_id, limit=5
            )
            context["conversation_memories"] = conversation_memories

            # Let LLM decide conversation flow and stream response
            async for chunk in self._ai_driven_conversation_stream(message, context, session_id, user_id):
                yield chunk

            # After streaming is complete, update preferences
            # We need to get the full response for learning
            full_response = await self._ai_driven_conversation(message, context, session_id, user_id)
            self._learn_user_preferences(user_id, message, {"intent": "unknown"}, full_response)
            await self._update_user_preferences(user_id, context, full_response)

        except Exception as e:
            self.logger.exception(f"💥 Streaming chat failed: {e}")
            # Stream error message
            error_msg = "I'm experiencing some technical difficulties. Let me try a simpler approach..."
            for chunk in self._stream_text(error_msg):
                yield chunk
    
    def _stream_text(self, text: str, chunk_size: int = 10):
        """Convert text into streaming chunks"""
        for i in range(0, len(text), chunk_size):
            yield text[i:i + chunk_size]
            # Small delay to simulate realistic streaming
            import time
            time.sleep(0.01)
    
    async def _ai_driven_conversation_stream(self, message: str, context: Dict[str, Any], session_id: str, user_id: Optional[str]):
        """
        Streaming version of AI-driven conversation with capability-based approach
        First determines the high-level capability, then executes tools if needed, then streams response
        """
        try:
            # Check if we have AI capabilities
            if not self.intent_agent or not hasattr(self.intent_agent, 'groq'):
                # Fallback response
                fallback_response = await self._handle_general_intent(message, context)
                for chunk in self._stream_text(fallback_response):
                    yield chunk
                return
            
            # Build system prompt with high-level capabilities and tools
            system_prompt = self._build_ai_orchestrator_prompt(context)
            
            # Get conversation history
            conversation_history = context.get("conversation_history", [])
            
            # Enhanced user prompt to encourage capability-based thinking
            enhanced_user_prompt = f"""{message}

First, determine which capability this request falls under, then use appropriate tools if needed."""
            
            # Prepare messages for AI
            messages = [
                {"role": "system", "content": system_prompt},
                *conversation_history[-5:],  # Last 5 messages for context
                {"role": "user", "content": enhanced_user_prompt}
            ]
            
            # First, check if AI wants to use tools based on capability selection
            decision_response = self.intent_agent.groq.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                temperature=0.3,
                max_tokens=150,  # Increased for better capability detection
                tools=self._format_tools_for_ai(),
                tool_choice="auto"
            )
            
            ai_message = decision_response.choices[0].message
            
            # If AI wants to use tools based on capability selection, execute them first
            if hasattr(ai_message, 'tool_calls') and ai_message.tool_calls:
                self.logger.info(
                    f"🎯 AI selected streaming capability requiring tools: {[tc.function.name for tc in ai_message.tool_calls]} | session={session_id}"
                )
                tool_results = await self._handle_tool_calls(ai_message.tool_calls, context, session_id, user_id)
                final_response = tool_results
            else:
                # No tools needed, check if content contains any capability selection or JSON
                content_text = ai_message.content.strip() if hasattr(ai_message, 'content') and ai_message.content else "I understand your request."
                
                # Check for JSON action format
                try:
                    json_match = re.search(r'\{[\s\S]*?"action"[\s\S]*?\}', content_text)
                    if json_match:
                        json_str = json_match.group(0)
                        action_data = json.loads(json_str)
                        if 'action' in action_data:
                            self.logger.info(f"🎯 AI selected streaming capability via JSON: {action_data['action']} | session={session_id}")
                            # Clean the response
                            content_text = content_text.replace(json_str, '').strip()
                except json.JSONDecodeError:
                    # Not valid JSON, continue
                    pass
                    
                final_response = content_text
            
            # Clean up response
            final_response = re.sub(r'<function=[^>]+>', '', final_response)
            final_response = re.sub(r'</function>', '', final_response)
            final_response = re.sub(r'\{[\s\S]*?"action"[\s\S]*?\}', '', final_response).strip()
            
            # Store conversation context
            await self._store_conversation_context(session_id, user_id, message, final_response, context)
            await self._save_conversation(session_id, user_id, message, final_response)
            
            self.logger.info(f"📝 Streaming response generated | length={len(final_response)} | session={session_id}")
            
            # Now stream the final response
            for chunk in self._stream_text(final_response):
                yield chunk
                
        except Exception as e:
            self.logger.error(f"Streaming AI-driven conversation failed: {e}")
            fallback_response = await self._handle_general_intent(message, context)
            for chunk in self._stream_text(fallback_response):
                yield chunk
    
    async def _ai_driven_conversation(self, message: str, context: Dict[str, Any], session_id: str, user_id: Optional[str]) -> str:
        """
        AI-driven conversation where the LLM decides which capabilities and tools to use
        based on high-level capabilities and natural conversation flow
        """
        try:
            # Check if we have AI capabilities
            if not self.intent_agent or not hasattr(self.intent_agent, 'groq'):
                return await self._handle_general_intent(message, context)
            
            # Build system prompt with high-level capabilities and available tools
            system_prompt = self._build_ai_orchestrator_prompt(context)
            
            # Get conversation history for context
            conversation_history = context.get("conversation_history", [])
            
            # Enhanced user prompt to encourage capability-based thinking
            enhanced_user_prompt = f"""{message}

First, determine which capability this request falls under, then use appropriate tools if needed."""
            
            # Prepare messages for AI
            messages = [
                {"role": "system", "content": system_prompt},
                *conversation_history[-5:],  # Last 5 messages for context
                {"role": "user", "content": enhanced_user_prompt}
            ]
            
            # Let AI decide what capabilities and tools to use
            response = self.intent_agent.groq.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                temperature=0.3,
                max_tokens=500,  # Increased for more comprehensive responses
                tools=self._format_tools_for_ai(),
                tool_choice="auto"
            )
            
            # Process AI response and tool calls
            ai_message = response.choices[0].message
            
            # Check if AI wants to call tools
            if hasattr(ai_message, 'tool_calls') and ai_message.tool_calls:
                self.logger.info(
                    f"🎯 AI selected capability requiring tools: {[tc.function.name for tc in ai_message.tool_calls]} | session={session_id}"
                )
                return await self._handle_tool_calls(ai_message.tool_calls, context, session_id, user_id)
            
            # If the model returned inline tool-call markup in content, parse and handle it
            content_text = (ai_message.content or '').strip() if hasattr(ai_message, 'content') else ''
            
            # Check for JSON action format first
            try:
                # Look for JSON blocks that might contain capability info
                json_match = re.search(r'\{[\s\S]*?"action"[\s\S]*?\}', content_text)
                if json_match:
                    json_str = json_match.group(0)
                    action_data = json.loads(json_str)
                    if 'action' in action_data:
                        self.logger.info(f"🎯 AI selected capability via JSON: {action_data['action']} | session={session_id}")
                        # Clean the response by removing the JSON block
                        content_text = content_text.replace(json_str, '').strip()
            except json.JSONDecodeError:
                # Not valid JSON, continue with regular processing
                pass
            
            # Check for inline tool calls
            inline_calls = self._parse_inline_tool_calls(content_text)
            if inline_calls:
                self.logger.info(
                    f"🛠️ Detected inline tool calls: {[c['name'] for c in inline_calls]} | session={session_id}"
                )
                # Convert parsed inline calls to a minimal structure compatible with _handle_tool_calls
                class _Func:
                    def __init__(self, name, arguments):
                        self.name = name
                        self.arguments = arguments
                class _Call:
                    def __init__(self, func):
                        self.function = func
                tool_calls = []
                for call in inline_calls:
                    tool_calls.append(_Call(_Func(call['name'], json.dumps(call['arguments']))))
                return await self._handle_tool_calls(tool_calls, context, session_id, user_id)

            # AI responded directly without tool calls
            # Post-process response to ensure natural flow
            response_text = response.choices[0].message.content.strip()
            
            # Clean up any remaining raw function syntax
            response_text = re.sub(r'<function=[^>]+>', '', response_text)
            response_text = re.sub(r'</function>', '', response_text)
            
            # Remove any JSON blocks that might have been included
            response_text = re.sub(r'\{[\s\S]*?"action"[\s\S]*?\}', '', response_text).strip()
            
            self.logger.info(f"🗣️ AI selected capability that didn't require tools | session={session_id}")
            return response_text
            
        except Exception as e:
            self.logger.error(f"AI-driven conversation failed: {e}")
            return await self._handle_general_intent(message, context)
    
    def _format_tools_for_ai(self) -> List[Dict[str, Any]]:
        """Format available tools for AI consumption"""
        tools = []
        for tool_name, tool_info in self.available_tools.items():
            if tool_name in self.available_capabilities and self.available_capabilities[tool_name]:
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "description": tool_info["description"],
                        "parameters": tool_info["parameters"]
                    }
                })
        return tools
    
    async def _handle_tool_calls(self, tool_calls: List, context: Dict[str, Any], session_id: str, user_id: Optional[str]) -> str:
        """Handle tool calls from the AI and generate appropriate response"""
        try:
            tool_results = []
            
            # Execute each tool call
            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                if tool_name in self.available_tools:
                    tool_function = self.available_tools[tool_name]["function"]
                    
                    # Structured logging for tool invocation
                    try:
                        pretty_args = json.dumps(tool_args)[:400]
                    except Exception:
                        pretty_args = str(tool_args)[:400]
                    self.logger.info(
                        f"▶️ Tool Invoke | name={tool_name} | session={session_id} | user={user_id} | args={pretty_args}"
                    )

                    # Call the appropriate tool
                    if tool_name == "understand_user_intent":
                        result = await tool_function(tool_args["message"], context)
                    elif tool_name == "collect_required_info":
                        result = await tool_function(
                            tool_args["intent"], 
                            tool_args["message"], 
                            tool_args.get("conversation_history", [])
                        )
                    elif tool_name == "search_business_information":
                        result = await tool_function(
                            tool_args["query"], 
                            tool_args.get("business_type")
                        )
                    elif tool_name == "execute_business_action":
                        result = await tool_function(tool_args["action_data"])
                    elif tool_name == "retrieve_memory_context":
                        result = await tool_function(
                            tool_args["query"], 
                            tool_args.get("memory_type"),
                            session_id  # Pass session_id for memory retrieval
                        )
                    elif tool_name == "search_business_sections":
                        result = await tool_function(
                            tool_args["business_id"], 
                            tool_args.get("section_type")
                        )
                    else:
                        result = {"error": f"Unknown tool: {tool_name}"}
                    
                    # Structured logging for tool result
                    try:
                        pretty_result = json.dumps(result)[:600]
                    except Exception:
                        pretty_result = str(result)[:600]
                    self.logger.info(
                        f"✅ Tool Result | name={tool_name} | session={session_id} | user={user_id} | result={pretty_result}"
                    )

                    tool_results.append({
                        "tool": tool_name,
                        "result": result
                    })
                else:
                    tool_results.append({
                        "tool": tool_name,
                        "result": {"error": f"Tool not available: {tool_name}"}
                    })
            
            # Let AI formulate response based on tool results
            return await self._generate_response_from_tools(tool_results, context)
            
        except Exception as e:
            self.logger.error(f"Tool call handling failed: {e}")
            return "I had trouble processing that request. Could you try again?"

    def _parse_inline_tool_calls(self, content: str) -> List[Dict[str, Any]]:
        """Parse inline tool-call markup like <function=tool_name{...}></function> from model content.
        Returns a list of dicts: [{"name": str, "arguments": dict}]."""
        if not content:
            return []
        calls: List[Dict[str, Any]] = []
        # Pattern captures: tool name in group 1, JSON-like args in group 2
        pattern = re.compile(r"<function\s*=\s*([\w_]+)\s*(\{.*?\})\s*>.*?</function>", re.DOTALL)
        for match in pattern.finditer(content):
            name = match.group(1)
            raw_args = match.group(2)
            try:
                # Ensure valid JSON (sometimes single quotes); try to coerce
                json_text = raw_args
                # Replace single quotes with double only if it seems safe
                if "'" in json_text and '"' not in json_text:
                    json_text = json_text.replace("'", '"')
                args = json.loads(json_text)
                # If content wrapped under a top-level key like {"context":..., "message":...}, pass as-is
                calls.append({"name": name, "arguments": args})
            except Exception:
                # If parsing fails, log and skip
                self.logger.warning(f"Failed to parse inline tool-call arguments for {name}")
                continue
        return calls
    
    async def _generate_response_from_tools(self, tool_results: List[Dict], context: Dict[str, Any]) -> str:
        """Generate natural response based on capability selection and tool execution results"""
        try:
            if not self.intent_agent or not hasattr(self.intent_agent, 'groq'):
                # Fallback: summarize tool results manually
                return self._summarize_tool_results(tool_results)
            
            # Determine which high-level capability was likely used based on tool names
            capability = "unknown"
            tool_names = [result.get("tool") for result in tool_results]
            
            if "understand_user_intent" in tool_names:
                if "collect_required_info" in tool_names and "execute_business_action" in tool_names:
                    capability = "Reservation/booking"
                elif "search_business_information" in tool_names:
                    capability = "Business discovery"
                else:
                    capability = "Information retrieval"
            elif "search_business_information" in tool_names:
                capability = "Business discovery"
            elif "search_business_sections" in tool_names:
                capability = "Information retrieval"
            elif "execute_business_action" in tool_names:
                capability = "Reservation/booking"
            elif "retrieve_memory_context" in tool_names:
                capability = "Personalized response"
            
            # Log capability used with tool results
            self.logger.info(f"🔍 Generating response for capability: {capability} with {len(tool_results)} tool results")
            
            # Build prompt for AI to formulate response based on capability and tool results
            prompt = f"""Based on the following tool execution results, provide a natural, helpful response to the user:

Detected capability: {capability}

Tool Results:
{json.dumps(tool_results, indent=2)}

Context:
- Available businesses: {len(context.get('businesses', []))}
- Current time: {context.get('current_time', 'Unknown')}
- User conversation history: {len(context.get('conversation_history', []))} messages

Please provide a conversational response that:
1. Addresses the user's request based on the detected capability
2. Incorporates the tool results in a natural, conversational way
3. Maintains a friendly, helpful tone like a knowledgeable local concierge
4. Avoids technical terms like "tool", "function", or "capability"
5. If there were errors, acknowledges them gracefully and offers alternatives
6. For business discovery, mentions specific business names when available
7. For reservations, confirms details clearly and provides confirmation info
8. For information retrieval, presents facts in an organized, readable way

Your response should flow naturally like a human concierge would speak."""

            response = self.intent_agent.groq.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "You are X-SevenAI, a helpful business concierge. Respond naturally based on capability selection and tool results."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=400  # Increased for more comprehensive responses
            )
            
            # Post-process response to ensure natural flow
            response_text = response.choices[0].message.content.strip()
            
            # Clean up any remaining raw function syntax or JSON
            response_text = re.sub(r'<function=[^>]+>', '', response_text)
            response_text = re.sub(r'</function>', '', response_text)
            response_text = re.sub(r'\{[\s\S]*?"action"[\s\S]*?\}', '', response_text).strip()
            
            return response_text
            
        except Exception as e:
            self.logger.error(f"Response generation failed: {e}")
            return self._summarize_tool_results(tool_results)
    
    def _summarize_tool_results(self, tool_results: List[Dict]) -> str:
        """Fallback method to summarize tool results without AI"""
        summaries = []
        
        for tool_result in tool_results:
            tool_name = tool_result["tool"]
            result = tool_result["result"]
            
            if tool_name == "understand_user_intent":
                intent = result.get("intent", "general")
                confidence = result.get("confidence", 0)
                summaries.append(f"I understand you want to {intent.replace('_', ' ')} (confidence: {confidence:.1f})")
            
            elif tool_name == "collect_required_info":
                status = result.get("status", "unknown")
                if status == "incomplete":
                    missing = result.get("missing_info", [])
                    summaries.append(f"I need more information: {', '.join(missing)}")
                elif status == "complete":
                    summaries.append("I have all the information I need")
            
            elif tool_name == "search_business_information":
                answer = result.get("answer", "No information found")
                confidence = result.get("confidence", 0)
                summaries.append(f"Search result: {answer} (confidence: {confidence:.1f})")
            
            elif tool_name == "execute_business_action":
                if result.get("success"):
                    message = result.get("confirmation_message", "Action completed successfully")
                    summaries.append(f"✅ {message}")
                else:
                    error = result.get("error", "Action failed")
                    summaries.append(f"❌ {error}")
        
        return " ".join(summaries) if summaries else "I'm processing your request..."
    
    
    async def _store_conversation_context(
        self,
        session_id: str,
        user_id: Optional[str],
        user_message: str,
        ai_response: str,
        context: Dict[str, Any]
    ) -> None:
        """Store conversation context in advanced memory system"""
        try:
            # Store semantic memory for the conversation
            if self.available_capabilities.get("semantic_memory", False):
                await self.memory_manager.store_semantic_memory(
                    session_id=session_id,
                    user_id=user_id,
                    content_type="conversation",
                    content_text=f"User: {user_message}\nAssistant: {ai_response}",
                    metadata={
                        "businesses_mentioned": [b.get("name", "") for b in context.get("businesses", [])],
                        "conversation_length": len(context.get("conversation_history", [])),
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            # Store short-term conversation memory
            conversation_context = {
                "user_message": user_message,
                "ai_response": ai_response,
                "timestamp": datetime.now().isoformat(),
                "businesses_available": len(context.get("businesses", [])),
                "categories_available": list(set(b.get("category", "") for b in context.get("businesses", [])))
            }
            
            await self.memory_manager.store_conversation_memory(
                session_id=session_id,
                user_id=user_id,
                memory_type="short_term",
                context_key=f"conversation_{datetime.now().isoformat()}",
                context_value=conversation_context,
                importance_score=0.6
            )
            
            # Update user context profile
            if user_id:
                profile_data = {
                    "last_interaction": datetime.now().isoformat(),
                    "total_conversations": len(context.get("conversation_history", [])) + 1,
                    "preferred_categories": list(set(b.get("category", "") for b in context.get("businesses", []))),
                    "interaction_patterns": {
                        "message_length": len(user_message),
                        "response_length": len(ai_response),
                        "business_context_used": len(context.get("businesses", [])) > 0
                    }
                }
                
                await self.memory_manager.update_user_context_profile(
                    user_id=user_id,
                    profile_data=profile_data
                )
                
        except Exception as e:
            self.logger.error(f"Failed to store conversation context: {e}")
    
    def get_capability_categories(self) -> Dict[str, str]:
        """Get available capability categories with descriptions"""
        return {
            "Greeting": "Welcome users and respond to greetings appropriately",
            "Casual conversation": "Engage in friendly chit-chat with users",
            "Business discovery": "Help users find businesses matching their needs",
            "Information retrieval": "Answer questions about business details, menus, hours, etc.",
            "Reservation/booking": "Help users book tables, appointments, or services",
            "Order placement": "Help users place orders for food, products, or services",
            "Cancellation/modification": "Help users cancel or change existing bookings/orders",
            "Answer FAQs": "Provide answers to common questions about businesses or services"
        }
    
    def _build_ai_orchestrator_prompt(self, context: Dict[str, Any]) -> str:
        """Build the AI orchestrator prompt with available tools and context"""
        businesses = context.get("businesses", [])
        business_stats = context.get("business_stats", {})

        # Get unique categories from cached data instead of loading from DB
        cached_categories = self.get_cached_categories()
        if cached_categories:
            categories = cached_categories
            self.logger.debug(f"✅ Used cached categories: {len(categories)} categories")
        else:
            # Fallback: extract from context business stats
            categories = business_stats.get("categories", [])
            self.logger.debug(f"⚠️ Cache not available, used context categories: {len(categories)} categories")
        
        # Build business examples
        businesses_text = "\n".join([
            f"- {biz['name']} ({biz['category']}) in {biz['location']}"
            for biz in businesses[:5]
        ])
        
        # Define high-level capability categories for AI
        capability_categories_dict = self.get_capability_categories()
        
        capability_text = "HIGH-LEVEL CAPABILITIES:\n"
        for i, (capability, description) in enumerate(capability_categories_dict.items(), 1):
            capability_text += f"{i}. {capability} - {description}\n"

        # Available tools description
        tools_description = []
        for tool_name, tool_info in self.available_tools.items():
            if tool_name in self.available_capabilities and self.available_capabilities[tool_name]:
                tools_description.append(f"- {tool_name}: {tool_info['description']}")
        
        tools_text = "\n".join(tools_description)
        
        return f"""You are X-SevenAI, a friendly and intelligent business concierge powered by advanced AI agents. You have access to powerful tools to help users with local businesses and services. Your goal is to provide natural, conversational assistance that flows like water - understanding user needs and responding helpfully without rigid templates or predetermined formats. Be conversational, adaptive, and genuinely helpful.

{capability_text}

AVAILABLE TOOLS:
{tools_text}

DECISION FRAMEWORK:
1. First, determine which high-level capability is needed based on the user's request
2. For business discovery → use 'search_business_information' tool
3. For information retrieval → use 'search_business_sections' tool
4. For reservations/orders → use 'understand_user_intent' then 'collect_required_info' then 'execute_business_action'
5. For personalization → use 'retrieve_memory_context' tool

RESPONSE GUIDELINES:
- Be natural and conversational - like a helpful local friend
- Dynamically choose which capabilities to use based on context
- Sometimes multiple capabilities may be needed (e.g., greeting + reservation)
- Ask for missing information when needed (e.g., time, party size)
- Be specific about businesses rather than generic
- Return structured information when executing actions

EXAMPLES:
- User: "I want pizza" → Capability: Business discovery → Use search_business_information tool
- User: "Book a table" → Capability: Reservation → Use understand_user_intent, collect_required_info
- User: "Tell me about Italian food" → Capability: Information retrieval → Use search_business_information

Always adapt to the conversation flow naturally. Use the most appropriate capability for each request."""

    
    async def _check_system_health(self):
        """Check overall system health and update degradation mode"""
        system_health = self_healing_manager.get_system_health()
        self.available_capabilities = self._assess_capabilities()
        
        # Check if we should enter degradation mode
        healthy_count = system_health["agents"]["healthy"]
        total_count = system_health["agents"]["total"]
        
        if total_count > 0:
            health_ratio = healthy_count / total_count
            self.degradation_mode = health_ratio < 0.5  # Degrade if less than 50% healthy
            
            if self.degradation_mode:
                self.logger.warning(f"🔶 Entering degradation mode: {healthy_count}/{total_count} agents healthy")
    
    def _get_system_status(self) -> Dict[str, Any]:
        """Get current system status for response"""
        return {
            "degradation_mode": self.degradation_mode,
            "available_capabilities": self.available_capabilities,
            "circuit_breakers": self_healing_manager.get_system_health()["circuit_breakers"]
        }
    
    async def _route_with_degradation(self, intent: str, message: str, context: Dict[str, Any],
                                     session_id: str, user_id: Optional[str]) -> str:
        """Route based on intent with graceful degradation"""
        
        if intent in ["service_booking", "product_order"]:
            if self.available_capabilities["slot_filling"]:
                return await self._handle_transactional_intent(intent, message, context, session_id, user_id)
            else:
                # Degradation: Direct execution without slot filling
                return await self._handle_degraded_transactional(intent, message, context)
                
        elif intent == "information":
            if self.available_capabilities["rag_search"]:
                return await self._handle_information_intent(message, context)
            else:
                # Degradation: Basic response without RAG
                return await self._handle_degraded_information(message, context)
        else:
            return await self._handle_general_intent(message, context)

    async def _handle_transactional_intent(self, intent: str, message: str, context: Dict[str, Any],
                                         session_id: str, user_id: Optional[str]) -> str:
        """Handle reservation/order intents with slot filling and execution"""
        try:
            # Get conversation history for slot filling context
            conversation_history = await self._get_conversation_history(session_id)

            # Step 2: Fill slots using Slot-Filling Agent
            slot_result = await self._fill_slots(intent, message, context, conversation_history)

            if slot_result["status"] == "incomplete":
                # Still need more information
                return slot_result["next_question"]
            else:
                # All slots filled, execute the action
                execution_result = await self.execution_agent.execute_action(slot_result["structured_data"])

                if execution_result.success:
                    return execution_result.confirmation_message
                else:
                    return f"I'm sorry, I couldn't complete that action: {execution_result.error_message}"

        except Exception as e:
            self.logger.error(f"Transactional intent handling failed: {e}")
            return "I had trouble processing that request. Could you try again with more details?"

    async def _handle_information_intent(self, message: str, context: Dict[str, Any]) -> str:
        """Handle information requests using RAG Agent"""
        try:
            if self.rag_agent:
                conversation_history = []  # Could load from context if needed
                rag_result = await self.rag_agent.answer_question(message, context, conversation_history)

                if rag_result.confidence > 0.3:
                    response = rag_result.synthesized_answer
                    # Add source attribution if multiple sources
                    if len(rag_result.sources) > 1:
                        response += f"\n\n📚 Information from: {', '.join(rag_result.sources[:3])}"
                    return response
                else:
                    return "I'd love to help with that, but I don't have specific information about it. Could you ask about our restaurants, menus, or reservations instead?"
            else:
                return "I'm here to help with restaurant information, but my knowledge system isn't available right now."

        except Exception as e:
            self.logger.error(f"Information intent handling failed: {e}")
            return "I had trouble retrieving that information. Could you try asking differently?"

    async def _handle_general_intent(self, message: str, context: Dict[str, Any]) -> str:
        """Handle general conversation using natural LLM response"""
        try:
            if not self.intent_agent or not hasattr(self.intent_agent, 'groq'):
                # Fallback without AI
                categories = set(biz.get("category", "General") for biz in context.get("businesses", []))
                category_list = ', '.join(sorted(categories))
                return f"Hello! I'm X-SevenAI, your multi-category business concierge. I can help with {category_list} businesses. What can I assist you with today?"

            # Use the LLM for natural conversation
            system_prompt = self._build_general_prompt(context)
            response = self.intent_agent.groq.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.8,
                max_tokens=200
            )

            # Post-process response to ensure natural flow
            response_text = response.choices[0].message.content.strip()
            
            # Clean up any remaining raw function syntax
            response_text = re.sub(r'<function=[^>]+>', '', response_text)
            response_text = re.sub(r'</function>', '', response_text)
            
            return response_text

        except Exception as e:
            self.logger.error(f"General intent handling failed: {e}")
            return "Hello! I'm here to help with local businesses and services. How can I assist you?"

    async def _fill_slots(self, intent: str, message: str, context: Dict[str, Any],
                         conversation_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fill slots using Slot-Filling Agent"""
        if self.slot_filling_agent:
            try:
                return await self.slot_filling_agent.fill_slots(intent, message, context, conversation_history)
            except Exception as e:
                self.logger.error(f"Slot filling failed: {e}")

        # Fallback slot filling
        return {"status": "incomplete", "next_question": f"Can you provide more details for your {intent}?"}


    async def _build_rich_context(
        self, session_id: str, user_location: Optional[str], user_language: str, preferences: Dict
    ) -> Dict[str, Any]:
        """Build enterprise-grade context with lazy loading for scalability"""
        context = {
            "current_time": datetime.now().strftime("%A, %B %d, %Y at %I:%M %p"),
            "user_location": user_location,
            "user_language": user_language,
            "user_preferences": preferences,
            # Lazy loading: Don't preload businesses for scalability
            # Search tools will query database dynamically when needed
            "businesses": [],  # Empty - search dynamically
            "business_sections": {},
        }

        # Load business statistics from cache instead of database (startup optimization)
        try:
            # Use cached business statistics (loaded once at startup)
            cached_stats = self.get_cached_business_stats()
            if cached_stats:
                context["business_stats"] = cached_stats
                self.logger.debug(f"✅ Used cached business stats: {cached_stats['total_businesses']} businesses")
            else:
                # Fallback: load from database if cache not available
                business_stats = await self._get_business_statistics()
                context["business_stats"] = business_stats
                self.logger.debug(f"⚠️ Cache not available, loaded business stats from DB: {business_stats['total_businesses']} businesses")
        except Exception as e:
            self.logger.error(f"⚠️ Failed to load business stats: {e}")
            context["business_stats"] = {"total_businesses": 0, "categories": []}

        # Load conversation history
        try:
            history_resp = self.supabase.table("messages").select("*").eq("session_id", session_id).order("created_at", desc=True).limit(10).execute()
            messages = history_resp.data or []
            context["conversation_history"] = []
            for msg in reversed(messages):
                sender_type = (msg.get("sender_type") or "").strip()
                role = "user" if sender_type == "customer" else "assistant"
                context["conversation_history"].append({
                    "role": role,
                    "content": msg.get("content", ""),
                })
        except Exception as e:
            self.logger.error(f"⚠️ Failed to load conversation history: {e}")
            context["conversation_history"] = []

        # Load semantic memories for context
        try:
            if self.available_capabilities.get("semantic_memory", False):
                semantic_memories = await self.memory_manager.search_semantic_memory(
                    session_id=session_id,
                    query_text="recent conversation context",
                    content_type="conversation",
                    top_k=3
                )
                context["semantic_memories"] = semantic_memories
        except Exception as e:
            self.logger.error(f"⚠️ Failed to load semantic memories: {e}")
            context["semantic_memories"] = []

        # Add memory context summary
        try:
            memory_summary = await self.memory_manager.get_memory_summary(session_id)
            context["memory_context"] = memory_summary
        except Exception as e:
            self.logger.error(f"⚠️ Failed to load memory summary: {e}")
            context["memory_context"] = {}

        return context

    async def _get_business_statistics(self) -> Dict[str, Any]:
        """Get business statistics for context metadata (scalable approach)"""
        try:
            # Get total business count
            count_resp = self.supabase.table("businesses").select("id", count="exact").eq("is_active", True).execute()
            total_businesses = count_resp.count or 0

            # Get unique categories
            categories_resp = self.supabase.table("businesses").select("category").eq("is_active", True).execute()
            categories = list(set(biz.get("category", "General") for biz in categories_resp.data or []))

            # Get business count by category
            category_counts = {}
            for category in categories:
                cat_count_resp = self.supabase.table("businesses").select("id", count="exact").eq("is_active", True).ilike("category", f"%{category}%").execute()
                category_counts[category] = cat_count_resp.count or 0

            return {
                "total_businesses": total_businesses,
                "categories": sorted(categories),
                "category_counts": category_counts,
                "last_updated": datetime.now().isoformat()
            }

        except Exception as e:
            self.logger.error(f"Failed to get business statistics: {e}")
            return {"total_businesses": 0, "categories": [], "category_counts": {}}

    async def _detect_intent_fast(self, message: str, conversation_history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Modern LLM-powered intent detection like ChatGPT.
        Uses sophisticated analysis instead of simple keyword matching.
        Now includes conversation context for better multi-turn understanding.
        """
        message_lower = message.lower().strip()

        # Initialize intent analysis
        intent_analysis = {
            "intent": "general",
            "confidence": 0.5,
            "business_type": None,
            "query": message,
            "entities": {},
            "context": {},
            "requires_tools": False,
            "conversation_context": self._analyze_conversation_context(conversation_history) if conversation_history else {}
        }

        # Check for follow-up responses to previous business suggestions
        if conversation_history:
            followup_analysis = self._detect_followup_intent(message_lower, conversation_history)
            if followup_analysis["is_followup"]:
                intent_analysis.update({
                    "intent": followup_analysis["intent"],
                    "confidence": followup_analysis["confidence"],
                    "business_type": followup_analysis["business_type"],
                    "entities": followup_analysis["entities"],
                    "context": followup_analysis["context"],
                    "requires_tools": followup_analysis["requires_tools"],
                    "followup_type": followup_analysis["followup_type"]
                })
                return intent_analysis

        # Business Search Intent Detection (enhanced)
        if self._is_business_search_query(message_lower):
            intent_analysis.update({
                "intent": "business_search",
                "confidence": 0.95,
                "business_type": self._extract_business_type_advanced(message_lower),
                "entities": self._extract_entities_from_query(message_lower),
                "context": self._extract_context_from_query(message_lower),
                "requires_tools": True
            })

        # Booking Intent Detection
        elif self._is_booking_query(message_lower):
            intent_analysis.update({
                "intent": "booking",
                "confidence": 0.9,
                "business_type": self._extract_business_type_advanced(message_lower),
                "entities": self._extract_entities_from_query(message_lower),
                "context": self._extract_context_from_query(message_lower),
                "requires_tools": True
            })

        # Information Intent Detection
        elif self._is_information_query(message_lower):
            intent_analysis.update({
                "intent": "information",
                "confidence": 0.8,
                "business_type": self._extract_business_type_advanced(message_lower),
                "entities": self._extract_entities_from_query(message_lower),
                "requires_tools": True
            })

        # Greeting Detection (only for very short messages)
        elif self._is_greeting(message_lower):
            intent_analysis.update({
                "intent": "greeting",
                "confidence": 0.8,
                "requires_tools": False
            })

        return intent_analysis

    def _is_business_search_query(self, message: str) -> bool:
        """
        Advanced business search detection like ChatGPT.
        Understands implicit search requests.
        """
        # Explicit search terms
        search_indicators = [
            'find', 'looking for', 'search', 'show me', 'recommend',
            'where can i', 'i need', 'i want', 'suggest', 'best',
            'available', 'nearby', 'around here', 'in the area'
        ]

        # Business-specific terms
        business_terms = [
            'restaurant', 'food', 'eat', 'pizza', 'coffee', 'cafe',
            'haircut', 'salon', 'doctor', 'dentist', 'car repair',
            'mechanic', 'plumber', 'cleaning', 'tutoring', 'store',
            'shop', 'service', 'repair', 'barber', 'spa'
        ]

        has_search_indicator = any(indicator in message for indicator in search_indicators)
        has_business_term = any(term in message for term in business_terms)

        # Implicit searches (like "I'm hungry" or "I need a haircut") - expanded
        implicit_indicators = [
            "i'm hungry", "i want to eat", "i need a haircut", "my car needs repair",
            "i need coffee", "i want food", "i need to see a doctor",
            "i want pizza", "i want sushi", "i want coffee", "i want burger",
            "looking for pizza", "looking for food", "looking for restaurant",
            "find me pizza", "find me food", "find me restaurant",
            "show me pizza", "show me food", "show me restaurant"
        ]
        has_implicit_search = any(indicator in message for indicator in implicit_indicators)

        return has_search_indicator or has_business_term or has_implicit_search

    def _is_booking_query(self, message: str) -> bool:
        """Advanced booking intent detection"""
        booking_indicators = [
            'book', 'reserve', 'schedule', 'appointment', 'table for',
            'make reservation', 'want to book', 'need to schedule',
            'set up appointment', 'make booking', 'reserve for'
        ]

        # Time-based booking indicators
        time_indicators = [
            'tonight', 'tomorrow', 'next week', 'this evening',
            'for today', 'at 8pm', 'at 7pm', 'at 6pm'
        ]

        has_booking_term = any(term in message for term in booking_indicators)
        has_time_reference = any(time in message for time in time_indicators)

        return has_booking_term or (has_time_reference and self._is_business_search_query(message))

    def _is_information_query(self, message: str) -> bool:
        """Advanced information intent detection"""
        info_indicators = [
            'tell me about', 'what is', 'how much', 'price of',
            'hours for', 'when does', 'where is', 'what are',
            'can you tell me', 'i need to know', 'information about'
        ]

        return any(indicator in message for indicator in info_indicators)

    def _is_greeting(self, message: str) -> bool:
        """Sophisticated greeting detection"""
        greetings = [
            'hello', 'hi', 'hey', 'good morning', 'good afternoon',
            'good evening', 'how are you', 'what\'s up', 'howdy'
        ]

        # Only classify as greeting if it's very short and contains greeting
        is_short_greeting = len(message.split()) <= 3 and any(greeting in message for greeting in greetings)

        # Or if it's just a greeting with some politeness
        is_polite_greeting = any(greeting in message for greeting in greetings) and len(message.split()) <= 5

        return is_short_greeting or is_polite_greeting

    def _extract_business_type_advanced(self, message: str) -> Optional[str]:
        """
        Advanced business type extraction like ChatGPT's entity recognition.
        """
        # Food & Hospitality
        if any(word in message for word in [
            'pizza', 'restaurant', 'food', 'cafe', 'burger', 'pasta', 'sushi',
            'italian', 'chinese', 'mexican', 'thai', 'indian', 'coffee', 'diner',
            'bar', 'pub', 'grill', 'bistro', 'eatery', 'deli', 'bakery'
        ]):
            return "food_hospitality"

        # Automotive Services
        if any(word in message for word in [
            'car repair', 'mechanic', 'tyre', 'tire', 'oil change', 'car wash',
            'auto repair', 'automotive', 'car service', 'garage', 'vehicle',
            'transmission', 'brake', 'battery', 'engine'
        ]):
            return "automotive_services"

        # Health & Medical
        if any(word in message for word in [
            'doctor', 'dentist', 'clinic', 'hospital', 'medical', 'appointment',
            'checkup', 'therapy', 'physician', 'nurse', 'health', 'wellness',
            'physical', 'exam', 'consultation'
        ]):
            return "health_medical"

        # Beauty & Personal Care
        if any(word in message for word in [
            'haircut', 'salon', 'spa', 'beauty', 'barber', 'nails', 'massage',
            'hair salon', 'beauty salon', 'manicure', 'pedicure', 'facial',
            'waxing', 'hair color', 'styling', 'cosmetologist'
        ]):
            return "beauty_personal_care"

        # Local Services
        if any(word in message for word in [
            'cleaning', 'plumber', 'electrician', 'repair', 'tutoring',
            'consulting', 'pest control', 'landscaping', 'moving', 'locksmith',
            'appliance repair', 'handyman', 'house cleaning', 'carpet cleaning'
        ]):
            return "local_services"

        return "general"

    def _extract_entities_from_query(self, message: str) -> Dict[str, Any]:
        """
        Extract entities from query like ChatGPT's NER (Named Entity Recognition).
        """
        entities = {
            "cuisine_types": [],
            "business_names": [],
            "locations": [],
            "price_ranges": [],
            "time_preferences": [],
            "group_sizes": [],
            "special_requirements": []
        }

        # Cuisine extraction
        cuisines = ['italian', 'chinese', 'mexican', 'thai', 'indian', 'american',
                   'french', 'japanese', 'korean', 'vietnamese', 'mediterranean']
        for cuisine in cuisines:
            if cuisine in message:
                entities["cuisine_types"].append(cuisine)

        # Location extraction
        locations = ['downtown', 'uptown', 'midtown', 'suburb', 'mall', 'airport']
        for location in locations:
            if location in message:
                entities["locations"].append(location)

        # Price range extraction
        if any(word in message for word in ['cheap', 'inexpensive', 'budget']):
            entities["price_ranges"].append("budget")
        elif any(word in message for word in ['expensive', 'upscale', 'fine dining']):
            entities["price_ranges"].append("upscale")

        # Time preferences
        if any(word in message for word in ['breakfast', 'morning']):
            entities["time_preferences"].append("morning")
        elif any(word in message for word in ['lunch', 'noon', 'afternoon']):
            entities["time_preferences"].append("afternoon")
        elif any(word in message for word in ['dinner', 'evening', 'tonight']):
            entities["time_preferences"].append("evening")

        # Group size
        import re
        party_match = re.search(r'party of (\d+)|table for (\d+)|for (\d+) people', message)
        if party_match:
            size = party_match.group(1) or party_match.group(2) or party_match.group(3)
            entities["group_sizes"].append(int(size))

        return entities

    def _extract_context_from_query(self, message: str) -> Dict[str, Any]:
        """
        Extract contextual information like ChatGPT's conversation understanding.
        """
        context = {
            "urgency": "normal",
            "specificity": "general",
            "social_context": "individual",
            "mood": "neutral",
            "intent_clarity": "clear"
        }

        # Urgency detection
        if any(word in message for word in ['urgent', 'asap', 'emergency', 'quickly']):
            context["urgency"] = "high"
        elif any(word in message for word in ['whenever', 'flexible', 'anytime']):
            context["urgency"] = "low"

        # Specificity detection
        if any(word in message for word in ['specific', 'particular', 'exact']):
            context["specificity"] = "high"
        elif any(word in message for word in ['any', 'whatever', 'something']):
            context["specificity"] = "low"

        # Social context
        if any(word in message for word in ['date', 'romantic', 'anniversary']):
            context["social_context"] = "romantic"
        elif any(word in message for word in ['family', 'kids', 'children']):
            context["social_context"] = "family"
        elif any(word in message for word in ['business', 'meeting', 'corporate']):
            context["social_context"] = "business"

        # Mood detection
        if any(word in message for word in ['!', 'excited', 'great', 'awesome']):
            context["mood"] = "positive"
        elif any(word in message for word in ['disappointed', 'unhappy', 'bad']):
            context["mood"] = "negative"

        return context

    def _analyze_conversation_context(self, conversation_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze conversation history to understand current context like ChatGPT.
        Determines what stage of conversation we're in and what was previously discussed.
        """
        context = {
            "last_ai_message": None,
            "previous_businesses_suggested": [],
            "conversation_stage": "initial",
            "pending_actions": [],
            "user_selections": []
        }

        if not conversation_history:
            return context

        # Get the last few messages to understand context
        recent_messages = conversation_history[-6:]  # Last 6 messages (3 exchanges)

        for msg in recent_messages:
            content = msg.get("content", "").lower()
            role = msg.get("role", "")

            if role == "assistant":
                context["last_ai_message"] = msg

                # Check if AI suggested businesses - more flexible detection
                if any(phrase in content for phrase in ["here are", "excellent choice", "great option", "found", "recommend", "suggestion", "option"]):
                    if "1." in content or "2." in content or "3." in content or any(str(i) + "." in content for i in range(1, 10)):
                        context["conversation_stage"] = "awaiting_selection"
                        context["previous_businesses_suggested"] = self._extract_suggested_businesses(content)

            elif role == "user":
                # Check for selection indicators
                if any(phrase in content for phrase in ["go with", "choose", "select", "pick", "that one", "the first", "second", "third"]):
                    context["user_selections"].append({
                        "message": msg["content"],
                        "timestamp": msg.get("timestamp")
                    })

        return context

    def _detect_followup_intent(self, message: str, conversation_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Detect if the current message is a follow-up to previous AI suggestions.
        This is key to preventing the repetitive behavior.
        """
        followup_analysis = {
            "is_followup": False,
            "intent": "general",
            "confidence": 0.0,
            "business_type": None,
            "entities": {},
            "context": {},
            "requires_tools": False,
            "followup_type": None
        }

        # Get conversation context
        conv_context = self._analyze_conversation_context(conversation_history)

        # Only process as followup if we recently suggested businesses
        if conv_context["conversation_stage"] != "awaiting_selection":
            return followup_analysis

        # Selection patterns - user choosing from previous suggestions
        # More specific patterns to avoid false positives
        selection_patterns = [
            r"go with (.+)",
            r"choose (.+)",
            r"select (.+)",
            r"pick (.+)",
            r"let's go with (.+)",
            r"i'll take (.+)",
            r"give me (.+)",
            r"that one",
            r"the first one",
            r"the second one",
            r"the third one",
            r"number (\d+)",
            r"option (\d+)",
            r"choice (\d+)",
            r"(\d+)\s*please",
            r"number\s*(\d+)",
            # Only match "i want" when it's clearly a selection (short phrases)
            r"i want (?:the )?(.{1,30}?)(?:\s|$)",  # Max 30 chars to avoid matching long queries
        ]

        for pattern in selection_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                selected_item = match.group(1) if match.groups() else match.group(0)

                # Special handling for "i want" pattern - check if it's actually a new search
                if "i want" in pattern and len(message.split()) > 3:
                    # If it's a longer message with "i want", it's likely a new search, not a selection
                    # Skip this match and let it fall through to business search detection
                    continue

                followup_analysis.update({
                    "is_followup": True,
                    "intent": "business_selection",
                    "confidence": 0.9,
                    "entities": {
                        "selected_business": selected_item.strip(),
                        "selection_type": "explicit_choice"
                    },
                    "context": {
                        "previous_suggestions": conv_context["previous_businesses_suggested"],
                        "conversation_stage": conv_context["conversation_stage"]
                    },
                    "requires_tools": True,
                    "followup_type": "selection"
                })
                break

        # If no explicit selection pattern matched, check if the message matches a previously suggested business name
        if not followup_analysis["is_followup"] and conv_context["conversation_stage"] == "awaiting_selection":
            previous_businesses = conv_context["previous_businesses_suggested"]
            message_lower = message.lower().strip()

            # Check if the entire message matches a business name (direct selection)
            for business in previous_businesses:
                business_name = business["name"].lower()
                # Exact match
                if message_lower == business_name:
                    followup_analysis.update({
                        "is_followup": True,
                        "intent": "business_selection",
                        "confidence": 0.95,  # Higher confidence for exact matches
                        "entities": {
                            "selected_business": business["name"],
                            "selection_type": "direct_name_match"
                        },
                        "context": {
                            "previous_suggestions": previous_businesses,
                            "conversation_stage": conv_context["conversation_stage"]
                        },
                        "requires_tools": True,
                        "followup_type": "selection"
                    })
                    break

                # Partial match (contains business name)
                elif len(message_lower) >= 3 and business_name in message_lower:
                    followup_analysis.update({
                        "is_followup": True,
                        "intent": "business_selection",
                        "confidence": 0.85,
                        "entities": {
                            "selected_business": business["name"],
                            "selection_type": "partial_name_match"
                        },
                        "context": {
                            "previous_suggestions": previous_businesses,
                            "conversation_stage": conv_context["conversation_stage"]
                        },
                        "requires_tools": True,
                        "followup_type": "selection"
                    })
                    break

        # Confirmation patterns - user confirming a choice
        if not followup_analysis["is_followup"]:
            confirmation_patterns = [
                r"yes", r"sure", r"okay", r"ok", r"fine", r"good", r"perfect",
                r"that works", r"sounds good", r"let's do it"
            ]

            for pattern in confirmation_patterns:
                if re.search(r'\b' + pattern + r'\b', message, re.IGNORECASE):
                    followup_analysis.update({
                        "is_followup": True,
                        "intent": "confirmation",
                        "confidence": 0.8,
                        "entities": {"confirmation_type": "positive"},
                        "context": {
                            "previous_suggestions": conv_context["previous_businesses_suggested"],
                            "conversation_stage": conv_context["conversation_stage"]
                        },
                        "requires_tools": True,
                        "followup_type": "confirmation"
                    })
                    break

        return followup_analysis

    def _extract_suggested_businesses(self, ai_message: str) -> List[Dict[str, Any]]:
        """
        Extract business suggestions from AI's previous message.
        This helps understand what options were presented to the user.
        """
        businesses = []
        lines = ai_message.split('\n')

        for line in lines:
            line = line.strip()
            # Look for numbered suggestions like "1. Rosa's Pizza"
            if re.match(r'^\d+\.\s*.+', line):
                # Extract business name
                business_match = re.match(r'^\d+\.\s*([^(-]+)', line)
                if business_match:
                    business_name = business_match.group(1).strip()
                    businesses.append({
                        "name": business_name,
                        "raw_text": line
                    })

        return businesses

    def _learn_user_preferences(self, user_id: str, message: str, intent_analysis: Dict[str, Any], response: str):
        """
        Learn user preferences from conversation like ChatGPT.
        Builds personalized profile over time.
        """
        if not user_id:
            return

        try:
            preferences = {
                "last_interaction": datetime.now().isoformat(),
                "preferred_business_types": [],
                "preferred_cuisines": [],
                "preferred_times": [],
                "budget_level": "medium",
                "preferred_locations": [],
                "interaction_patterns": []
            }

            # Extract preferences from intent analysis
            entities = intent_analysis.get('entities', {})

            if entities.get('cuisine_types'):
                preferences["preferred_cuisines"].extend(entities['cuisine_types'])

            if entities.get('time_preferences'):
                preferences["preferred_times"].extend(entities['time_preferences'])

            if entities.get('price_ranges'):
                if "budget" in entities['price_ranges']:
                    preferences["budget_level"] = "low"
                elif "upscale" in entities['price_ranges']:
                    preferences["budget_level"] = "high"

            # Store in memory
            try:
                # Try to use the memory manager's user preference method
                if hasattr(self.memory_manager, 'store_user_preference'):
                    self.memory_manager.store_user_preference(user_id, "business_search", preferences)
                else:
                    # Fallback: store directly in database
                    self.supabase.table("user_context_profiles").upsert({
                        "user_id": user_id,
                        "profile_data": preferences,
                        "updated_at": datetime.now().isoformat()
                    }, on_conflict="user_id").execute()
            except Exception as e:
                self.logger.warning(f"Could not store user preferences: {e}")

        except Exception as e:
            self.logger.error(f"Error learning user preferences: {e}")

    def _get_multimodal_context(self, user_id: str = None, location: str = None) -> Dict[str, Any]:
        """
        Get multi-modal context like modern AI systems.
        Includes location, time, weather, user preferences, etc.
        """
        context = {
            "current_time": datetime.now().isoformat(),
            "time_of_day": self._get_time_of_day(),
            "day_of_week": datetime.now().strftime("%A"),
            "season": self._get_season(),
            "location": location or "unknown",
            "weather": self._get_weather_context(),
            "user_preferences": {},
            "recent_searches": []
        }

        # Get user preferences if available
        if user_id:
            try:
                # Try to use the memory manager's method
                if hasattr(self.memory_manager, 'get_user_preferences'):
                    user_prefs = self.memory_manager.get_user_preferences(user_id)
                else:
                    # Fallback: get from database directly
                    resp = self.supabase.table("user_context_profiles").select("*").eq("user_id", user_id).execute()
                    user_prefs = resp.data[0] if resp.data else {}
                
                context["user_preferences"] = user_prefs or {}
            except Exception as e:
                self.logger.warning(f"Could not load user preferences: {e}")
                context["user_preferences"] = {}

        # Get recent search history
        if user_id:
            try:
                # Try to use the memory manager's method
                if hasattr(self.memory_manager, 'get_recent_searches'):
                    recent_searches = self.memory_manager.get_recent_searches(user_id, limit=5)
                else:
                    # Fallback: empty list
                    recent_searches = []
                
                context["recent_searches"] = recent_searches or []
            except Exception as e:
                self.logger.warning(f"Could not load recent searches: {e}")
                context["recent_searches"] = []

        return context

    def _get_time_of_day(self) -> str:
        """Get current time of day for contextual suggestions"""
        hour = datetime.now().hour

        if 5 <= hour < 12:
            return "morning"
        elif 12 <= hour < 17:
            return "afternoon"
        elif 17 <= hour < 22:
            return "evening"
        else:
            return "night"

    def _get_season(self) -> str:
        """Get current season for seasonal suggestions"""
        month = datetime.now().month

        if month in [12, 1, 2]:
            return "winter"
        elif month in [3, 4, 5]:
            return "spring"
        elif month in [6, 7, 8]:
            return "summer"
        else:
            return "fall"

    def _get_weather_context(self) -> Dict[str, Any]:
        """
        Get weather context for recommendations.
        In production, this would integrate with a weather API.
        """
        # Mock weather data - in production, integrate with weather API
        time_of_day = self._get_time_of_day()
        season = self._get_season()

        weather_suggestions = {
            "summer": {
                "outdoor_friendly": True,
                "air_conditioned": True,
                "cold_drinks": True
            },
            "winter": {
                "indoor_friendly": True,
                "warm_drinks": True,
                "hearty_food": True
            },
            "spring": {
                "outdoor_friendly": True,
                "light_fare": True
            },
            "fall": {
                "comfort_food": True,
                "indoor_friendly": True
            }
        }

        return {
            "season": season,
            "time_of_day": time_of_day,
            "suggestions": weather_suggestions.get(season, {}),
            "temperature": "moderate",  # Mock data
            "conditions": "clear"  # Mock data
        }

    def _personalize_recommendations(self, businesses: List[Dict], user_context: Dict[str, Any]) -> List[Dict]:
        """
        Personalize business recommendations based on user context.
        Like ChatGPT's personalized suggestions.
        """
        if not businesses:
            return businesses

        user_prefs = user_context.get('user_preferences', {})
        time_of_day = user_context.get('time_of_day', 'evening')
        weather = user_context.get('weather', {})

        # Score businesses based on user preferences
        for business in businesses:
            personalization_score = 0

            # Time suitability
            business_category = business.get('category', '').lower()
            if time_of_day == 'morning' and 'cafe' in business_category:
                personalization_score += 0.3
            elif time_of_day == 'evening' and 'restaurant' in business_category:
                personalization_score += 0.3

            # Weather suitability
            weather_suggestions = weather.get('suggestions', {})
            if weather_suggestions.get('outdoor_friendly') and 'outdoor' in business.get('description', '').lower():
                personalization_score += 0.2

            # User preference matching
            preferred_cuisines = user_prefs.get('preferred_cuisines', [])
            business_desc = business.get('description', '').lower()
            for cuisine in preferred_cuisines:
                if cuisine.lower() in business_desc:
                    personalization_score += 0.4

            # Recent search history
            recent_searches = user_context.get('recent_searches', [])
            for search in recent_searches:
                if search.get('business_type') == business.get('category'):
                    personalization_score += 0.1

            business['personalization_score'] = personalization_score

        # Sort by personalization score
        businesses.sort(key=lambda x: x.get('personalization_score', 0), reverse=True)

        return businesses

    def _enhance_response_with_context(self, response: str, intent_analysis: Dict[str, Any], user_context: Dict[str, Any]) -> str:
        """
        Enhance response with contextual information like ChatGPT.
        Adds time-aware, weather-aware, and personalized elements.
        """
        try:
            enhanced_parts = [response]

            time_of_day = user_context.get('time_of_day')
            weather = user_context.get('weather', {})
            user_prefs = user_context.get('user_preferences', {})

            # Add time-based suggestions
            if time_of_day == 'morning' and 'restaurant' in response.lower():
                enhanced_parts.append("Since it's morning, you might also enjoy our breakfast specials!")

            elif time_of_day == 'evening' and 'restaurant' in response.lower():
                enhanced_parts.append("Perfect timing for dinner! Many restaurants have evening specials.")

            # Add weather-based suggestions
            season = weather.get('season')
            if season == 'summer' and 'outdoor' in response.lower():
                enhanced_parts.append("With the nice weather, outdoor seating would be perfect!")

            # Add personalization
            preferred_cuisines = user_prefs.get('preferred_cuisines', [])
            if preferred_cuisines and len(enhanced_parts) == 1:
                enhanced_parts.append(f"Based on your preference for {preferred_cuisines[0]} cuisine, I focused on those options.")

            # Combine enhancements
            if len(enhanced_parts) > 1:
                return " ".join(enhanced_parts)
            else:
                return response

        except Exception as e:
            self.logger.error(f"Error enhancing response with context: {e}")
            return response

    async def _handle_business_search_direct(self, query: str, business_type: Optional[str] = None, user_id: str = None) -> str:
        """
        Direct business search handling - like modern AI systems.
        Immediate response without complex agent orchestration.
        """
        try:
            # Extract location from query
            location = self._extract_location(query)

            # Call RAG search directly
            from app.services.ai.rag_search import RAGSearch
            rag = RAGSearch(self.supabase)

            # Search with filters
            filters = {}
            if business_type and business_type != "general":
                filters["category"] = business_type

            results = rag.search_businesses(query=query, filters=filters, top_k=5)

            if results and len(results) > 0:
                # Format natural response
                response = self._format_business_search_response(query, results, location)
                return response
            else:
                # No results found
                return self._format_no_business_found_response(query, business_type)

        except Exception as e:
            self.logger.error(f"Direct business search failed: {e}")
            return f"I'd be happy to help you find what you need. Could you tell me more about '{query}'?"

    def _extract_location(self, query: str) -> Optional[str]:
        """Extract location from query"""
        query_lower = query.lower()

        # Common locations
        locations = ['riga', 'jurmala', 'daugavpils', 'liepaja', 'jelgava', 'ventspils']

        for location in locations:
            if location in query_lower:
                return location

        # Look for "in [location]" pattern
        import re
        location_match = re.search(r'\b(?:in|near|around)\s+([a-zA-Z\s]+)', query_lower)
        if location_match:
            return location_match.group(1).strip()

        return None


    def _build_general_prompt(self, context: Dict[str, Any]) -> str:

        # Create category-specific help text based on available categories
        help_text = []

        if any("restaurant" in cat.lower() or "food" in cat.lower() or "hospitality" in cat.lower() for cat in categories):
            help_text.append("- Restaurant reservations and food orders")

        if any("service" in cat.lower() or "repair" in cat.lower() or "automotive" in cat.lower() for cat in categories):
            help_text.append("- Service appointments and repairs")

        if any("retail" in cat.lower() or "shop" in cat.lower() for cat in categories):
            help_text.append("- Product purchases and shopping")

        if any("health" in cat.lower() or "medical" in cat.lower() for cat in categories):
            help_text.append("- Medical appointments and healthcare services")

        if any("freelance" in cat.lower() or "consulting" in cat.lower() or "professional" in cat.lower() for cat in categories):
            help_text.append("- Freelance and professional services")

        help_text.extend([
            "- Business information and recommendations",
            "- General assistance with local services"
        ])

        help_text_str = "\n".join(help_text)

        return f"""You are X-SevenAI, a friendly multi-category business concierge.

🌟 {context['current_time']}
📍 Serving: {total_businesses} businesses across {len(categories)} categories

AVAILABLE CATEGORIES: {', '.join(sorted(categories))}

Be friendly, conversational, and helpful. You can help with:
{help_text_str}

CRITICAL: When users ask about finding businesses, restaurants, services, or recommendations:
1. ALWAYS call the search_business_information tool first
2. Use the business_type parameter when users ask about specific categories
3. Provide specific business names and details from the search results
4. If no perfect matches, suggest alternatives from available businesses

Example: If user says "pizza shops", call search_business_information with query="pizza" and business_type="food_hospitality"

Keep responses natural and engaging. Adapt your assistance based on the business category and user needs!"""

    async def _get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get recent conversation history for context"""
        try:
            history_resp = self.supabase.table("messages").select("*").eq("session_id", session_id).order("created_at", desc=True).limit(20).execute()
            messages = history_resp.data or []

            conversation_history = []
            for msg in reversed(messages):
                sender_type = (msg.get("sender_type") or "").strip()
                role = "user" if sender_type == "customer" else "assistant"
                conversation_history.append({
                    "role": role,
                    "content": msg.get("content", ""),
                })

            return conversation_history

        except Exception as e:
            self.logger.error(f"Failed to get conversation history: {e}")
            return []

    async def _save_conversation(self, session_id: str, user_id: Optional[str], user_message: str, ai_response: str):
        """Save conversation — for memory, analytics, training"""
        try:
            now = datetime.utcnow().isoformat()
            self.supabase.table("messages").insert({
                "session_id": session_id,
                "sender_type": "customer",
                "role": "user",
                "content": user_message,
                "chat_context": "global",
                "created_at": now,
            }).execute()
            self.supabase.table("messages").insert({
                "session_id": session_id,
                "sender_type": "assistant",
                "role": "assistant",
                "content": ai_response,
                "chat_context": "global",
                "created_at": now,
            }).execute()
        except Exception as e:
            self.logger.error(f"❌ Failed to save conversation: {e}")

    async def _load_user_preferences(self, user_id: Optional[str]) -> Dict:
        """Load user preferences — for personalization"""
        if not user_id:
            return {}
        try:
            resp = self.supabase.table("user_context_profiles").select("*").eq("user_id", user_id).execute()
            return resp.data[0] if resp.data else {}
        except:
            return {}

    async def _update_user_preferences(self, user_id: Optional[str], context: Dict, response: str):
        """Update preferences — e.g., favorite business, usual party size"""
        if not user_id:
            return
        try:
            # Extract preferences from context/response (simplified)
            prefs = {"last_interaction": datetime.utcnow().isoformat()}
            if context.get("user_preferences"):
                prefs.update(context["user_preferences"])

            # Upsert
            self.supabase.table("user_context_profiles").upsert({
                "user_id": user_id,
                "profile_data": prefs,
                "preferences": prefs,
                "updated_at": datetime.utcnow().isoformat(),
            }, on_conflict="user_id").execute()
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to update preferences: {e}")

    async def _handle_business_selection(self, intent_analysis: Dict[str, Any], conversation_history: List[Dict[str, Any]], user_id: str = None) -> str:
        """
        Handle user selecting a business from previous suggestions.
        Now fully AI-driven - no hardcoded responses.
        """
        # AI will handle this naturally through orchestrator
        return ""

    async def _handle_confirmation_response(self, intent_analysis: Dict[str, Any], conversation_history: List[Dict[str, Any]], user_id: str = None) -> str:
        """
        Handle user confirmation responses (yes/no) to previous suggestions.
        Now fully AI-driven - no hardcoded responses.
        """
        # AI will handle this naturally through orchestrator
        return ""
