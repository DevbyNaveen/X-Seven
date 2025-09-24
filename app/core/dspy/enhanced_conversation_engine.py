"""
DSPy-Enhanced Conversation Engine
Integrates DSPy modules with LangGraph conversation flows
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

import dspy
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .config import get_dspy_manager
from .base_modules import (
    IntentDetectionModule,
    AgentRoutingModule, 
    ResponseGenerationModule,
    ConversationSummaryModule,
    BusinessSpecificIntentModule
)
from .optimizers import DSPyOptimizer, OptimizationConfig
from app.api.v1.conversation_flow_engine import ConversationState, ConversationStage

logger = logging.getLogger(__name__)


@dataclass
class DSPyConversationState(ConversationState):
    """Enhanced conversation state with DSPy predictions"""
    dspy_predictions: Dict[str, Any] = None
    optimization_metadata: Dict[str, Any] = None
    confidence_scores: Dict[str, float] = None
    
    def __post_init__(self):
        if self.dspy_predictions is None:
            self.dspy_predictions = {}
        if self.optimization_metadata is None:
            self.optimization_metadata = {}
        if self.confidence_scores is None:
            self.confidence_scores = {}


class DSPyEnhancedConversationEngine:
    """LangGraph conversation engine enhanced with DSPy optimization"""
    
    def __init__(self, config=None, enable_optimization: bool = True):
        self.config = config
        self.enable_optimization = enable_optimization
        
        # Initialize DSPy
        self.dspy_manager = get_dspy_manager()
        
        # Initialize DSPy modules
        self.intent_module = IntentDetectionModule()
        self.routing_module = AgentRoutingModule()
        self.response_module = ResponseGenerationModule()
        self.summary_module = ConversationSummaryModule()
        
        # Business-specific modules
        self.business_intent_modules = {}
        
        # Optimizer
        if enable_optimization:
            opt_config = OptimizationConfig()
            self.optimizer = DSPyOptimizer(opt_config)
        else:
            self.optimizer = None
        
        # Memory and state
        self.memory = MemorySaver()
        self.conversations: Dict[str, DSPyConversationState] = {}
        
        # Build enhanced flow graph
        self.flow_graph = self._build_enhanced_conversation_graph()
        
        # Optimization status
        self.modules_optimized = False
        self.optimization_in_progress = False
    
    def _build_enhanced_conversation_graph(self) -> StateGraph:
        """Build DSPy-enhanced conversation flow graph"""
        graph = StateGraph(DSPyConversationState)
        
        # Add enhanced nodes
        graph.add_node("dspy_greeting", self._dspy_greeting_node)
        graph.add_node("dspy_intent_detection", self._dspy_intent_detection_node)
        graph.add_node("dspy_information_gathering", self._dspy_information_gathering_node)
        graph.add_node("dspy_agent_routing", self._dspy_agent_routing_node)
        graph.add_node("dspy_response_generation", self._dspy_response_generation_node)
        graph.add_node("dspy_confirmation", self._dspy_confirmation_node)
        graph.add_node("dspy_workflow_trigger", self._dspy_workflow_trigger_node)
        graph.add_node("dspy_completion", self._dspy_completion_node)
        graph.add_node("dspy_error_recovery", self._dspy_error_recovery_node)
        
        # Define enhanced flow
        graph.add_edge("dspy_greeting", "dspy_intent_detection")
        graph.add_edge("dspy_intent_detection", "dspy_information_gathering")
        graph.add_edge("dspy_information_gathering", "dspy_agent_routing")
        graph.add_edge("dspy_agent_routing", "dspy_response_generation")
        graph.add_edge("dspy_response_generation", "dspy_confirmation")
        graph.add_edge("dspy_confirmation", "dspy_workflow_trigger")
        graph.add_edge("dspy_workflow_trigger", "dspy_completion")
        graph.add_edge("dspy_error_recovery", "dspy_intent_detection")
        
        # Add conditional edges for error handling
        graph.add_conditional_edges(
            "dspy_response_generation",
            self._should_recover_dspy,
            {
                "recover": "dspy_error_recovery",
                "continue": "dspy_confirmation"
            }
        )
        
        # Set entry point
        graph.set_entry_point("dspy_greeting")
        
        return graph.compile(checkpointer=self.memory)
    
    async def _dspy_greeting_node(self, state: DSPyConversationState) -> DSPyConversationState:
        """Enhanced greeting with DSPy optimization"""
        logger.info(f"DSPy greeting node for conversation {state.conversation_id}")
        
        state.current_stage = ConversationStage.GREETING.value
        state.updated_at = datetime.now()
        
        # Use DSPy for greeting generation if this is a returning conversation
        if state.turn_count > 0 and state.conversation_history:
            try:
                # Generate contextual greeting
                greeting_prompt = f"Generate a contextual greeting for a returning customer. Previous conversation: {state.conversation_history[-1] if state.conversation_history else 'None'}"
                
                # Simple DSPy prediction for greeting
                greeting_prediction = dspy.Predict("context -> greeting")(context=greeting_prompt)
                greeting_message = greeting_prediction.greeting
                
                state.confidence_scores["greeting"] = 0.8
                
            except Exception as e:
                logger.warning(f"DSPy greeting generation failed: {e}")
                greeting_message = "Hello! I'm here to help you. What can I assist you with today?"
                state.confidence_scores["greeting"] = 0.6
        else:
            greeting_message = "Hello! I'm here to help you. What can I assist you with today?"
            state.confidence_scores["greeting"] = 0.8
        
        if state.turn_count == 0:
            greeting_msg = {
                "role": "assistant",
                "content": greeting_message,
                "timestamp": datetime.now().isoformat(),
                "stage": "greeting",
                "confidence": state.confidence_scores.get("greeting", 0.8)
            }
            state.messages.append(greeting_msg)
        
        return state
    
    async def _dspy_intent_detection_node(self, state: DSPyConversationState) -> DSPyConversationState:
        """Enhanced intent detection using DSPy"""
        logger.info(f"DSPy intent detection for conversation {state.conversation_id}")
        
        state.current_stage = ConversationStage.INTENT_DETECTION.value
        state.updated_at = datetime.now()
        
        try:
            # Get latest user message
            user_messages = [msg for msg in state.messages if msg.get("role") == "user"]
            if not user_messages:
                return state
            
            latest_message = user_messages[-1]["content"]
            
            # Prepare context
            conversation_history = "\n".join([
                f"{msg['role']}: {msg['content']}" 
                for msg in state.messages[-6:] if msg.get("role") in ["user", "assistant"]
            ])
            
            business_context = self._build_business_context(state)
            
            # Use business-specific intent module if available
            business_category = state.context.get("business_category", "local_services")
            if business_category not in self.business_intent_modules:
                self.business_intent_modules[business_category] = BusinessSpecificIntentModule(business_category)
            
            intent_module = self.business_intent_modules[business_category]
            
            # Get DSPy prediction
            intent_prediction = intent_module.forward(
                message=latest_message,
                conversation_history=conversation_history,
                business_context=business_context
            )
            
            # Store DSPy prediction
            state.dspy_predictions["intent_detection"] = {
                "intent": intent_prediction.intent,
                "confidence": intent_prediction.confidence,
                "reasoning": intent_prediction.reasoning,
                "requires_booking": intent_prediction.requires_booking,
                "business_category": intent_prediction.business_category,
                "timestamp": datetime.now().isoformat()
            }
            
            # Update context with DSPy results
            state.context.update({
                "detected_intent": intent_prediction.intent,
                "intent_confidence": intent_prediction.confidence,
                "requires_booking": intent_prediction.requires_booking,
                "business_category": intent_prediction.business_category,
                "intent_reasoning": intent_prediction.reasoning
            })
            
            state.confidence_scores["intent_detection"] = intent_prediction.confidence
            
            logger.info(f"DSPy detected intent: {intent_prediction.intent} (confidence: {intent_prediction.confidence:.2f})")
            
        except Exception as e:
            logger.error(f"DSPy intent detection failed: {e}")
            # Fallback to basic intent detection
            state.context["detected_intent"] = "general"
            state.context["intent_confidence"] = 0.5
            state.confidence_scores["intent_detection"] = 0.5
        
        return state
    
    async def _dspy_information_gathering_node(self, state: DSPyConversationState) -> DSPyConversationState:
        """Enhanced information gathering with DSPy insights"""
        logger.info(f"DSPy information gathering for conversation {state.conversation_id}")
        
        state.current_stage = ConversationStage.INFORMATION_GATHERING.value
        state.updated_at = datetime.now()
        
        # Use DSPy prediction to determine required information
        detected_intent = state.context.get("detected_intent", "general")
        
        # Enhanced information requirements based on DSPy predictions
        if detected_intent == "booking" and state.context.get("requires_booking", False):
            required_info = ["date", "time", "party_size", "contact", "special_requests"]
        elif detected_intent == "order":
            required_info = ["items", "quantity", "delivery_method", "contact"]
        elif detected_intent == "discovery":
            required_info = ["location", "preferences", "budget_range"]
        else:
            required_info = []
        
        # Check what information we already have
        missing_info = []
        for info_key in required_info:
            if info_key not in state.context:
                missing_info.append(info_key)
        
        state.context["missing_information"] = missing_info
        state.context["information_complete"] = len(missing_info) == 0
        state.context["required_information"] = required_info
        
        return state
    
    async def _dspy_agent_routing_node(self, state: DSPyConversationState) -> DSPyConversationState:
        """Enhanced agent routing using DSPy"""
        logger.info(f"DSPy agent routing for conversation {state.conversation_id}")
        
        state.current_stage = ConversationStage.AGENT_ROUTING.value
        state.updated_at = datetime.now()
        
        try:
            # Prepare routing context
            intent = state.context.get("detected_intent", "general")
            business_context = self._build_business_context(state)
            conversation_type = state.conversation_type
            
            user_messages = [msg for msg in state.messages if msg.get("role") == "user"]
            user_message = user_messages[-1]["content"] if user_messages else ""
            
            available_agents = [
                "RestaurantAgent", "BeautyAgent", "AutomotiveAgent",
                "HealthAgent", "LocalServicesAgent", "GeneralPurposeAgent",
                "BusinessAnalyticsAgent", "VoiceEnhancementAgent"
            ]
            
            # Get DSPy routing prediction
            routing_prediction = self.routing_module.forward(
                intent=intent,
                business_context=business_context,
                conversation_type=conversation_type,
                user_message=user_message,
                available_agents=available_agents
            )
            
            # Store DSPy prediction
            state.dspy_predictions["agent_routing"] = {
                "selected_agent": routing_prediction.selected_agent,
                "routing_reason": routing_prediction.routing_reason,
                "confidence": routing_prediction.confidence,
                "fallback_agent": routing_prediction.fallback_agent,
                "timestamp": datetime.now().isoformat()
            }
            
            # Update context
            state.context["selected_agent"] = routing_prediction.selected_agent
            state.context["routing_reason"] = routing_prediction.routing_reason
            state.context["routing_confidence"] = routing_prediction.confidence
            
            state.agent_history.append(routing_prediction.selected_agent)
            state.confidence_scores["agent_routing"] = routing_prediction.confidence
            
            logger.info(f"DSPy routed to: {routing_prediction.selected_agent} (confidence: {routing_prediction.confidence:.2f})")
            
        except Exception as e:
            logger.error(f"DSPy agent routing failed: {e}")
            # Fallback routing
            state.context["selected_agent"] = "GeneralPurposeAgent"
            state.context["routing_reason"] = "Fallback due to routing error"
            state.confidence_scores["agent_routing"] = 0.5
        
        return state
    
    async def _dspy_response_generation_node(self, state: DSPyConversationState) -> DSPyConversationState:
        """Enhanced response generation using DSPy"""
        logger.info(f"DSPy response generation for conversation {state.conversation_id}")
        
        state.current_stage = ConversationStage.PROCESSING.value
        state.updated_at = datetime.now()
        
        try:
            # Prepare response generation context
            user_messages = [msg for msg in state.messages if msg.get("role") == "user"]
            user_message = user_messages[-1]["content"] if user_messages else ""
            
            conversation_history = "\n".join([
                f"{msg['role']}: {msg['content']}" 
                for msg in state.messages[-8:] if msg.get("role") in ["user", "assistant"]
            ])
            
            business_context = self._build_business_context(state)
            agent_context = self._build_agent_context(state.context.get("selected_agent", "GeneralPurposeAgent"))
            intent = state.context.get("detected_intent", "general")
            
            # Generate response using DSPy
            response_prediction = self.response_module.forward(
                user_message=user_message,
                conversation_history=conversation_history,
                business_context=business_context,
                agent_context=agent_context,
                intent=intent
            )
            
            # Store DSPy prediction
            state.dspy_predictions["response_generation"] = {
                "response": response_prediction.response,
                "action_items": response_prediction.action_items,
                "confidence": response_prediction.confidence,
                "requires_human": response_prediction.requires_human,
                "timestamp": datetime.now().isoformat()
            }
            
            # Update context
            state.context["generated_response"] = response_prediction.response
            state.context["action_items"] = response_prediction.action_items
            state.context["response_confidence"] = response_prediction.confidence
            state.context["requires_human"] = response_prediction.requires_human
            
            state.confidence_scores["response_generation"] = response_prediction.confidence
            
            # Add response to messages
            response_msg = {
                "role": "assistant",
                "content": response_prediction.response,
                "timestamp": datetime.now().isoformat(),
                "stage": "processing",
                "confidence": response_prediction.confidence,
                "action_items": response_prediction.action_items,
                "agent": state.context.get("selected_agent", "GeneralPurposeAgent")
            }
            state.messages.append(response_msg)
            
            logger.info(f"DSPy generated response (confidence: {response_prediction.confidence:.2f})")
            
        except Exception as e:
            logger.error(f"DSPy response generation failed: {e}")
            # Fallback response
            fallback_response = "I'd be happy to help you. Could you please provide more details about what you're looking for?"
            state.context["generated_response"] = fallback_response
            state.confidence_scores["response_generation"] = 0.4
            
            response_msg = {
                "role": "assistant",
                "content": fallback_response,
                "timestamp": datetime.now().isoformat(),
                "stage": "processing",
                "confidence": 0.4,
                "fallback": True
            }
            state.messages.append(response_msg)
        
        return state
    
    async def _dspy_confirmation_node(self, state: DSPyConversationState) -> DSPyConversationState:
        """Enhanced confirmation with DSPy insights"""
        logger.info(f"DSPy confirmation for conversation {state.conversation_id}")
        
        state.current_stage = ConversationStage.CONFIRMATION.value
        state.updated_at = datetime.now()
        
        # Use DSPy predictions to determine confirmation needs
        requires_booking = state.context.get("requires_booking", False)
        intent = state.context.get("detected_intent", "general")
        requires_human = state.context.get("requires_human", False)
        
        needs_confirmation = (
            requires_booking or 
            intent in ["booking", "order", "appointment"] or
            requires_human
        )
        
        state.context["needs_confirmation"] = needs_confirmation
        
        return state
    
    async def _dspy_workflow_trigger_node(self, state: DSPyConversationState) -> DSPyConversationState:
        """Enhanced workflow triggering with DSPy insights"""
        logger.info(f"DSPy workflow trigger for conversation {state.conversation_id}")
        
        state.current_stage = ConversationStage.WORKFLOW_TRIGGER.value
        state.updated_at = datetime.now()
        
        # Use DSPy predictions to determine workflow needs
        requires_booking = state.context.get("requires_booking", False)
        intent = state.context.get("detected_intent", "general")
        
        workflow_type = None
        if requires_booking and intent == "booking":
            workflow_type = "appointment_workflow"
        elif intent == "order":
            workflow_type = "order_workflow"
        elif state.context.get("requires_human", False):
            workflow_type = "human_escalation_workflow"
        
        if workflow_type:
            state.context["workflow_type"] = workflow_type
            state.context["workflow_data"] = self._prepare_workflow_data(state)
            state.context["workflow_triggered"] = True
        else:
            state.context["workflow_triggered"] = False
        
        return state
    
    async def _dspy_completion_node(self, state: DSPyConversationState) -> DSPyConversationState:
        """Enhanced completion with DSPy summary"""
        logger.info(f"DSPy completion for conversation {state.conversation_id}")
        
        state.current_stage = ConversationStage.COMPLETION.value
        state.updated_at = datetime.now()
        state.turn_count += 1
        
        # Generate conversation summary using DSPy
        try:
            conversation_history = "\n".join([
                f"{msg['role']}: {msg['content']}" 
                for msg in state.messages if msg.get("role") in ["user", "assistant"]
            ])
            
            business_context = self._build_business_context(state)
            key_intents = ", ".join(set([
                pred.get("intent", "general") 
                for pred in [state.dspy_predictions.get("intent_detection", {})]
            ]))
            
            summary_prediction = self.summary_module.forward(
                conversation_history=conversation_history,
                business_context=business_context,
                key_intents=key_intents
            )
            
            state.context["conversation_summary"] = summary_prediction.summary
            state.context["key_points"] = summary_prediction.key_points
            state.context["next_steps"] = summary_prediction.next_steps
            state.context["sentiment"] = summary_prediction.sentiment
            
        except Exception as e:
            logger.warning(f"DSPy summary generation failed: {e}")
        
        # Calculate overall confidence
        confidence_scores = list(state.confidence_scores.values())
        overall_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.5
        state.context["overall_confidence"] = overall_confidence
        
        state.context["ready_for_response"] = True
        
        return state
    
    async def _dspy_error_recovery_node(self, state: DSPyConversationState) -> DSPyConversationState:
        """Enhanced error recovery with DSPy"""
        logger.info(f"DSPy error recovery for conversation {state.conversation_id}")
        
        state.current_stage = ConversationStage.ERROR_RECOVERY.value
        state.updated_at = datetime.now()
        
        # Use DSPy to generate recovery response
        try:
            error_context = state.context.get("error_message", "Unknown error occurred")
            recovery_prompt = f"Generate a helpful recovery response for this error: {error_context}"
            
            recovery_prediction = dspy.Predict("error_context -> recovery_response")(error_context=recovery_prompt)
            
            state.context["recovery_response"] = recovery_prediction.recovery_response
            state.context["recovery_attempted"] = True
            state.context["recovery_timestamp"] = datetime.now().isoformat()
            
        except Exception as e:
            logger.error(f"DSPy error recovery failed: {e}")
            state.context["recovery_response"] = "I apologize for the error. Let me try to help you again."
        
        return state
    
    def _should_recover_dspy(self, state: DSPyConversationState) -> str:
        """Enhanced recovery decision using DSPy confidence scores"""
        # Check if any confidence scores are too low
        min_confidence = min(state.confidence_scores.values()) if state.confidence_scores else 1.0
        
        if min_confidence < 0.3 or state.context.get("error_occurred", False):
            return "recover"
        return "continue"
    
    def _build_business_context(self, state: DSPyConversationState) -> str:
        """Build business context string for DSPy"""
        context_parts = []
        
        if state.business_id:
            context_parts.append(f"Business ID: {state.business_id}")
        
        if state.conversation_type:
            context_parts.append(f"Conversation Type: {state.conversation_type}")
        
        business_category = state.context.get("business_category", "local_services")
        context_parts.append(f"Business Category: {business_category}")
        
        return " | ".join(context_parts) if context_parts else "General business context"
    
    def _build_agent_context(self, agent_name: str) -> str:
        """Build agent context string for DSPy"""
        agent_contexts = {
            "RestaurantAgent": "Restaurant and food service specialist with expertise in dining, menus, and reservations",
            "BeautyAgent": "Beauty and wellness specialist with expertise in salon services and treatments",
            "AutomotiveAgent": "Automotive service specialist with expertise in car maintenance and repairs",
            "HealthAgent": "Healthcare service specialist with expertise in medical appointments and services",
            "LocalServicesAgent": "Local services specialist with expertise in community businesses",
            "GeneralPurposeAgent": "General assistant with broad knowledge and helpful capabilities",
            "BusinessAnalyticsAgent": "Business analytics specialist with expertise in data and insights",
            "VoiceEnhancementAgent": "Voice interaction specialist optimized for audio communication"
        }
        
        return agent_contexts.get(agent_name, "General assistant capabilities")
    
    def _prepare_workflow_data(self, state: DSPyConversationState) -> Dict[str, Any]:
        """Prepare workflow data with DSPy insights"""
        return {
            "conversation_id": state.conversation_id,
            "user_id": state.user_id,
            "business_id": state.business_id,
            "context": state.context,
            "dspy_predictions": state.dspy_predictions,
            "confidence_scores": state.confidence_scores,
            "timestamp": datetime.now().isoformat()
        }
    
    # Public API methods
    
    async def create_conversation(self, conversation_type: str = "general",
                                initial_context: Dict[str, Any] = None,
                                user_id: str = None, business_id: str = None) -> str:
        """Create a new DSPy-enhanced conversation"""
        import uuid
        conversation_id = str(uuid.uuid4())
        
        state = DSPyConversationState(
            conversation_id=conversation_id,
            user_id=user_id,
            business_id=business_id,
            conversation_type=conversation_type,
            context=initial_context or {},
            created_at=datetime.now(),
            updated_at=datetime.now(),
            dspy_predictions={},
            confidence_scores={},
            optimization_metadata={}
        )
        
        self.conversations[conversation_id] = state
        logger.info(f"Created DSPy-enhanced conversation {conversation_id}")
        
        return conversation_id
    
    async def process_message(self, conversation_id: str, message: str,
                            user_id: str = None) -> DSPyConversationState:
        """Process message through DSPy-enhanced flow"""
        if conversation_id not in self.conversations:
            raise ValueError(f"Conversation {conversation_id} not found")
        
        state = self.conversations[conversation_id]
        
        # Add user message
        user_msg = {
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id
        }
        state.messages.append(user_msg)
        
        # Process through DSPy-enhanced graph
        try:
            result = await self.flow_graph.ainvoke(
                state,
                config={"configurable": {"thread_id": conversation_id}}
            )
            
            self.conversations[conversation_id] = result
            return result
            
        except Exception as e:
            logger.error(f"DSPy conversation processing failed: {e}")
            state.context["error_occurred"] = True
            state.context["error_message"] = str(e)
            return state
    
    async def optimize_modules(self, force_optimization: bool = False) -> Dict[str, Any]:
        """Optimize DSPy modules using collected data"""
        if not self.optimizer:
            return {"error": "Optimization disabled"}
        
        if self.optimization_in_progress:
            return {"error": "Optimization already in progress"}
        
        if self.modules_optimized and not force_optimization:
            return {"message": "Modules already optimized. Use force_optimization=True to re-optimize"}
        
        self.optimization_in_progress = True
        
        try:
            logger.info("🚀 Starting DSPy module optimization...")
            
            # Optimize modules
            modules_to_optimize = {
                "intent_detection": self.intent_module,
                "agent_routing": self.routing_module,
                "response_generation": self.response_module
            }
            
            optimized_modules = await self.optimizer.optimize_full_pipeline(modules_to_optimize)
            
            # Update modules
            self.intent_module = optimized_modules["intent_detection"]
            self.routing_module = optimized_modules["agent_routing"]
            self.response_module = optimized_modules["response_generation"]
            
            self.modules_optimized = True
            
            # Get optimization stats
            stats = self.optimizer.get_optimization_stats()
            
            logger.info("✅ DSPy module optimization completed!")
            
            return {
                "success": True,
                "message": "DSPy modules optimized successfully",
                "stats": stats,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"DSPy optimization failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        
        finally:
            self.optimization_in_progress = False
    
    def get_optimization_status(self) -> Dict[str, Any]:
        """Get current optimization status"""
        return {
            "modules_optimized": self.modules_optimized,
            "optimization_in_progress": self.optimization_in_progress,
            "optimization_enabled": self.optimizer is not None,
            "optimization_history": self.optimizer.get_optimization_history() if self.optimizer else [],
            "confidence_stats": self._get_confidence_stats()
        }
    
    def _get_confidence_stats(self) -> Dict[str, Any]:
        """Get confidence statistics across conversations"""
        all_scores = []
        stage_scores = {}
        
        for conv in self.conversations.values():
            for stage, score in conv.confidence_scores.items():
                all_scores.append(score)
                if stage not in stage_scores:
                    stage_scores[stage] = []
                stage_scores[stage].append(score)
        
        if not all_scores:
            return {"message": "No confidence data available"}
        
        return {
            "overall_average": sum(all_scores) / len(all_scores),
            "total_predictions": len(all_scores),
            "stage_averages": {
                stage: sum(scores) / len(scores)
                for stage, scores in stage_scores.items()
            },
            "low_confidence_count": len([s for s in all_scores if s < 0.5])
        }
