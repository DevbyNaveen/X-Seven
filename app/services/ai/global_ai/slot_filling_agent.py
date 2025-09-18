"""
Slot-Filling Agent - Modern Data Collection Agent with Self-Healing
Collects required information for reservations and orders with automatic recovery
"""
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime

from .self_healing import with_self_healing, self_healing_manager

@dataclass
class SlotSchema:
    """Schema for a required slot"""
    name: str
    type: str
    required: bool = True
    description: str = ""
    validation: Optional[str] = None

@dataclass
class SlotState:
    """Current state of slot filling"""
    slots: Dict[str, Any] = field(default_factory=dict)
    missing_slots: List[str] = field(default_factory=list)
    is_complete: bool = False
    last_question: Optional[str] = None

class SlotFillingAgent:
    """
    AI-powered slot filling agent with self-healing capabilities
    Collects required information through natural conversation with automatic recovery
    """

    def __init__(self, groq_client):
        self.groq = groq_client
        self.logger = logging.getLogger(__name__)
        
        # Register with self-healing system
        self_healing_manager.register_agent("slot_filling_agent", self)
        
        # Define fallback strategies
        self._fallback_strategies = self._create_fallback_strategies()
        
        # Dynamic slot schemas based on business categories
        self.slot_schemas = self._initialize_dynamic_slot_schemas()
    
    def _initialize_dynamic_slot_schemas(self) -> Dict[str, List[SlotSchema]]:
        """Initialize dynamic slot schemas - will be updated based on business context"""
        return {
            "service_booking": [
                SlotSchema("business_name", "string", True, "Name of the business"),
                SlotSchema("customer_name", "string", True, "Name for the booking"),
                SlotSchema("party_size", "integer", False, "Number of people (for restaurants) or quantity (for services)"),
                SlotSchema("booking_date", "date", True, "Date for the booking/appointment"),
                SlotSchema("booking_time", "time", True, "Time for the booking/appointment"),
                SlotSchema("phone", "string", True, "Contact phone number"),
                SlotSchema("special_requests", "string", False, "Any special requests or requirements")
            ],
            "product_order": [
                SlotSchema("business_name", "string", True, "Business to order from"),
                SlotSchema("customer_name", "string", True, "Name for the order"),
                SlotSchema("phone", "string", True, "Contact phone number"),
                SlotSchema("items", "list", True, "Products or services to order"),
                SlotSchema("delivery_method", "string", False, "delivery, pickup, or in-store"),
                SlotSchema("delivery_address", "string", False, "Address for delivery (if applicable)"),
                SlotSchema("special_instructions", "string", False, "Special instructions for the order")
            ],
            "information": [
                SlotSchema("business_name", "string", False, "Specific business to inquire about"),
                SlotSchema("topic", "string", True, "What information they want (hours, location, services, etc.)")
            ]
        }

    def _create_fallback_strategies(self):
        """Create fallback strategies for self-healing"""
        async def basic_fallback():
            return {
                "status": "incomplete", 
                "next_question": "Could you please provide more details for your request?",
                "missing_slots": ["details"],
                "next_slot": "details"
            }
        
        return basic_fallback
    
    @with_self_healing("slot_filling_agent")
    async def fill_slots(self, intent: str, message: str, context: Dict[str, Any],
                        conversation_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Fill slots for the given intent with self-healing protection
        
        Args:
            intent: The detected intent (service_booking/product_order/information)
            message: Current user message
            context: Business context
            conversation_history: Previous conversation turns
            
        Returns:
            Dict with slot state and next action
        """
        try:
            # Update slot schema based on business context if needed
            self._update_slot_schema_for_context(intent, context)
            
            # Get slot schema for this intent
            slots = self.slot_schemas.get(intent, [])
            if not slots:
                return {"error": f"No slot schema for intent: {intent}"}

            # Extract current slot values from context and message
            current_slots = await self._extract_slots(intent, message, context, conversation_history)

            # Determine missing slots
            missing_slots = []
            for slot in slots:
                if slot.required and not current_slots.get(slot.name):
                    missing_slots.append(slot.name)

            # Check if we have all required slots
            is_complete = len(missing_slots) == 0

            if is_complete:
                return {
                    "status": "complete",
                    "slots": current_slots,
                    "structured_data": await self._create_structured_data(intent, current_slots, context)
                }
            else:
                # Generate next question for missing slot
                next_slot = missing_slots[0]
                question = await self._generate_question(intent, next_slot, current_slots, context)
                
                return {
                    "status": "incomplete",
                    "slots": current_slots,
                    "missing_slots": missing_slots,
                    "next_question": question,
                    "next_slot": next_slot
                }

        except Exception as e:
            self.logger.error(f"Slot filling failed: {e}")
            return {"error": str(e)}
    
    def _update_slot_schema_for_context(self, intent: str, context: Dict[str, Any]):
        """Update slot schema based on specific business context"""
        businesses = context.get("businesses", [])
        if not businesses:
            return
            
        # Get business categories
        categories = set(biz.get("category", "General").lower() for biz in businesses)
        
        # Adjust slot schemas based on business types
        if intent == "service_booking":
            # Add category-specific slots
            for category in categories:
                if "restaurant" in category or "food" in category:
                    # Keep party_size as required for restaurants
                    for slot in self.slot_schemas[intent]:
                        if slot.name == "party_size":
                            slot.required = True
                            break
                elif "service" in category or "repair" in category:
                    # Make party_size optional for services
                    for slot in self.slot_schemas[intent]:
                        if slot.name == "party_size":
                            slot.required = False
                            slot.description = "Number of items or quantity needed"
                            break

    async def _extract_slots(self, intent: str, message: str, context: Dict[str, Any],
                           conversation_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract slot values using AI"""
        try:
            system_prompt = self._build_extraction_prompt(intent, context)

            # Format conversation history
            history_text = "\n".join([
                f"{'User' if msg.get('role') == 'user' else 'Assistant'}: {msg.get('content', '')}"
                for msg in conversation_history[-5:]
            ])

            user_content = f"""Previous conversation:
{history_text}

Current message: {message}

Extract all available slot values from the current message and context."""

            response = self.groq.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.2,
                max_tokens=400,
                response_format={"type": "json_object"}
            )

            return json.loads(response.choices[0].message.content)

        except Exception as e:
            self.logger.error(f"Slot extraction failed: {e}")
            # Fallback to basic extraction
            return self._basic_extraction(intent, message, context)

    def _build_extraction_prompt(self, intent: str, context: Dict[str, Any]) -> str:
        """Build dynamic extraction prompt based on intent and business categories"""
        businesses = context.get("businesses", [])
        categories = set(biz.get("category", "General") for biz in businesses)
        
        # Build business context
        business_list = "\n".join([
            f"- {biz['name']} ({biz['category']})"
            for biz in businesses[:5]
        ])
        
        base_prompt = f"""You are a data extraction expert for a multi-category business system.

Available business categories: {', '.join(sorted(categories))}
Available businesses:
{business_list}

"""
        
        if intent == "service_booking":
            return base_prompt + """Extract booking/appointment slot values from user messages. Be flexible with different business types.

SLOT DEFINITIONS:
- business_name: Name of business (match against available businesses)
- customer_name: Person's name for the booking
- party_size: Number of people/items/quantity (context-dependent)
- booking_date: Date (format as YYYY-MM-DD)
- booking_time: Time (format as HH:MM in 24-hour format)
- phone: Phone number (standard format)
- special_requests: Any special requirements or notes

EXTRACTION RULES:
- Use fuzzy matching for business names
- Convert relative dates ("tomorrow", "next Friday") to actual dates
- Parse natural time expressions ("7pm", "half past 8")
- Extract numbers for party size or quantity
- Use context from previous messages if not in current message
- Adapt to business category (party_size might mean people for restaurants, items for services)

RESPOND WITH JSON:
{{
  "business_name": "extracted business name",
  "customer_name": "customer name",
  "party_size": 2,
  "booking_date": "2024-01-15",
  "booking_time": "19:00",
  "phone": "+1234567890",
  "special_requests": "special requirements"
}}"""
            
        elif intent == "product_order":
            return base_prompt + """Extract order/purchase slot values from user messages. Be flexible with different product types.

SLOT DEFINITIONS:
- business_name: Business to order from (match against available businesses)
- customer_name: Name for the order
- phone: Contact phone number
- items: List of products/services with quantities (format as "2x Product Name, 1x Another Item")
- delivery_method: "delivery", "pickup", "in-store", or other relevant method
- delivery_address: Address for delivery (only if delivery_method is "delivery")
- special_instructions: Any special preparation or delivery instructions

EXTRACTION RULES:
- Use fuzzy matching for business names
- Parse quantities ("2 items", "one large", "a couple of")
- Identify delivery vs pickup preferences
- Extract full addresses when mentioned
- Use context from previous messages

RESPOND WITH JSON:
{{
  "business_name": "business name",
  "customer_name": "customer name",
  "phone": "+1234567890",
  "items": "2x Product A, 1x Product B",
  "delivery_method": "delivery",
  "delivery_address": "123 Main St, City",
  "special_instructions": "special instructions"
}}"""
            
        elif intent == "information":
            return base_prompt + """Extract information request details from user messages.

SLOT DEFINITIONS:
- business_name: Specific business they want information about (optional)
- topic: What information they want (hours, location, services, products, prices, etc.)

EXTRACTION RULES:
- business_name is optional - they might want general information
- topic should capture the main information need
- Be specific about what they're asking for

RESPOND WITH JSON:
{{
  "business_name": "business name (optional)",
  "topic": "information topic"
}}"""
            
        return base_prompt + "Extract relevant slot values based on the user's intent and message."

    def _basic_extraction(self, intent: str, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Basic keyword-based extraction as fallback"""
        message_lower = message.lower()
        slots = {}

        # Basic extraction for service_booking
        if intent == "service_booking":
            # Extract party size
            import re
            size_match = re.search(r'(?:party of|table for|for|group of)\s+(\d+)', message_lower)
            if size_match:
                slots["party_size"] = int(size_match.group(1))
            
            # Extract phone number
            phone_match = re.search(r'(\+?[\d\s\-\(\)]{10,})', message)
            if phone_match:
                slots["phone"] = phone_match.group(1).strip()
            
            # Extract name (very basic)
            name_patterns = [
                r'(?:my name is|i\'m|name:?)\s*([A-Za-z\s]+?)(?:\s|$|,)',
                r'(?:booking for|reservation for)\s*([A-Za-z\s]+?)(?:\s|$|,)',
                r'(?:this is|hi i\'m)\s*([A-Za-z\s]+?)(?:\s|$|,)'
            ]
            for pattern in name_patterns:
                name_match = re.search(pattern, message_lower)
                if name_match:
                    slots["customer_name"] = name_match.group(1).strip().title()
                    break

        elif intent == "product_order":
            # Extract phone number
            phone_match = re.search(r'(\+?[\d\s\-\(\)]{10,})', message)
            if phone_match:
                slots["phone"] = phone_match.group(1).strip()

            # Extract delivery method
            if "delivery" in message_lower:
                slots["delivery_method"] = "delivery"
            elif "pickup" in message_lower or "takeout" in message_lower:
                slots["delivery_method"] = "pickup"

            # Extract customer name
            name_match = re.search(r'(?:my name is|i\'m|name:?)\s*([A-Za-z\s]+?)(?:\s|$|,)', message_lower)
            if name_match:
                slots["customer_name"] = name_match.group(1).strip().title()

        # Try to extract business name from context of available businesses
        businesses = context.get("businesses", [])
        if businesses:
            for biz in businesses:
                biz_name_lower = biz["name"].lower()
                # Check if business name appears in message
                if biz_name_lower in message_lower:
                    slots["business_name"] = biz["name"]
                    break
            
            # If no business name found, set it to empty so fallback logic can work
            if "business_name" not in slots:
                slots["business_name"] = ""

        return slots

    async def _generate_question(self, intent: str, slot_name: str, current_slots: Dict[str, Any],
                               context: Dict[str, Any]) -> str:
        """Generate natural question for missing slot"""
        try:
            # Build question generation prompt
            businesses = context.get("businesses", [])
            business_names = [biz["name"] for biz in businesses[:3]]

            question_prompt = f"""You are a friendly restaurant concierge. Generate a natural, conversational question to ask for missing information.

Intent: {intent}
Missing slot: {slot_name}
Available businesses: {', '.join(business_names)}
Current filled slots: {json.dumps(current_slots, indent=2)}

Generate ONE natural question that:
- Is friendly and conversational
- Doesn't mention technical terms like "slot" or "required field"
- Uses context from already filled information
- Is concise and easy to answer

Question:"""

            response = self.groq.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "user", "content": question_prompt}
                ],
                temperature=0.7,
                max_tokens=100
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            self.logger.error(f"Question generation failed: {e}")
            # Fallback questions
            fallback_questions = {
                "business_name": "Which restaurant would you like to make a reservation at?",
                "customer_name": "What's the name for the reservation?",
                "party_size": "How many people will be joining you?",
                "reservation_date": "What date would you like to book for?",
                "reservation_time": "What time would you prefer?",
                "phone": "What's your phone number so we can contact you?",
                "items": "What would you like to order?",
                "delivery_method": "Would you like delivery or pickup?"
            }
            return fallback_questions.get(slot_name, f"Can you please provide the {slot_name}?")

    async def _create_structured_data(self, intent: str, slots: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Create structured data for execution agent based on intent"""
        if intent == "service_booking":
            # Find business by name with improved matching
            business_name = slots.get("business_name", "").strip()
            business = self._find_business_by_name(business_name, context)

            # If no specific business found, use first available business as fallback
            if not business and context.get("businesses"):
                business = context["businesses"][0]
                self.logger.info(f"No specific business found for '{business_name}', using fallback: {business['name']}")

            return {
                "action": "create_booking",
                "business_id": business["id"] if business else None,
                "customer_name": slots.get("customer_name"),
                "party_size": slots.get("party_size"),
                "booking_datetime": f"{slots.get('booking_date')}T{slots.get('booking_time')}:00",
                "phone": slots.get("phone"),
                "special_requests": slots.get("special_requests", ""),
                "business_category": business.get("category") if business else "General"
            }

        elif intent == "product_order":
            # Find business by name with improved matching
            business_name = slots.get("business_name", "").strip()
            business = self._find_business_by_name(business_name, context)

            # If no specific business found, use first available business as fallback
            if not business and context.get("businesses"):
                business = context["businesses"][0]
                self.logger.info(f"No specific business found for '{business_name}', using fallback: {business['name']}")

            return {
                "action": "create_order",
                "business_id": business["id"] if business else None,
                "customer_name": slots.get("customer_name"),
                "phone": slots.get("phone"),
                "items": slots.get("items", ""),
                "delivery_method": slots.get("delivery_method", "pickup"),
                "delivery_address": slots.get("delivery_address", ""),
                "special_instructions": slots.get("special_instructions", ""),
                "business_category": business.get("category") if business else "General"
            }

        elif intent == "information":
            return {
                "action": "get_information",
                "business_name": slots.get("business_name"),
                "topic": slots.get("topic", "general"),
                "business_category": None  # Will be determined by RAG
            }

        return {}

    def _find_business_by_name(self, business_name: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find business by name with multiple matching strategies"""
        if not business_name:
            return None

        businesses = context.get("businesses", [])
        if not businesses:
            return None

        business_name_lower = business_name.lower().strip()

        # Strategy 1: Exact match
        for biz in businesses:
            if biz["name"].lower() == business_name_lower:
                return biz

        # Strategy 2: Contains match (business name contains the extracted name)
        for biz in businesses:
            if business_name_lower in biz["name"].lower():
                return biz

        # Strategy 3: Extracted name contains business name
        for biz in businesses:
            if biz["name"].lower() in business_name_lower:
                return biz

        # Strategy 4: Fuzzy matching with common words
        business_words = set(business_name_lower.split())
        for biz in businesses:
            biz_words = set(biz["name"].lower().split())
            if business_words & biz_words:  # Intersection of words
                return biz

        return None
