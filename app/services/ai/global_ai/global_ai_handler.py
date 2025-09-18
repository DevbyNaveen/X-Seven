"""
Modern Global AI Handler - Agent-Orchestrated Architecture with Self-Healing
Orchestrates specialized agents for intent detection, slot filling, RAG, and execution with automatic recovery
"""
from __future__ import annotations
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from .intent_agent import IntentAgent, IntentResult
from .slot_filling_agent import SlotFillingAgent
from .rag_agent import RAGAgent, RAGResult
from .execution_agent import ExecutionAgent, ExecutionResult
from .self_healing import self_healing_manager, HealthStatus

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

    def __init__(self, supabase, groq_api_key: str | None = None, webhook_url: Optional[str] = None):
        self.supabase = supabase
        self.webhook_url = webhook_url
        self.logger = logging.getLogger(__name__)

        # Initialize specialized agents with self-healing
        self.intent_agent = None
        self.slot_filling_agent = None
        self.rag_agent = None
        self.execution_agent = ExecutionAgent(supabase, webhook_url)

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
        
        # Graceful degradation state
        self.degradation_mode = False
        self.available_capabilities = self._assess_capabilities()
    
    def _assess_capabilities(self) -> Dict[str, bool]:
        """Assess what capabilities are currently available"""
        return {
            "intent_detection": self.intent_agent is not None,
            "slot_filling": self.slot_filling_agent is not None,
            "rag_search": self.rag_agent is not None,
            "execution": True,  # Execution agent always available
            "groq_available": self.intent_agent is not None
        }
    
    async def chat(
        self,
        message: str,
        session_id: str,
        user_id: Optional[str] = None,
        user_location: Optional[str] = None,
        user_language: str = "en",
        user_preferences: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Main chat entrypoint — modern agent-orchestrated flow with self-healing
        """
        try:
            # Check system health and update capabilities
            await self._check_system_health()
            
            # Load or initialize user preferences
            preferences = user_preferences or await self._load_user_preferences(user_id)

            # Build rich context — everything agents need to be brilliant
            context = await self._build_rich_context(session_id, user_location, user_language, preferences)

            # Step 1: Intent Detection with self-healing
            intent_result = await self._detect_intent_with_fallback(message, context)

            # Step 2: Route based on intent with graceful degradation
            response = await self._route_with_degradation(intent_result.intent, message, context, session_id, user_id)

            # Save conversation + update preferences
            await self._save_conversation(session_id, user_id, message, response)
            await self._update_user_preferences(user_id, context, response)

            return {
                "message": response,
                "success": True,
                "session_id": session_id,
                "intent": intent_result.intent,
                "system_health": self._get_system_status(),
                "timestamp": datetime.utcnow().isoformat(),
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
    
    async def _detect_intent_with_fallback(self, message: str, context: Dict[str, Any]) -> IntentResult:
        """Intent detection with multiple fallback levels"""
        # Primary: AI-powered intent detection
        if self.available_capabilities["intent_detection"]:
            try:
                return await self.intent_agent.detect_intent(message, context)
            except Exception as e:
                self.logger.error(f"Intent agent failed: {e}")
        
        # Secondary: Keyword-based detection
        self.logger.info("🔄 Using keyword-based intent detection")
        message_lower = message.lower().strip()
        
        if any(word in message_lower for word in ["book", "reserve", "appointment", "schedule", "booking"]):
            return IntentResult("service_booking", 0.7, {}, "Keyword fallback: service booking")
        elif any(word in message_lower for word in ["order", "buy", "purchase", "get", "want", "need"]):
            return IntentResult("product_order", 0.7, {}, "Keyword fallback: product order")
        elif any(word in message_lower for word in ["what", "when", "where", "how", "tell me about", "information"]):
            return IntentResult("information", 0.6, {}, "Keyword fallback: information")
        else:
            return IntentResult("general", 0.5, {}, "Keyword fallback: general")
    
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
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.8,
                max_tokens=200
            )

            return response.choices[0].message.content.strip()

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

    # Graceful Degradation Methods
    async def _handle_degraded_transactional(self, intent: str, message: str, context: Dict[str, Any]) -> str:
        """Handle transactional intents when slot filling is unavailable - category-agnostic"""
        try:
            # Extract basic information from message using simple parsing
            basic_info = self._extract_basic_info(message)
            
            if intent == "service_booking":
                return await self._create_simple_booking(basic_info, context)
            elif intent == "product_order":
                return await self._create_simple_order(basic_info, context)
            else:
                categories = set(biz.get("category", "General") for biz in context.get("businesses", []))
                category_list = ', '.join(sorted(categories))
                return f"I understand you want to make a booking or order, but I need more details. I can help with {category_list} businesses. Could you please provide your name and contact information?"
                
        except Exception as e:
            self.logger.error(f"Degraded transactional handling failed: {e}")
            return "I'm having trouble processing that request right now. Could you try again in a moment?"

    async def _handle_degraded_information(self, message: str, context: Dict[str, Any]) -> str:
        """Handle information requests when RAG is unavailable - category-agnostic"""
        try:
            # Basic keyword-based responses for different categories
            message_lower = message.lower()
            
            if "menu" in message_lower:
                return await self._get_basic_menu_info(context)
            elif "hours" in message_lower or "open" in message_lower or "time" in message_lower:
                return await self._get_basic_hours_info(context)
            elif "location" in message_lower or "address" in message_lower or "where" in message_lower:
                return await self._get_basic_location_info(context)
            elif "service" in message_lower or "repair" in message_lower:
                return await self._get_basic_services_info(context)
            elif "product" in message_lower or "shop" in message_lower:
                return await self._get_basic_products_info(context)
            else:
                # Generic help based on available categories
                categories = set(biz.get("category", "General") for biz in context.get("businesses", []))
                category_list = ', '.join(sorted(categories))
                return f"I'd be happy to help with information about {category_list} businesses. What would you like to know about our services, products, hours, or locations?"
                
        except Exception as e:
            self.logger.error(f"Degraded information handling failed: {e}")
            return "I'm having trouble retrieving information right now. Could you try asking about our businesses, services, or products?"

    def _extract_basic_info(self, message: str) -> Dict[str, Any]:
        """Extract basic information from message using simple patterns"""
        import re
        
        info = {}
        message_lower = message.lower()
        
        # Extract phone number
        phone_match = re.search(r'(\+?[\d\s\-\(\)]{10,})', message)
        if phone_match:
            info["phone"] = phone_match.group(1).strip()
        
        # Extract name (very basic)
        name_match = re.search(r'(?:my name is|i\'m|name:?)\s*([A-Za-z\s]+?)(?:\s|$|,)'.lower(), message_lower)
        if name_match:
            info["customer_name"] = name_match.group(1).strip().title()
        
        # Extract party size
        party_match = re.search(r'(?:party of|table for|for)\s+(\d+)', message_lower)
        if party_match:
            info["party_size"] = int(party_match.group(1))
        
        # Extract time preference
        time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm|evening|tonight|today|tomorrow)', message_lower)
        if time_match:
            hour = int(time_match.group(1))
            minute = time_match.group(2) or "00"
            period = time_match.group(3)
            if period in ["pm", "evening", "tonight"] and hour < 12:
                hour += 12
            info["time"] = f"{hour:02d}:{minute}"
        
        return info

    async def _create_simple_booking(self, info: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Create a simple booking with minimal information - category-agnostic"""
        try:
            # Use first available business
            business = context.get("businesses", [{}])[0]
            business_category = business.get("category", "General").lower()
            
            # Determine appropriate action based on category
            if "restaurant" in business_category or "food" in business_category:
                action = "create_reservation"
                booking_data = {
                    "action": action,
                    "business_id": business.get("id"),
                    "customer_name": info.get("customer_name", "Valued Guest"),
                    "party_size": info.get("party_size", 2),
                    "reservation_datetime": f"{datetime.now().date()}T{info.get('time', '19:00')}:00",
                    "phone": info.get("phone", ""),
                    "special_requests": "Created via simplified process"
                }
                confirmation = f"Thank you! I've made a reservation for {info.get('party_size', 2)} people at {business.get('name', 'our restaurant')}. You'll receive a confirmation shortly."
            else:
                # Generic service/product booking
                action = "create_booking"
                booking_data = {
                    "action": action,
                    "business_id": business.get("id"),
                    "customer_name": info.get("customer_name", "Valued Guest"),
                    "party_size": info.get("party_size", 1),
                    "booking_datetime": f"{datetime.now().date()}T{info.get('time', '09:00')}:00",
                    "phone": info.get("phone", ""),
                    "special_requests": "Created via simplified process",
                    "business_category": business_category
                }
                
                if "service" in business_category or "repair" in business_category:
                    confirmation = f"Thank you! I've scheduled your service appointment at {business.get('name', 'our service center')}. You'll receive a confirmation shortly."
                elif "retail" in business_category or "shop" in business_category:
                    confirmation = f"Thank you! I've scheduled your appointment at {business.get('name', 'our store')}. You'll receive a confirmation shortly."
                else:
                    confirmation = f"Thank you! Your booking at {business.get('name', 'our business')} is confirmed. You'll receive a confirmation shortly."
            
            execution_result = await self.execution_agent.execute_action(booking_data)
            
            if execution_result.success:
                return confirmation
            else:
                return "I had trouble making that booking. Could you please provide more details?"
                
        except Exception as e:
            self.logger.error(f"Simple booking failed: {e}")
            return "I'm having trouble with the booking right now. Please try again."

    async def _create_simple_order(self, info: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Create a simple order with minimal information"""
        try:
            # Use first available business
            business = context.get("businesses", [{}])[0]
            
            order_data = {
                "action": "create_order",
                "business_id": business.get("id"),
                "customer_name": info.get("customer_name", "Valued Guest"),
                "phone": info.get("phone", ""),
                "items": "Order placed via simplified process",
                "delivery_method": "pickup",
                "special_instructions": "Created via simplified process"
            }
            
            execution_result = await self.execution_agent.execute_action(order_data)
            
            if execution_result.success:
                return f"Thank you! I've placed your order from {business.get('name', 'our restaurant')}. You'll receive confirmation shortly."
            else:
                return "I had trouble placing that order. Could you please provide more details?"
                
        except Exception as e:
            self.logger.error(f"Simple order failed: {e}")
            return "I'm having trouble with the order right now. Please try again."

    async def _get_basic_menu_info(self, context: Dict[str, Any]) -> str:
        """Get basic menu information when RAG is unavailable"""
        try:
            businesses = context.get("businesses", [])
            if not businesses:
                return "I don't have menu information available right now."
            
            business = businesses[0]
            menu_items = business.get("menu", [])[:5]  # Show first 5 items
            
            if menu_items:
                menu_text = "\n".join([f"- {item['name']} (€{item['price']:.2f})" for item in menu_items])
                return f"Here's what we offer at {business['name']}:\n{menu_text}\n\nThis is just a sample - we have many more delicious options!"
            else:
                return f"{business['name']} has a great selection of dishes. I'd recommend calling them directly for the full menu."
                
        except Exception as e:
            self.logger.error(f"Basic menu info failed: {e}")
            return "I'm having trouble accessing menu information right now."

    async def _get_basic_hours_info(self, context: Dict[str, Any]) -> str:
        """Get basic hours information when RAG is unavailable"""
        try:
            businesses = context.get("businesses", [])
            if not businesses:
                return "I don't have hours information available right now."
            
            business = businesses[0]
            status = business.get("status", "Open")
            
            return f"{business['name']} is currently {status.lower()}. For specific hours, I'd recommend calling them at {business.get('phone', 'their phone number')}."
                
        except Exception as e:
            self.logger.error(f"Basic hours info failed: {e}")
            return "I'm having trouble accessing hours information right now."

    async def _get_basic_services_info(self, context: Dict[str, Any]) -> str:
        """Get basic services information when RAG is unavailable"""
        try:
            businesses = context.get("businesses", [])
            service_businesses = [biz for biz in businesses if "service" in biz.get("category", "").lower() or "repair" in biz.get("category", "").lower()]
            
            if not service_businesses:
                return "I don't have specific service information available right now."
            
            business = service_businesses[0]
            
            return f"{business['name']} provides excellent service. For specific service information, I'd recommend calling them at {business.get('phone', 'their phone number')} or visiting their location."
                
        except Exception as e:
            self.logger.error(f"Basic services info failed: {e}")
            return "I'm having trouble accessing service information right now."

    async def _get_basic_products_info(self, context: Dict[str, Any]) -> str:
        """Get basic products information when RAG is unavailable"""
        try:
            businesses = context.get("businesses", [])
            product_businesses = [biz for biz in businesses if "retail" in biz.get("category", "").lower() or "shop" in biz.get("category", "").lower()]
            
            if not product_businesses:
                return "I don't have specific product information available right now."
            
            business = product_businesses[0]
            
            return f"{business['name']} offers a great selection of products. For specific product information, I'd recommend calling them at {business.get('phone', 'their phone number')} or visiting their store."
                
        except Exception as e:
            self.logger.error(f"Basic products info failed: {e}")
            return "I'm having trouble accessing product information right now."

    async def _build_rich_context(
        self, session_id: str, user_location: Optional[str], user_language: str, preferences: Dict
    ) -> Dict[str, Any]:
        """Build enterprise-grade context — briefing for all agents"""
        context = {
            "current_time": datetime.now().strftime("%A, %B %d, %Y at %I:%M %p"),
            "user_location": user_location,
            "user_language": user_language,
            "user_preferences": preferences,
            "businesses": [],
            "conversation_history": [],
        }

        # Load businesses + enrich with menu, status, location
        try:
            businesses_resp = self.supabase.table("businesses").select("*").eq("is_active", True).execute()
            businesses = businesses_resp.data or []

            for biz in businesses:
                # Load menu
                menu_resp = self.supabase.table("menu_items").select("*").eq("business_id", biz["id"]).eq("is_available", True).execute()
                menu_items = menu_resp.data or []

                # Format business for agents
                formatted_biz = {
                    "id": biz["id"],
                    "name": biz["name"],
                    "category": biz.get("category", "General"),
                    "location": biz.get("address", ""),
                    "description": biz.get("description", ""),
                    "phone": biz.get("phone", ""),
                    "status": "Open" if biz.get("is_active") else "Closed",
                    "menu": [
                        {
                            "id": item["id"],
                            "name": item["name"],
                            "description": item.get("description", ""),
                            "price": float(item.get("base_price", 0)),
                            "currency": "€",
                        }
                        for item in menu_items
                    ],
                }

                # Location filtering
                if user_location:
                    loc_lower = user_location.lower().strip()
                    biz_loc = formatted_biz["location"].lower()
                    if loc_lower in biz_loc or any(word in biz_loc for word in loc_lower.split()):
                        context["businesses"].append(formatted_biz)
                else:
                    context["businesses"].append(formatted_biz)

        except Exception as e:
            self.logger.error(f"⚠️ Failed to load businesses: {e}")

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

        return context

    def _build_general_prompt(self, context: Dict[str, Any]) -> str:
        """Build dynamic prompt for general conversation based on available business categories"""
        businesses = context.get("businesses", [])
        
        # Get unique categories
        categories = set(biz.get("category", "General") for biz in businesses)
        
        # Build business examples
        businesses_text = "\n".join([
            f"- {biz['name']} ({biz['category']}) in {biz['location']}"
            for biz in businesses[:8]
        ])
        
        # Create category-specific help text
        help_text = []
        
        if any("restaurant" in cat.lower() or "food" in cat.lower() for cat in categories):
            help_text.append("- Restaurant reservations and food orders")
            
        if any("service" in cat.lower() or "repair" in cat.lower() for cat in categories):
            help_text.append("- Service appointments and repairs")
            
        if any("retail" in cat.lower() or "shop" in cat.lower() for cat in categories):
            help_text.append("- Product purchases and shopping")
            
        help_text.extend([
            "- Business information and recommendations",
            "- General assistance with local services"
        ])
        
        help_text_str = "\n".join(help_text)

        return f"""You are X-SevenAI, a friendly multi-category business concierge.

🌟 {context['current_time']}
📍 Serving: {len(context['businesses'])} businesses across {len(categories)} categories

AVAILABLE CATEGORIES: {', '.join(sorted(categories))}

AVAILABLE BUSINESSES:
{businesses_text}

Be friendly, conversational, and helpful. You can help with:
{help_text_str}

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
            resp = self.supabase.table("user_preferences").select("*").eq("user_id", user_id).execute()
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
            self.supabase.table("user_preferences").upsert({
                "user_id": user_id,
                "preferences": prefs,
                "updated_at": datetime.utcnow().isoformat(),
            }, on_conflict="user_id").execute()
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to update preferences: {e}")
