"""
Intent Agent - Modern AI Intent Detection with Self-Healing
Identifies user intent from natural language messages with automatic recovery
"""
import json
import logging
from typing import Dict, Any, Optional, Literal, List
from dataclasses import dataclass

from .self_healing import with_self_healing, self_healing_manager

IntentType = Literal["reservation", "order", "info", "other"]

@dataclass
class IntentResult:
    """Result of intent detection"""
    intent: IntentType
    confidence: float
    entities: Dict[str, Any]
    reasoning: str

class IntentAgent:
    """
    AI-powered intent detection agent with self-healing capabilities
    Uses LLM to understand user intent from natural language with automatic recovery
    """
    
    def __init__(self, groq_client):
        self.groq = groq_client
        self.logger = logging.getLogger(__name__)
        
        # Register with self-healing system
        self_healing_manager.register_agent("intent_agent", self)
        
        # Define fallback strategies
        self._fallback_strategies = self._create_fallback_strategies()
    
    def _create_fallback_strategies(self):
        """Create fallback strategies for self-healing"""
        async def keyword_fallback():
            return {
                "intent": "other",
                "confidence": 0.3,
                "entities": {},
                "reasoning": "Keyword-based fallback due to system issues"
            }
        
        return keyword_fallback
    
    @with_self_healing("intent_agent")
    async def detect_intent(self, message: str, context: Dict[str, Any]) -> IntentResult:
        """
        Detect user intent from message using AI with self-healing protection
        
        Args:
            message: User's message
            context: Business context and conversation history
            
        Returns:
            IntentResult with detected intent and metadata
        """
        try:
            # Build dynamic intent detection prompt based on available businesses
            system_prompt = await self._build_dynamic_intent_prompt(context)
            
            response = self.groq.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"User message: {message}"}
                ],
                temperature=0.3,
                max_tokens=300,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            return IntentResult(
                intent=result.get("intent", "other"),
                confidence=result.get("confidence", 0.5),
                entities=result.get("entities", {}),
                reasoning=result.get("reasoning", "")
            )
            
        except Exception as e:
            self.logger.error(f"Intent detection failed: {e}")
            # Fallback to keyword-based detection
            return await self._dynamic_fallback_intent_detection(message, context)
    
    async def _build_dynamic_intent_prompt(self, context: Dict[str, Any]) -> str:
        """Build dynamic intent detection prompt based on available business categories"""
        businesses = context.get("businesses", [])
        
        # Analyze available business categories
        categories = set()
        business_examples = []
        
        for biz in businesses:
            category = biz.get("category", "General")
            categories.add(category)
            business_examples.append(f"- {biz['name']} ({category})")
        
        # Create dynamic intent categories based on business types
        intent_categories = self._generate_dynamic_intents(list(categories))
        
        # Build business context
        businesses_context = "\n".join(business_examples[:8])  # Show up to 8 examples
        
        return f"""You are an expert intent classifier for a multi-category business discovery system.

Your job is to analyze user messages and determine their primary intent across different business categories.

AVAILABLE BUSINESS CATEGORIES:
{', '.join(sorted(categories))}

DYNAMIC INTENT CATEGORIES:
{intent_categories}

CLASSIFICATION RULES:
- Focus on the primary action the user wants to take
- Consider the business category when determining intent
- Be flexible - adapt to different types of businesses (restaurants, services, retail, etc.)
- Extract relevant entities like business names, times, dates, quantities
- Confidence should reflect how clear the intent is (0.0-1.0)

AVAILABLE BUSINESSES:
{businesses_context}

RESPOND WITH JSON:
{{
  "intent": "service_booking|product_order|information|general",
  "confidence": 0.8,
  "entities": {{
    "business_name": "extracted business name (if mentioned, otherwise leave empty)",
    "category": "business category if detectable",
    "time": "extracted time",
    "date": "extracted date",
    "quantity": "extracted quantity or party size"
  }},
  "reasoning": "brief explanation of classification"
}}"""

    def _generate_dynamic_intents(self, categories: List[str]) -> str:
        """Generate dynamic intent categories based on business types"""
        intents = []
        
        # Always include these core intents
        intents.append('"service_booking": User wants to book an appointment, make a reservation, or schedule a service')
        intents.append('"product_order": User wants to order/purchase products or services')
        intents.append('"information": User is asking about services, products, hours, location, or general information')
        intents.append('"general": General conversation, greetings, or unclear intent')
        
        # Add category-specific intents
        for category in categories:
            category_lower = category.lower()
            if "restaurant" in category_lower or "food" in category_lower:
                intents.append(f'"{category_lower}_reservation": User wants to book a table or make a dining reservation')
                intents.append(f'"{category_lower}_order": User wants to order food for delivery, pickup, or dine-in')
            elif "service" in category_lower or "repair" in category_lower:
                intents.append(f'"{category_lower}_booking": User wants to schedule a service appointment')
            elif "retail" in category_lower or "shop" in category_lower:
                intents.append(f'"{category_lower}_purchase": User wants to buy products or inquire about items')
        
        return '\n'.join(f'- {intent}' for intent in intents)

    async def _dynamic_fallback_intent_detection(self, message: str, context: Dict[str, Any]) -> IntentResult:
        """Dynamic keyword-based fallback that adapts to available business categories"""
        message_lower = message.lower().strip()
        
        # Get available business categories
        businesses = context.get("businesses", [])
        categories = set(biz.get("category", "General").lower() for biz in businesses)
        
        # Dynamic keyword generation based on categories
        booking_keywords = [
            "book", "reserve", "appointment", "schedule", "booking", 
            "available", "availability", "slot", "time", "date"
        ]
        
        order_keywords = [
            "order", "buy", "purchase", "get", "want", "need",
            "delivery", "pickup", "takeout"
        ]
        
        info_keywords = [
            "what", "when", "where", "how", "tell me about", 
            "information", "details", "hours", "location", "price"
        ]
        
        # Add category-specific keywords
        for category in categories:
            if "restaurant" in category or "food" in category:
                booking_keywords.extend(["table", "dine", "dinner", "lunch", "reservation"])
                order_keywords.extend(["menu", "food", "eat", "hungry", "dish", "meal"])
            elif "service" in category or "repair" in category:
                booking_keywords.extend(["fix", "repair", "service", "maintenance", "appointment"])
            elif "retail" in category or "shop" in category:
                order_keywords.extend(["product", "item", "shopping", "buy", "purchase"])
        
        # Score intents
        booking_score = sum(1 for word in booking_keywords if word in message_lower)
        order_score = sum(1 for word in order_keywords if word in message_lower)
        info_score = sum(1 for word in info_keywords if word in message_lower)
        
        max_score = max(booking_score, order_score, info_score)
        
        if max_score == 0:
            intent = "general"
            confidence = 0.3
        elif booking_score >= max_score:
            intent = "service_booking"
            confidence = 0.7
        elif order_score >= max_score:
            intent = "product_order"
            confidence = 0.7
        else:
            intent = "information"
            confidence = 0.6
            
        return IntentResult(
            intent=intent,
            confidence=confidence,
            entities={},
            reasoning=f"Dynamic keyword detection with score {max_score}"
        )
