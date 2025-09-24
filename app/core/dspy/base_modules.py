"""
DSPy Base Modules
Core DSPy modules for conversation processing
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

import dspy
from dspy import Signature, InputField, OutputField

logger = logging.getLogger(__name__)


# DSPy Signatures for different tasks
class IntentDetectionSignature(Signature):
    """Detect user intent from conversation message"""
    message: str = InputField(desc="User message to analyze")
    conversation_history: str = InputField(desc="Previous conversation context")
    business_context: str = InputField(desc="Business information and context")
    
    intent: str = OutputField(desc="Detected intent (booking, order, discovery, support, general)")
    confidence: float = OutputField(desc="Confidence score between 0.0 and 1.0")
    reasoning: str = OutputField(desc="Brief explanation of intent detection")
    requires_booking: bool = OutputField(desc="Whether the request requires booking functionality")
    business_category: str = OutputField(desc="Relevant business category for the request")


class AgentRoutingSignature(Signature):
    """Route conversation to appropriate agent"""
    intent: str = InputField(desc="Detected user intent")
    business_context: str = InputField(desc="Business information and context")
    conversation_type: str = InputField(desc="Type of conversation (dedicated, dashboard, global)")
    user_message: str = InputField(desc="Original user message")
    available_agents: str = InputField(desc="List of available agents and their capabilities")
    
    selected_agent: str = OutputField(desc="Name of the selected agent")
    routing_reason: str = OutputField(desc="Explanation for agent selection")
    confidence: float = OutputField(desc="Confidence in routing decision")
    fallback_agent: str = OutputField(desc="Backup agent if primary fails")


class ResponseGenerationSignature(Signature):
    """Generate contextual response for conversation"""
    user_message: str = InputField(desc="User's message")
    conversation_history: str = InputField(desc="Previous conversation context")
    business_context: str = InputField(desc="Business information and services")
    agent_context: str = InputField(desc="Selected agent's expertise and role")
    intent: str = InputField(desc="Detected user intent")
    
    response: str = OutputField(desc="Generated response to user")
    action_items: str = OutputField(desc="Any follow-up actions needed")
    confidence: float = OutputField(desc="Confidence in response quality")
    requires_human: bool = OutputField(desc="Whether human intervention is needed")


class ConversationSummarySignature(Signature):
    """Summarize conversation for context management"""
    conversation_history: str = InputField(desc="Full conversation history")
    business_context: str = InputField(desc="Business information")
    key_intents: str = InputField(desc="Main intents discussed")
    
    summary: str = OutputField(desc="Concise conversation summary")
    key_points: str = OutputField(desc="Important points and decisions")
    next_steps: str = OutputField(desc="Recommended next steps")
    sentiment: str = OutputField(desc="Overall conversation sentiment")


# DSPy Modules
class IntentDetectionModule(dspy.Module):
    """DSPy module for intent detection with optimization"""
    
    def __init__(self):
        super().__init__()
        self.intent_detector = dspy.ChainOfThought(IntentDetectionSignature)
    
    def forward(self, message: str, conversation_history: str = "", 
                business_context: str = "") -> dspy.Prediction:
        """Detect intent from user message"""
        try:
            prediction = self.intent_detector(
                message=message,
                conversation_history=conversation_history or "No previous conversation",
                business_context=business_context or "General business context"
            )
            
            # Validate and normalize outputs
            prediction.confidence = max(0.0, min(1.0, float(prediction.confidence)))
            prediction.intent = prediction.intent.lower().strip()
            
            return prediction
            
        except Exception as e:
            logger.error(f"Intent detection failed: {e}")
            # Return fallback prediction
            return dspy.Prediction(
                intent="general",
                confidence=0.5,
                reasoning="Fallback due to processing error",
                requires_booking=False,
                business_category="local_services"
            )


class AgentRoutingModule(dspy.Module):
    """DSPy module for intelligent agent routing"""
    
    def __init__(self):
        super().__init__()
        self.router = dspy.ChainOfThought(AgentRoutingSignature)
    
    def forward(self, intent: str, business_context: str = "", 
                conversation_type: str = "general", user_message: str = "",
                available_agents: List[str] = None) -> dspy.Prediction:
        """Route to appropriate agent based on context"""
        try:
            # Format available agents
            agents_list = available_agents or [
                "RestaurantAgent", "BeautyAgent", "AutomotiveAgent", 
                "HealthAgent", "LocalServicesAgent", "GeneralPurposeAgent"
            ]
            agents_str = ", ".join(agents_list)
            
            prediction = self.router(
                intent=intent,
                business_context=business_context or "General business",
                conversation_type=conversation_type,
                user_message=user_message,
                available_agents=agents_str
            )
            
            # Validate agent selection
            if prediction.selected_agent not in agents_list:
                prediction.selected_agent = "GeneralPurposeAgent"
                prediction.routing_reason = "Fallback to general agent"
            
            prediction.confidence = max(0.0, min(1.0, float(prediction.confidence)))
            
            return prediction
            
        except Exception as e:
            logger.error(f"Agent routing failed: {e}")
            return dspy.Prediction(
                selected_agent="GeneralPurposeAgent",
                routing_reason="Fallback due to routing error",
                confidence=0.5,
                fallback_agent="GeneralPurposeAgent"
            )


class ResponseGenerationModule(dspy.Module):
    """DSPy module for contextual response generation"""
    
    def __init__(self):
        super().__init__()
        self.generator = dspy.ChainOfThought(ResponseGenerationSignature)
    
    def forward(self, user_message: str, conversation_history: str = "",
                business_context: str = "", agent_context: str = "",
                intent: str = "general") -> dspy.Prediction:
        """Generate contextual response"""
        try:
            prediction = self.generator(
                user_message=user_message,
                conversation_history=conversation_history or "No previous conversation",
                business_context=business_context or "General business context",
                agent_context=agent_context or "General assistant capabilities",
                intent=intent
            )
            
            # Validate outputs
            prediction.confidence = max(0.0, min(1.0, float(prediction.confidence)))
            
            # Ensure response is not empty
            if not prediction.response or len(prediction.response.strip()) < 10:
                prediction.response = "I'd be happy to help you. Could you please provide more details about what you're looking for?"
                prediction.confidence = 0.6
            
            return prediction
            
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return dspy.Prediction(
                response="I apologize, but I'm having trouble processing your request right now. Please try again.",
                action_items="Retry request",
                confidence=0.3,
                requires_human=True
            )


class ConversationSummaryModule(dspy.Module):
    """DSPy module for conversation summarization"""
    
    def __init__(self):
        super().__init__()
        self.summarizer = dspy.ChainOfThought(ConversationSummarySignature)
    
    def forward(self, conversation_history: str, business_context: str = "",
                key_intents: str = "") -> dspy.Prediction:
        """Summarize conversation for context management"""
        try:
            prediction = self.summarizer(
                conversation_history=conversation_history,
                business_context=business_context or "General business",
                key_intents=key_intents or "General conversation"
            )
            
            return prediction
            
        except Exception as e:
            logger.error(f"Conversation summary failed: {e}")
            return dspy.Prediction(
                summary="Conversation in progress",
                key_points="User interaction ongoing",
                next_steps="Continue conversation",
                sentiment="neutral"
            )


# Enhanced modules with business-specific optimization
class BusinessSpecificIntentModule(dspy.Module):
    """Intent detection optimized for specific business categories"""
    
    def __init__(self, business_category: str):
        super().__init__()
        self.business_category = business_category
        self.intent_detector = dspy.ChainOfThought(IntentDetectionSignature)
        
        # Category-specific intent mappings
        self.category_intents = {
            "food_hospitality": ["booking", "order", "menu_inquiry", "dietary_restrictions"],
            "beauty_personal_care": ["booking", "service_inquiry", "stylist_request", "product_info"],
            "automotive_services": ["service_booking", "repair_inquiry", "maintenance", "emergency"],
            "health_medical": ["appointment", "service_inquiry", "insurance", "emergency"],
            "local_services": ["service_request", "availability", "pricing", "location"]
        }
    
    def forward(self, message: str, conversation_history: str = "",
                business_context: str = "") -> dspy.Prediction:
        """Detect intent with business category optimization"""
        # Add category-specific context
        enhanced_context = f"{business_context}\nBusiness Category: {self.business_category}\n"
        if self.business_category in self.category_intents:
            common_intents = ", ".join(self.category_intents[self.business_category])
            enhanced_context += f"Common intents for this category: {common_intents}"
        
        return self.intent_detector(
            message=message,
            conversation_history=conversation_history,
            business_context=enhanced_context
        )
