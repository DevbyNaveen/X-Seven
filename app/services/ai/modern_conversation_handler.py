"""Modern Conversation Handler

Simplified conversation handler that uses rich context and natural AI understanding
instead of complex state management. Implements the modern AI transformation approach.
"""
from typing import Any, Dict, List, Optional, AsyncGenerator
import json
import re
import os
import asyncio
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Business, Message
from app.services.ai.context_builder import RichContextBuilder
from app.services.ai.business_functions import UniversalBusinessFunctions
from app.config.settings import settings


class ModernConversationHandler:
    """Simplified conversation handler using rich context and natural AI understanding."""
    
    def __init__(self, db: Session):
        self.db = db
        self.context_builder = RichContextBuilder(db)
        self.business_functions = UniversalBusinessFunctions(db)
    
    async def process_message(
        self,
        *,
        session_id: str,
        message: str,
        channel: str = "chat",
        context: Optional[Dict[str, Any]] = None,
        phone_number: Optional[str] = None,
        location: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Process a user message with rich context and natural AI understanding."""
        
        # Build comprehensive context
        selected_business_id = None
        if context:
            selected_business_id = context.get("selected_business") or context.get("business_id")
        
        rich_context = self.context_builder.build_context(
            session_id=session_id,
            user_message=message,
            selected_business_id=selected_business_id,
            location=location,
            phone_number=phone_number,
            max_history_messages=getattr(settings, "GROQ_MAX_HISTORY", 6),
            max_businesses=getattr(settings, "GROQ_MAX_BUSINESSES", 8)
        )
        
        # Generate AI response with rich context
        ai_response = await self._generate_ai_response(rich_context)
        
        # Parse response and actions
        response_text, suggested_actions = self._parse_response(ai_response)
        
        # Save messages if business is selected
        if selected_business_id:
            await self._save_conversation(
                session_id=session_id,
                business_id=selected_business_id,
                user_message=message,
                ai_response=response_text
            )
        
        return {
            "message": response_text,
            "suggested_actions": suggested_actions,
            "metadata": {
                "business_id": selected_business_id,
                "channel": channel,
                "ai_model_used": "groq",
                "context_type": "rich_natural"
            }
        }
    
    async def stream_response(
        self,
        *,
        session_id: str,
        message: str,
        channel: str = "chat",
        context: Optional[Dict[str, Any]] = None,
        phone_number: Optional[str] = None,
        location: Optional[Dict[str, Any]] = None,
        delay_ms: int = 30,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream response character by character for natural typing effect."""
        
        # Get complete response first
        response = await self.process_message(
            session_id=session_id,
            message=message,
            channel=channel,
            context=context,
            phone_number=phone_number,
            location=location,
        )
        
        full_message = response["message"]
        suggested_actions = response["suggested_actions"]
        metadata = response["metadata"]
        
        # Stream character by character with natural typing delays
        if full_message:
            for i, char in enumerate(full_message):
                yield {
                    "type": "chunk",
                    "data": {
                        "character": char,
                        "position": i,
                        "partial_message": full_message[:i+1]
                    }
                }
                
                # Natural typing delays based on character type
                if char == '\n':
                    await asyncio.sleep(delay_ms * 3 / 1000)  # Longer pause for new lines
                elif char in '.!?':
                    await asyncio.sleep(delay_ms * 4 / 1000)  # Pause after sentences
                elif char == ',':
                    await asyncio.sleep(delay_ms * 2 / 1000)  # Brief pause for commas
                elif char == ' ':
                    await asyncio.sleep(delay_ms * 0.7 / 1000)  # Quick pause for spaces
                else:
                    await asyncio.sleep(delay_ms / 1000)  # Normal character delay
        
        # Send actions and metadata
        if suggested_actions:
            yield {"type": "actions", "data": suggested_actions}
        
        yield {"type": "metadata", "data": metadata}
        
        # Final completion
        yield {
            "type": "complete",
            "data": {
                "message": full_message,
                "suggested_actions": suggested_actions,
                "metadata": metadata
            }
        }
    
    async def _generate_ai_response(self, rich_context: Dict[str, Any]) -> str:
        """Generate AI response using rich context and natural prompting with function calling."""
        
        system_prompt = self._build_system_prompt()
        context_json = json.dumps(rich_context, ensure_ascii=False, indent=2, default=str)
        
        full_prompt = f"""{system_prompt}

RICH CONTEXT:
{context_json}

USER MESSAGE: {rich_context['user_message']}

Response:"""
        
        # Ensure prompt size is manageable
        max_chars = getattr(settings, "GROQ_MAX_PROMPT_CHARS", 12000)
        if len(full_prompt) > max_chars:
            rich_context = await self._rebuild_shrunk_context(rich_context)
            context_json = json.dumps(rich_context, ensure_ascii=False, indent=2, default=str)
            full_prompt = f"""{system_prompt}

RICH CONTEXT:
{context_json}

USER MESSAGE: {rich_context['user_message']}

Response:"""
        
        try:
            # Try with function calling first
            response = await self._call_llm_with_functions(full_prompt)
            
            if response.get("function_call"):
                # Execute function and generate final response
                function_result = await self._execute_function_call(response["function_call"])
                final_response = await self._generate_final_response(
                    rich_context, response["function_call"], function_result
                )
                return self._clean_response(final_response)
            else:
                # Direct response without function call
                return self._clean_response(response.get("content", ""))
                
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"AI response generation failed: {e}")
            
            # Fallback to basic LLM call
            try:
                response = await self._call_llm(full_prompt)
                return self._clean_response(response)
            except Exception as fallback_error:
                logger.error(f"Fallback LLM call also failed: {fallback_error}")
                return "I'm having trouble processing your request right now. Please try again."

    async def _rebuild_shrunk_context(self, rich_context: Dict[str, Any]) -> Dict[str, Any]:
        """Rebuild a smaller context by limiting history and businesses."""
        try:
            session_id = rich_context.get("session_id")
            user_message = rich_context.get("user_message", "")
            location = rich_context.get("location")
            phone_number = rich_context.get("phone_number")
            selected_business = rich_context.get("selected_business") or {}
            selected_business_id = selected_business.get("id") if isinstance(selected_business, dict) else None
            
            return self.context_builder.build_context(
                session_id=session_id,
                user_message=user_message,
                selected_business_id=selected_business_id,
                location=location,
                phone_number=phone_number,
                max_history_messages=3,
                max_businesses=3,
            )
        except Exception:
            return rich_context
    
    def _build_system_prompt(self) -> str:
        """Modern, concise system prompt focused on natural conversation."""
        return """You are X-SevenAI, an intelligent business assistant that helps customers discover, book, and order from local businesses.

# Core Capabilities
- **Find businesses** across 5 categories: Food, Beauty, Automotive, Health, Local Services
- **Check availability** and make intelligent booking recommendations  
- **Process orders** and reservations seamlessly
- **Provide personalized suggestions** based on preferences and context

# Available Functions
When you need specific data or actions, call these functions:
- `find_businesses(criteria, category, location)` - Search businesses
- `get_services(business_id)` - Get menu/services for a business
- `get_booking_data(business_id, date, time, participants)` - Check availability
- `create_booking_record(...)` - Confirm bookings
- `create_order_record(...)` - Process orders

# Interaction Style
- **Natural & conversational** - Talk like a helpful local expert
- **Proactive** - Suggest relevant options and alternatives
- **Context-aware** - Remember what was discussed earlier
- **Multi-lingual** - Respond in the user's language
- **Action-oriented** - Guide users toward successful bookings/orders

# Decision Making
- **Peak times** → Suggest alternatives or express service
- **Large groups** → Check capacity and recommend optimal times
- **Availability issues** → Offer waitlist, nearby alternatives, or different times
- **Unclear requests** → Ask clarifying questions to help better

# Response Format
- Use **markdown** for clarity (bold, lists, etc.)
- Include **specific details** (times, prices, locations)
- End with **clear next steps** or suggested actions
- Be **concise but complete** - quality over quantity

You have access to comprehensive business data and booking intelligence. Use it to provide exceptional service that feels personal and helpful."""

    def _get_available_functions(self) -> List[Dict[str, Any]]:
        """Get available functions for native LLM function calling."""
        return [
            {
                "name": "find_businesses",
                "description": "Search for businesses by name, category, or location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "criteria": {"type": "string", "description": "General search term"},
                        "category": {"type": "string", "description": "Business category"},
                        "service_type": {"type": "string", "description": "Specific service type"},
                        "location": {"type": "string", "description": "Location filter"},
                        "features": {"type": "array", "items": {"type": "string"}},
                        "limit": {"type": "integer", "description": "Max results"}
                    }
                }
            },
            {
                "name": "get_services",
                "description": "Get services/menu for a specific business",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "business_id": {"type": "integer", "description": "Business ID"},
                        "service_category": {"type": "string", "description": "Service category filter"},
                        "search_term": {"type": "string", "description": "Search within services"}
                    },
                    "required": ["business_id"]
                }
            },
            {
                "name": "get_booking_data",
                "description": "Get booking availability data",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "business_id": {"type": "integer", "description": "Business ID"},
                        "date": {"type": "string", "format": "date", "description": "Date (YYYY-MM-DD)"},
                        "time": {"type": "string", "description": "Time (HH:MM)"},
                        "participants": {"type": "integer", "description": "Number of participants"},
                        "service_type": {"type": "string", "description": "Service type"}
                    },
                    "required": ["business_id", "date", "time", "participants"]
                }
            },
            {
                "name": "create_booking_record",
                "description": "Create a confirmed booking",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "business_id": {"type": "integer"},
                        "customer_info": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "phone": {"type": "string"},
                                "email": {"type": "string"}
                            },
                            "required": ["name", "phone"]
                        },
                        "datetime_str": {"type": "string", "description": "ISO datetime"},
                        "service_participants": {"type": "integer"},
                        "service_type": {"type": "string"},
                        "special_requests": {"type": "string"}
                    },
                    "required": ["business_id", "customer_info", "datetime_str", "service_participants"]
                }
            },
            {
                "name": "create_order_record",
                "description": "Create an order for services/products",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "business_id": {"type": "integer"},
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "integer"},
                                    "quantity": {"type": "integer"},
                                    "customizations": {"type": "array", "items": {"type": "string"}}
                                },
                                "required": ["id", "quantity"]
                            }
                        },
                        "customer_info": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "phone": {"type": "string"},
                                "email": {"type": "string"}
                            },
                            "required": ["name", "phone"]
                        },
                        "payment_method": {"type": "string"},
                        "delivery_info": {"type": "object"}
                    },
                    "required": ["business_id", "items", "customer_info"]
                }
            }
        ]

    async def _call_llm_with_functions(self, prompt: str) -> Dict[str, Any]:
        """Call LLM with native function calling support."""
        try:
            from groq import Groq
            
            api_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY")
            if not api_key:
                return {"content": await self._call_llm(prompt)}
            
            # Fix: Remove the proxies parameter that's causing the error
            client = Groq(api_key=api_key)
            
            groq_model = getattr(settings, "GROQ_MODEL", "llama-3.1-8b-instant")
            max_tokens = int(getattr(settings, "GROQ_MAX_TOKENS", 600))
            
            response = client.chat.completions.create(
                model=groq_model,
                messages=[{"role": "user", "content": prompt}],
                tools=[{"type": "function", "function": func} for func in self._get_available_functions()],
                tool_choice="auto",
                temperature=0.7,
                max_tokens=max_tokens
            )
            
            message = response.choices[0].message
            
            # Check for tool calls
            if hasattr(message, 'tool_calls') and message.tool_calls:
                tool_call = message.tool_calls[0]
                return {
                    "function_call": {
                        "name": tool_call.function.name,
                        "arguments": json.loads(tool_call.function.arguments)
                    }
                }
            else:
                return {"content": message.content or ""}
                
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Function calling failed: {e}")
            # Fallback to basic LLM call
            return {"content": await self._call_llm(prompt)}
    
    async def _execute_function_call(self, function_call: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the requested business function."""
        function_name = function_call["name"]
        args = function_call["arguments"]

        try:
            if function_name == "find_businesses":
                return self.business_functions.find_businesses(**args)
            elif function_name == "get_services":
                return self.business_functions.get_services(**args)
            elif function_name == "get_booking_data":
                return self.business_functions.get_booking_data(**args)
            elif function_name == "create_booking_record":
                return self.business_functions.create_booking_record(**args)
            elif function_name == "create_order_record":
                return self.business_functions.create_order_record(**args)
            else:
                return {"error": f"Unknown function: {function_name}"}
        except Exception as e:
            return {"error": f"Function execution failed: {str(e)}"}
    
    async def _generate_final_response(
        self,
        rich_context: Dict[str, Any],
        function_call: Dict[str, Any],
        function_result: Dict[str, Any]
    ) -> str:
        """Generate final response incorporating function results."""
        
        system_prompt = """You have executed a function and received results. Use these results to provide a natural, helpful response to the user.

RULES:
- Present the function results naturally without mentioning the function call
- Respond in the user's language
- Use Markdown formatting for readability
- Be conversational and helpful
- Don't expose any technical details about the function execution"""
        
        context_summary = {
            "user_message": rich_context["user_message"],
            "function_executed": function_call["name"],
            "function_results": function_result
        }
        
        prompt = f"""{system_prompt}

CONTEXT: {json.dumps(context_summary, ensure_ascii=False, default=str)}

Provide a natural response based on the function results:"""
        
        return await self._call_llm(prompt)
    
    def _parse_response(self, response: str) -> tuple[str, List[Dict[str, str]]]:
        """Parse response text and extract suggested actions."""
        if not response:
            return "", []
        
        # Look for ACTIONS section
        actions = []
        main_text = response
        
        actions_match = re.search(r'\nACTIONS:\s*\n(.*?)(?:\n\n|\n[A-Z]+:|\Z)', response, re.DOTALL | re.IGNORECASE)
        if actions_match:
            main_text = response[:actions_match.start()].strip()
            actions_text = actions_match.group(1)
            
            # Parse action lines
            for line in actions_text.split('\n'):
                line = line.strip()
                if '|' in line:
                    # Remove bullet points and parse
                    line = re.sub(r'^[-*•]\s*', '', line)
                    if '|' in line:
                        title, action_id = line.split('|', 1)
                        actions.append({
                            "id": action_id.strip(),
                            "title": title.strip()
                        })
        
        return main_text.strip(), actions
    
    def _clean_response(self, response: str) -> str:
        """Clean and format AI response."""
        if not response:
            return ""
        
        # Remove common AI thinking patterns
        cleaned = re.sub(r'^(Okay|Let me|I need to|I will|I can help you|Sure|Of course)[,.]?\s*', '', response.strip(), flags=re.IGNORECASE)
        
        # Remove function call artifacts
        cleaned = re.sub(r'FUNCTION_CALL:.*?}', '', cleaned, flags=re.DOTALL)
        
        # Clean up extra whitespace
        cleaned = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned)
        
        return cleaned.strip()
    
    async def _call_llm(self, prompt: str) -> str:
        """Make a basic LLM call without function calling."""
        try:
            from groq import Groq
            
            api_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY")
            if not api_key:
                return "I'm having trouble connecting to my AI service right now. Please try again."
            
            # Fix: Remove the proxies parameter
            client = Groq(api_key=api_key)
            
            groq_model = getattr(settings, "GROQ_MODEL", "llama-3.1-8b-instant")
            max_tokens = int(getattr(settings, "GROQ_MAX_TOKENS", 600))
            
            response = client.chat.completions.create(
                model=groq_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=max_tokens,
                stream=False
            )
            
            return response.choices[0].message.content or ""
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"LLM call failed: {e}")
            return "I'm having trouble processing your request right now. Please try again."
    
    async def _save_conversation(
        self,
        session_id: str,
        business_id: int,
        user_message: str,
        ai_response: str
    ) -> None:
        """Save conversation messages to database."""
        try:
            # Save user message
            user_msg = Message(
                session_id=session_id,
                business_id=business_id,
                sender_type="customer",
                content=user_message,
                message_type="text",
                intent_detected="natural_conversation",
                ai_model_used=None,
                response_time_ms=None,
                extra_data={}
            )
            self.db.add(user_msg)
            
            # Save AI response
            ai_msg = Message(
                session_id=session_id,
                business_id=business_id,
                sender_type="bot",
                content=ai_response,
                message_type="text",
                intent_detected="natural_conversation",
                ai_model_used="groq",
                response_time_ms=None,
                extra_data={}
            )
            self.db.add(ai_msg)
            
            self.db.commit()
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to save conversation: {e}")
            # Don't fail the conversation on database errors
            pass