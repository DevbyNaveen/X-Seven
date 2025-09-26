"""
LangGraph Conversation Flow Engine
Manages stateful conversation flows with graph-based routing
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ConversationState(BaseModel):
    """State model for LangGraph conversations"""
    # Required fields first
    conversation_id: str

    # Fields with defaults
    user_id: Optional[str] = None
    business_id: Optional[str] = None
    conversation_type: str = "general"  # dedicated, dashboard, global
    current_stage: str = "greeting"
    context: Dict[str, Any] = field(default_factory=dict)
    messages: List[Dict[str, Any]] = field(default_factory=list)
    agent_history: List[str] = field(default_factory=list)
    turn_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConversationStage(Enum):
    """Conversation flow stages"""
    GREETING = "greeting"
    INTENT_DETECTION = "intent_detection"
    INFORMATION_GATHERING = "information_gathering"
    AGENT_ROUTING = "agent_routing"
    PROCESSING = "processing"
    CONFIRMATION = "confirmation"
    WORKFLOW_TRIGGER = "workflow_trigger"
    COMPLETION = "completion"
    ERROR_RECOVERY = "error_recovery"


@dataclass
class ConversationConfig:
    """Configuration for conversation flow engine"""
    max_turns: int = 50
    timeout_seconds: int = 300
    enable_persistence: bool = True
    enable_recovery: bool = True
    fallback_agent: str = "GeneralPurposeAgent"
    redis_ttl: int = 3600  # 1 hour
    max_context_size: int = 10000


class ConversationFlowEngine:
    """LangGraph-based conversation flow engine"""
    
    def __init__(self, config: ConversationConfig):
        self.config = config
        self.memory = MemorySaver()
        self.conversations: Dict[str, ConversationState] = {}
        self.flow_graph = self._build_conversation_graph()
        
    def _build_conversation_graph(self) -> StateGraph:
        """Build the LangGraph conversation flow"""
        
        # Define the graph state
        graph = StateGraph(ConversationState)
        
        # Add nodes for each conversation stage
        graph.add_node("greeting", self._greeting_node)
        graph.add_node("intent_detection", self._intent_detection_node)
        graph.add_node("information_gathering", self._information_gathering_node)
        graph.add_node("agent_routing", self._agent_routing_node)
        graph.add_node("processing", self._processing_node)
        graph.add_node("confirmation", self._confirmation_node)
        graph.add_node("workflow_trigger", self._workflow_trigger_node)
        graph.add_node("completion", self._completion_node)
        graph.add_node("error_recovery", self._error_recovery_node)
        
        # Define the flow edges
        graph.add_edge("greeting", "intent_detection")
        graph.add_edge("intent_detection", "information_gathering")
        graph.add_edge("information_gathering", "agent_routing")
        graph.add_edge("agent_routing", "processing")
        graph.add_edge("processing", "confirmation")
        graph.add_edge("confirmation", "workflow_trigger")
        graph.add_edge("workflow_trigger", "completion")
        graph.add_edge("error_recovery", "intent_detection")
        
        # Add conditional edges for error handling
        graph.add_conditional_edges(
            "processing",
            self._should_recover,
            {
                "recover": "error_recovery",
                "continue": "confirmation"
            }
        )
        
        # Set entry point
        graph.set_entry_point("greeting")
        
        # Compile the graph
        return graph.compile(checkpointer=self.memory)
    
    async def _greeting_node(self, state: ConversationState) -> ConversationState:
        """Handle initial greeting and setup"""
        logger.info(f"Greeting node for conversation {state.conversation_id}")
        
        state.current_stage = ConversationStage.GREETING.value
        state.updated_at = datetime.now()
        
        # Add greeting message if first interaction
        if state.turn_count == 0:
            greeting_msg = {
                "role": "assistant",
                "content": "Hello! I'm here to help you. What can I assist you with today?",
                "timestamp": datetime.now().isoformat(),
                "stage": "greeting"
            }
            state.messages.append(greeting_msg)
        
        return state
    
    async def _intent_detection_node(self, state: ConversationState) -> ConversationState:
        """Detect user intent and classify request"""
        logger.info(f"Intent detection for conversation {state.conversation_id}")
        
        state.current_stage = ConversationStage.INTENT_DETECTION.value
        state.updated_at = datetime.now()
        
        # Get the latest user message
        user_messages = [msg for msg in state.messages if msg.get("role") == "user"]
        if user_messages:
            latest_message = user_messages[-1]["content"]
            
            # Simple intent classification (can be enhanced with LLM)
            intent = self._classify_intent(latest_message)
            state.context["detected_intent"] = intent
            state.context["requires_booking"] = self._requires_booking(latest_message)
            state.context["business_category"] = self._detect_business_category(latest_message)
        
        return state
    
    async def _information_gathering_node(self, state: ConversationState) -> ConversationState:
        """Gather required information for processing"""
        logger.info(f"Information gathering for conversation {state.conversation_id}")
        
        state.current_stage = ConversationStage.INFORMATION_GATHERING.value
        state.updated_at = datetime.now()
        
        # Check if we have enough information
        required_info = self._get_required_information(state.context.get("detected_intent", "general"))
        missing_info = []
        
        for info_key in required_info:
            if info_key not in state.context:
                missing_info.append(info_key)
        
        state.context["missing_information"] = missing_info
        state.context["information_complete"] = len(missing_info) == 0
        
        return state
    
    async def _agent_routing_node(self, state: ConversationState) -> ConversationState:
        """Route to appropriate agent based on context"""
        logger.info(f"Agent routing for conversation {state.conversation_id}")
        
        state.current_stage = ConversationStage.AGENT_ROUTING.value
        state.updated_at = datetime.now()
        
        # Determine agent based on conversation type and context
        if state.conversation_type == "dedicated":
            # Use business-specific agent
            agent_type = self._get_business_agent(state.business_id)
        elif state.conversation_type == "dashboard":
            # Use dashboard management agent
            agent_type = "DashboardAgent"
        else:
            # Global chat - use intent-based routing
            agent_type = self._route_by_intent(state.context.get("detected_intent", "general"))
        
        state.context["selected_agent"] = agent_type
        state.agent_history.append(agent_type)
        
        return state
    
    async def _processing_node(self, state: ConversationState) -> ConversationState:
        """Process request with selected agent"""
        logger.info(f"Processing with agent {state.context.get('selected_agent')} for conversation {state.conversation_id}")
        
        state.current_stage = ConversationStage.PROCESSING.value
        state.updated_at = datetime.now()
        
        # This will be handled by the CrewAI integration
        state.context["processing_status"] = "ready_for_agent"
        state.context["processing_timestamp"] = datetime.now().isoformat()
        
        return state
    
    async def _confirmation_node(self, state: ConversationState) -> ConversationState:
        """Handle confirmation and validation"""
        logger.info(f"Confirmation node for conversation {state.conversation_id}")
        
        state.current_stage = ConversationStage.CONFIRMATION.value
        state.updated_at = datetime.now()
        
        # Check if confirmation is needed
        needs_confirmation = state.context.get("requires_booking", False) or \
                           state.context.get("detected_intent") in ["booking", "order", "appointment"]
        
        state.context["needs_confirmation"] = needs_confirmation
        
        return state
    
    async def _workflow_trigger_node(self, state: ConversationState) -> ConversationState:
        """Trigger Temporal workflows if needed"""
        logger.info(f"Workflow trigger for conversation {state.conversation_id}")
        
        state.current_stage = ConversationStage.WORKFLOW_TRIGGER.value
        state.updated_at = datetime.now()
        
        # Determine if workflow is needed
        workflow_type = self._determine_workflow_type(state.context)
        if workflow_type:
            state.context["workflow_type"] = workflow_type
            state.context["workflow_data"] = self._prepare_workflow_data(state)
            state.context["workflow_triggered"] = True
        else:
            state.context["workflow_triggered"] = False
        
        return state
    
    async def _completion_node(self, state: ConversationState) -> ConversationState:
        """Complete the conversation turn"""
        logger.info(f"Completion node for conversation {state.conversation_id}")
        
        state.current_stage = ConversationStage.COMPLETION.value
        state.updated_at = datetime.now()
        state.turn_count += 1
        
        # Mark conversation as ready for response
        state.context["ready_for_response"] = True
        
        return state
    
    async def _error_recovery_node(self, state: ConversationState) -> ConversationState:
        """Handle errors and recovery"""
        logger.info(f"Error recovery for conversation {state.conversation_id}")
        
        state.current_stage = ConversationStage.ERROR_RECOVERY.value
        state.updated_at = datetime.now()
        
        # Implement recovery logic
        state.context["recovery_attempted"] = True
        state.context["recovery_timestamp"] = datetime.now().isoformat()
        
        return state
    
    def _should_recover(self, state: ConversationState) -> str:
        """Determine if error recovery is needed"""
        if state.context.get("error_occurred", False):
            return "recover"
        return "continue"
    
    def _classify_intent(self, message: str) -> str:
        """Classify user intent from message"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["book", "reserve", "schedule", "appointment"]):
            return "booking"
        elif any(word in message_lower for word in ["order", "buy", "purchase"]):
            return "order"
        elif any(word in message_lower for word in ["find", "search", "recommend", "suggest"]):
            return "discovery"
        elif any(word in message_lower for word in ["help", "support", "problem", "issue"]):
            return "support"
        else:
            return "general"
    
    def _requires_booking(self, message: str) -> bool:
        """Check if message requires booking functionality"""
        booking_keywords = ["book", "reserve", "schedule", "appointment", "table", "slot"]
        return any(keyword in message.lower() for keyword in booking_keywords)
    
    def _detect_business_category(self, message: str) -> str:
        """Detect business category from message"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["restaurant", "food", "dining", "menu"]):
            return "food_hospitality"
        elif any(word in message_lower for word in ["beauty", "salon", "hair", "spa"]):
            return "beauty_personal_care"
        elif any(word in message_lower for word in ["car", "auto", "mechanic", "repair"]):
            return "automotive_services"
        elif any(word in message_lower for word in ["doctor", "medical", "health", "clinic"]):
            return "health_medical"
        else:
            return "local_services"
    
    def _get_required_information(self, intent: str) -> List[str]:
        """Get required information fields for intent"""
        requirements = {
            "booking": ["date", "time", "party_size", "contact"],
            "order": ["items", "quantity", "delivery_address"],
            "discovery": ["location", "preferences"],
            "support": ["issue_description"],
            "general": []
        }
        return requirements.get(intent, [])
    
    def _get_business_agent(self, business_id: str) -> str:
        """Get appropriate agent for business"""
        # This would query the business table to get category
        # For now, return general agent
        return "GeneralPurposeAgent"
    
    def _route_by_intent(self, intent: str) -> str:
        """Route to agent based on intent"""
        routing = {
            "booking": "RestaurantAgent",
            "order": "RestaurantAgent", 
            "discovery": "GeneralPurposeAgent",
            "support": "GeneralPurposeAgent",
            "general": "GeneralPurposeAgent"
        }
        return routing.get(intent, "GeneralPurposeAgent")
    
    def _determine_workflow_type(self, context: Dict[str, Any]) -> Optional[str]:
        """Determine if a Temporal workflow should be triggered"""
        if context.get("requires_booking", False):
            return "appointment_workflow"
        elif context.get("detected_intent") == "order":
            return "order_workflow"
        return None
    
    def _prepare_workflow_data(self, state: ConversationState) -> Dict[str, Any]:
        """Prepare data for Temporal workflow"""
        return {
            "conversation_id": state.conversation_id,
            "user_id": state.user_id,
            "business_id": state.business_id,
            "context": state.context,
            "timestamp": datetime.now().isoformat()
        }
    
    # Public API methods
    
    async def create_conversation(self, conversation_type: str = "general", 
                                initial_context: Dict[str, Any] = None,
                                user_id: str = None, business_id: str = None) -> str:
        """Create a new conversation"""
        conversation_id = str(uuid.uuid4())
        
        state = ConversationState(
            conversation_id=conversation_id,
            user_id=user_id,
            business_id=business_id,
            conversation_type=conversation_type,
            context=initial_context or {},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        self.conversations[conversation_id] = state
        logger.info(f"Created conversation {conversation_id} of type {conversation_type}")
        
        return conversation_id
    
    async def process_message(self, conversation_id: str, message: str, 
                            user_id: str = None) -> ConversationState:
        """Process a message through the conversation flow"""
        if conversation_id not in self.conversations:
            raise ValueError(f"Conversation {conversation_id} not found")
        
        state = self.conversations[conversation_id]
        
        # Add user message to state
        user_msg = {
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id
        }
        state.messages.append(user_msg)
        
        # Process through the graph
        try:
            result = await self.flow_graph.ainvoke(
                state,
                config={"configurable": {"thread_id": conversation_id}}
            )
            
            # Update stored state
            self.conversations[conversation_id] = result
            return result
            
        except Exception as e:
            logger.error(f"Error processing message in conversation {conversation_id}: {e}")
            state.context["error_occurred"] = True
            state.context["error_message"] = str(e)
            return state
    
    async def get_conversation_state(self, conversation_id: str) -> Optional[ConversationState]:
        """Get current conversation state"""
        return self.conversations.get(conversation_id)
    
    async def get_conversation_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get conversation message history"""
        state = self.conversations.get(conversation_id)
        if state:
            return state.messages
        return []
    
    async def end_conversation(self, conversation_id: str) -> bool:
        """End a conversation"""
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
            logger.info(f"Ended conversation {conversation_id}")
            return True
        return False
    
    async def update_conversation_context(self, conversation_id: str, 
                                        context_updates: Dict[str, Any]) -> bool:
        """Update conversation context"""
        if conversation_id in self.conversations:
            self.conversations[conversation_id].context.update(context_updates)
            self.conversations[conversation_id].updated_at = datetime.now()
            return True
        return False
