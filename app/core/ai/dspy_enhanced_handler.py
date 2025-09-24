"""
DSPy Enhanced AI Handler
Integrates DSPy optimization with existing AI handlers
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

import dspy
from app.core.ai.base_handler import BaseAIHandler
from app.core.ai.types import RichContext, ChatContext
from app.core.dspy.config import get_dspy_manager
from app.core.dspy.base_modules import (
    IntentDetectionModule,
    ResponseGenerationModule,
    BusinessSpecificIntentModule
)
from app.core.dspy.enhanced_conversation_engine import DSPyEnhancedConversationEngine

logger = logging.getLogger(__name__)


class DSPyEnhancedAIHandler(BaseAIHandler):
    """Enhanced AI handler with DSPy optimization capabilities"""
    
    def __init__(self, supabase=None):
        super().__init__(supabase)
        
        # Initialize DSPy components
        self.dspy_manager = get_dspy_manager()
        self.conversation_engine = DSPyEnhancedConversationEngine()
        
        # DSPy modules
        self.intent_module = IntentDetectionModule()
        self.response_module = ResponseGenerationModule()
        self.business_modules = {}
        
        # Performance tracking
        self.performance_metrics = {
            "total_requests": 0,
            "dspy_successes": 0,
            "dspy_failures": 0,
            "average_confidence": 0.0,
            "optimization_count": 0
        }
        
        logger.info("✅ DSPy Enhanced AI Handler initialized")
    
    async def process_message_with_dspy(
        self,
        message: str,
        session_id: str,
        business_id: Optional[int] = None,
        user_id: Optional[str] = None,
        chat_context: ChatContext = ChatContext.DEDICATED,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process message using DSPy-enhanced pipeline"""
        
        self.performance_metrics["total_requests"] += 1
        
        try:
            # Build rich context
            context = RichContext(
                chat_context=chat_context,
                session_id=session_id,
                user_message=message,
                business_id=business_id,
                user_id=user_id,
                db=self.supabase
            )
            
            # Enhance context with additional data
            if additional_context:
                context.additional_context = additional_context
            
            # Step 1: DSPy Intent Detection
            intent_result = await self._dspy_intent_detection(context)
            
            # Step 2: DSPy Response Generation
            response_result = await self._dspy_response_generation(context, intent_result)
            
            # Step 3: Save conversation with DSPy metadata
            await self._save_dspy_conversation(context, response_result, intent_result)
            
            # Update performance metrics
            self.performance_metrics["dspy_successes"] += 1
            self._update_confidence_metrics(intent_result, response_result)
            
            return {
                "message": response_result["response"],
                "success": True,
                "chat_context": chat_context.value,
                "business_id": business_id,
                "session_id": session_id,
                "dspy_metadata": {
                    "intent": intent_result,
                    "response_confidence": response_result.get("confidence", 0.0),
                    "optimization_used": True,
                    "timestamp": datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"DSPy enhanced processing failed: {e}")
            self.performance_metrics["dspy_failures"] += 1
            
            # Fallback to standard processing
            return await self._fallback_processing(message, session_id, business_id, user_id, chat_context)
    
    async def _dspy_intent_detection(self, context: RichContext) -> Dict[str, Any]:
        """Enhanced intent detection using DSPy"""
        try:
            # Prepare context for DSPy
            conversation_history = self._format_conversation_history(context.conversation_history)
            business_context = self._build_business_context_string(context)
            
            # Use business-specific module if available
            business_category = getattr(context, 'business_category', 'local_services')
            if business_category not in self.business_modules:
                self.business_modules[business_category] = BusinessSpecificIntentModule(business_category)
            
            intent_module = self.business_modules[business_category]
            
            # Get DSPy prediction
            prediction = intent_module.forward(
                message=context.user_message,
                conversation_history=conversation_history,
                business_context=business_context
            )
            
            return {
                "intent": prediction.intent,
                "confidence": prediction.confidence,
                "reasoning": prediction.reasoning,
                "requires_booking": prediction.requires_booking,
                "business_category": prediction.business_category,
                "method": "dspy_enhanced"
            }
            
        except Exception as e:
            logger.warning(f"DSPy intent detection failed, using fallback: {e}")
            return {
                "intent": "general",
                "confidence": 0.5,
                "reasoning": "Fallback intent detection",
                "requires_booking": False,
                "business_category": "local_services",
                "method": "fallback"
            }
    
    async def _dspy_response_generation(self, context: RichContext, intent_result: Dict[str, Any]) -> Dict[str, Any]:
        """Enhanced response generation using DSPy"""
        try:
            # Prepare context
            conversation_history = self._format_conversation_history(context.conversation_history)
            business_context = self._build_business_context_string(context)
            agent_context = self._determine_agent_context(intent_result["intent"], context.chat_context)
            
            # Generate response using DSPy
            prediction = self.response_module.forward(
                user_message=context.user_message,
                conversation_history=conversation_history,
                business_context=business_context,
                agent_context=agent_context,
                intent=intent_result["intent"]
            )
            
            return {
                "response": prediction.response,
                "action_items": prediction.action_items,
                "confidence": prediction.confidence,
                "requires_human": prediction.requires_human,
                "method": "dspy_enhanced"
            }
            
        except Exception as e:
            logger.warning(f"DSPy response generation failed, using fallback: {e}")
            
            # Fallback response generation
            fallback_response = await self._generate_fallback_response(context, intent_result)
            return {
                "response": fallback_response,
                "action_items": "Continue conversation",
                "confidence": 0.6,
                "requires_human": False,
                "method": "fallback"
            }
    
    async def _generate_fallback_response(self, context: RichContext, intent_result: Dict[str, Any]) -> str:
        """Generate fallback response using traditional method"""
        try:
            # Use the original AI response method as fallback
            prompt = self.build_prompt(context)
            return await self.get_ai_response(prompt)
        except Exception as e:
            logger.error(f"Fallback response generation failed: {e}")
            return "I'd be happy to help you. Could you please provide more details about what you're looking for?"
    
    def _format_conversation_history(self, history: Optional[List[Dict[str, Any]]]) -> str:
        """Format conversation history for DSPy"""
        if not history:
            return "No previous conversation"
        
        formatted_history = []
        for entry in history[-6:]:  # Last 6 messages
            role = entry.get('role', 'unknown')
            content = entry.get('content', '')
            formatted_history.append(f"{role}: {content}")
        
        return "\n".join(formatted_history)
    
    def _build_business_context_string(self, context: RichContext) -> str:
        """Build business context string for DSPy"""
        context_parts = []
        
        if hasattr(context, 'current_business') and context.current_business:
            business = context.current_business
            context_parts.append(f"Business: {business.get('name', 'Unknown')}")
            context_parts.append(f"Category: {business.get('category', 'General')}")
            context_parts.append(f"Description: {business.get('description', 'Business services')}")
        
        if hasattr(context, 'business_menu') and context.business_menu:
            menu_items = [f"{item['name']} - ${item['price']}" for item in context.business_menu[:5]]
            context_parts.append(f"Services: {', '.join(menu_items)}")
        
        context_parts.append(f"Chat Context: {context.chat_context.value}")
        
        return " | ".join(context_parts) if context_parts else "General business context"
    
    def _determine_agent_context(self, intent: str, chat_context: ChatContext) -> str:
        """Determine agent context based on intent and chat context"""
        if chat_context == ChatContext.DEDICATED:
            return "Business-specific customer service representative with detailed knowledge of services and booking capabilities"
        elif chat_context == ChatContext.DASHBOARD:
            return "Business analytics and dashboard specialist with expertise in data interpretation and business insights"
        else:
            # Global context
            intent_contexts = {
                "booking": "Reservation and appointment specialist with booking expertise",
                "order": "Order processing specialist with product and service knowledge",
                "discovery": "Business discovery specialist with local knowledge and recommendations",
                "support": "Customer support specialist with problem-solving capabilities",
                "general": "General customer service representative with broad knowledge"
            }
            return intent_contexts.get(intent, "General assistant with helpful capabilities")
    
    async def _save_dspy_conversation(self, context: RichContext, response_result: Dict[str, Any], intent_result: Dict[str, Any]):
        """Save conversation with DSPy metadata"""
        try:
            # Enhanced conversation saving with DSPy metadata
            if not context.db:
                logger.warning("No database connection available for saving conversation")
                return
            
            # Prepare enhanced payloads
            user_msg = {
                "session_id": context.session_id,
                "business_id": context.business_id,
                "content": context.user_message,
                "sender_type": "customer",
                "role": "user",
                "chat_context": context.chat_context.value,
                "created_at": datetime.utcnow().isoformat(),
                "dspy_metadata": {
                    "intent_detected": intent_result["intent"],
                    "intent_confidence": intent_result["confidence"],
                    "intent_method": intent_result["method"]
                }
            }
            
            assistant_msg = {
                "session_id": context.session_id,
                "business_id": context.business_id,
                "content": response_result["response"],
                "sender_type": "assistant",
                "role": "assistant",
                "chat_context": context.chat_context.value,
                "created_at": datetime.utcnow().isoformat(),
                "dspy_metadata": {
                    "response_confidence": response_result["confidence"],
                    "response_method": response_result["method"],
                    "action_items": response_result.get("action_items", ""),
                    "requires_human": response_result.get("requires_human", False)
                }
            }
            
            # Insert with enhanced metadata
            context.db.table("messages").insert(user_msg).execute()
            context.db.table("messages").insert(assistant_msg).execute()
            
            logger.debug("Saved DSPy-enhanced conversation to database")
            
        except Exception as e:
            logger.error(f"Failed to save DSPy conversation: {e}")
    
    async def _fallback_processing(self, message: str, session_id: str, business_id: Optional[int], 
                                 user_id: Optional[str], chat_context: ChatContext) -> Dict[str, Any]:
        """Fallback to standard processing when DSPy fails"""
        try:
            # Use original processing method
            if chat_context == ChatContext.DEDICATED:
                from app.services.ai.dedicated_ai_handler import DedicatedAIHandler
                handler = DedicatedAIHandler(self.supabase)
                return await handler.process_message(message, session_id, business_id, user_id)
            else:
                # Use base handler
                context = RichContext(
                    chat_context=chat_context,
                    session_id=session_id,
                    user_message=message,
                    business_id=business_id,
                    user_id=user_id,
                    db=self.supabase
                )
                
                prompt = self.build_prompt(context)
                response = await self.get_ai_response(prompt)
                await self.save_conversation(context, response)
                
                return {
                    "message": response,
                    "success": True,
                    "chat_context": chat_context.value,
                    "fallback": True
                }
                
        except Exception as e:
            logger.error(f"Fallback processing failed: {e}")
            return {
                "message": "I apologize, but I'm having trouble processing your request right now. Please try again.",
                "success": False,
                "error": str(e)
            }
    
    def _update_confidence_metrics(self, intent_result: Dict[str, Any], response_result: Dict[str, Any]):
        """Update performance metrics with confidence scores"""
        intent_confidence = intent_result.get("confidence", 0.0)
        response_confidence = response_result.get("confidence", 0.0)
        
        # Calculate running average
        current_avg = self.performance_metrics["average_confidence"]
        total_requests = self.performance_metrics["total_requests"]
        
        new_confidence = (intent_confidence + response_confidence) / 2
        self.performance_metrics["average_confidence"] = (
            (current_avg * (total_requests - 1) + new_confidence) / total_requests
        )
    
    def build_prompt(self, context: RichContext) -> str:
        """Enhanced prompt building with DSPy insights"""
        # This maintains compatibility with the base handler
        # while potentially incorporating DSPy insights in the future
        
        lines = [
            f"You are an AI assistant helping with {context.chat_context.value} chat.",
            f"Current time: {context.current_time.strftime('%Y-%m-%d %H:%M')}",
            ""
        ]
        
        if hasattr(context, 'current_business') and context.current_business:
            lines.append(f"## Business: {context.current_business['name']}")
            lines.append(f"**Category**: {context.current_business.get('category', 'General')}")
            lines.append(f"**Description**: {context.current_business.get('description', 'Business services')}")
            lines.append("")
        
        if hasattr(context, 'business_menu') and context.business_menu:
            lines.append("## Available Services")
            for item in context.business_menu[:8]:
                lines.append(f"• **{item['name']}** - ${item['price']} ({item.get('description', 'Service')})")
            lines.append("")
        
        if context.conversation_history:
            lines.append("## Recent Conversation")
            for entry in context.conversation_history[-6:]:
                lines.append(f"{entry['role']}: {entry['content']}")
            lines.append("")
        
        lines.extend([
            f"## Customer Message\n{context.user_message}",
            "",
            "## Your Response",
            "Be helpful, professional, and assist with inquiries, bookings, and orders. Use DSPy-enhanced understanding when available."
        ])
        
        return "\n".join(lines)
    
    async def optimize_dspy_modules(self) -> Dict[str, Any]:
        """Trigger DSPy module optimization"""
        try:
            result = await self.conversation_engine.optimize_modules()
            if result.get("success"):
                self.performance_metrics["optimization_count"] += 1
            return result
        except Exception as e:
            logger.error(f"DSPy optimization failed: {e}")
            return {"success": False, "error": str(e)}
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get DSPy performance metrics"""
        success_rate = (
            self.performance_metrics["dspy_successes"] / 
            max(self.performance_metrics["total_requests"], 1)
        )
        
        return {
            **self.performance_metrics,
            "success_rate": success_rate,
            "failure_rate": 1 - success_rate,
            "optimization_status": self.conversation_engine.get_optimization_status()
        }
    
    def get_dspy_status(self) -> Dict[str, Any]:
        """Get DSPy system status"""
        return {
            "dspy_initialized": self.dspy_manager._initialized,
            "modules_loaded": {
                "intent_detection": self.intent_module is not None,
                "response_generation": self.response_module is not None,
                "conversation_engine": self.conversation_engine is not None
            },
            "business_modules_count": len(self.business_modules),
            "performance_metrics": self.get_performance_metrics(),
            "timestamp": datetime.now().isoformat()
        }
