"""
CrewAI-LangGraph Integration Layer
Bridges LangGraph conversation flows with CrewAI agent orchestration
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
import logging

from app.api.v1.conversation_flow_engine import ConversationFlowEngine, ConversationConfig, ConversationState
from app.api.v1.redis_persistence import RedisPersistenceManager
from app.services.ai.crewai_orchestrator import get_crewai_orchestrator
from app.workflows.temporal_integration import TemporalWorkflowManager

logger = logging.getLogger(__name__)


class CrewAILangGraphIntegrator:
    """Integration layer between LangGraph conversation flows and CrewAI agents"""
    
    def __init__(self):
        # Initialize components
        self.conversation_config = ConversationConfig(
            max_turns=50,
            timeout_seconds=300,
            enable_persistence=True,
            enable_recovery=True,
            fallback_agent="GeneralPurposeAgent"
        )
        
        self.flow_engine = ConversationFlowEngine(self.conversation_config)
        self.redis_manager = RedisPersistenceManager()
        self.crewai_orchestrator = get_crewai_orchestrator()
        self.temporal_manager = TemporalWorkflowManager()
        
        # Agent mapping for different conversation types
        self.agent_mapping = {
            "dedicated": self._handle_dedicated_chat,
            "dashboard": self._handle_dashboard_chat,
            "global": self._handle_global_chat
        }
        
        logger.info("✅ CrewAI-LangGraph integrator initialized")
    
    async def create_enhanced_conversation(self, conversation_type: str = "global",
                                         initial_context: Dict[str, Any] = None,
                                         user_id: str = None, 
                                         business_id: str = None) -> str:
        """Create a new conversation with enhanced context"""
        try:
            # Create conversation in LangGraph
            conversation_id = await self.flow_engine.create_conversation(
                conversation_type=conversation_type,
                initial_context=initial_context or {},
                user_id=user_id,
                business_id=business_id
            )
            
            # Enhance context based on conversation type
            enhanced_context = await self._enhance_initial_context(
                conversation_type, initial_context, user_id, business_id
            )
            
            # Save to Redis for persistence
            await self.redis_manager.save_conversation_state(
                conversation_id, 
                {
                    "conversation_id": conversation_id,
                    "conversation_type": conversation_type,
                    "user_id": user_id,
                    "business_id": business_id,
                    "context": enhanced_context,
                    "created_at": datetime.now().isoformat(),
                    "status": "active"
                }
            )
            
            logger.info(f"Created enhanced conversation {conversation_id} of type {conversation_type}")
            return conversation_id
            
        except Exception as e:
            logger.error(f"Failed to create enhanced conversation: {e}")
            raise
    
    async def process_message_with_agent(self, conversation_id: str, message: str, 
                                       user_id: str = None) -> Dict[str, Any]:
        """Process message through LangGraph flow and CrewAI agents"""
        try:
            # Load conversation state
            conversation_state = await self.flow_engine.get_conversation_state(conversation_id)
            if not conversation_state:
                raise ValueError(f"Conversation {conversation_id} not found")
            
            # Process through LangGraph flow
            updated_state = await self.flow_engine.process_message(
                conversation_id, message, user_id
            )
            
            # Check if ready for agent processing
            if updated_state.context.get("processing_status") == "ready_for_agent":
                # Route to appropriate agent handler
                handler = self.agent_mapping.get(
                    updated_state.conversation_type, 
                    self._handle_global_chat
                )
                
                agent_response = await handler(updated_state, message, user_id)
                
                # Update conversation state with agent response
                updated_state.context["agent_response"] = agent_response
                updated_state.context["last_agent_used"] = agent_response.get("agent_used", "unknown")
                
                # Add assistant message to conversation
                assistant_msg = {
                    "role": "assistant",
                    "content": agent_response.get("response", "I couldn't process your request."),
                    "timestamp": datetime.now().isoformat(),
                    "agent": agent_response.get("agent_used"),
                    "metadata": agent_response.get("metadata", {})
                }
                updated_state.messages.append(assistant_msg)
                
                # Trigger workflows if needed
                if updated_state.context.get("workflow_triggered", False):
                    await self._trigger_temporal_workflow(updated_state)
                
                # Save updated state
                await self.redis_manager.save_conversation_state(
                    conversation_id,
                    self._serialize_conversation_state(updated_state)
                )
                
                # Return formatted response
                return {
                    "conversation_id": conversation_id,
                    "response": agent_response.get("response", ""),
                    "agent_used": agent_response.get("agent_used", "unknown"),
                    "turn_count": updated_state.turn_count,
                    "status": "processed",
                    "context": updated_state.context,
                    "metadata": {
                        "processing_time": agent_response.get("processing_time"),
                        "workflow_triggered": updated_state.context.get("workflow_triggered", False),
                        "conversation_stage": updated_state.current_stage
                    }
                }
            else:
                # Still in flow processing
                return {
                    "conversation_id": conversation_id,
                    "response": "I'm processing your request...",
                    "agent_used": "flow_engine",
                    "turn_count": updated_state.turn_count,
                    "status": "processing",
                    "context": updated_state.context,
                    "metadata": {
                        "conversation_stage": updated_state.current_stage,
                        "needs_more_info": len(updated_state.context.get("missing_information", [])) > 0
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to process message in conversation {conversation_id}: {e}")
            return {
                "conversation_id": conversation_id,
                "error": str(e),
                "status": "error",
                "agent_used": "error_handler"
            }
    
    async def _handle_dedicated_chat(self, state: ConversationState, message: str, 
                                   user_id: str = None) -> Dict[str, Any]:
        """Handle dedicated business chat"""
        logger.info(f"Processing dedicated chat for business {state.business_id}")
        
        try:
            # Get business context
            business_context = await self._get_business_context(state.business_id)
            
            # Process with CrewAI using business category
            response = await self.crewai_orchestrator.process_request(
                message=message,
                user_id=user_id or state.user_id,
                session_id=state.conversation_id,
                conversation_history=state.messages,
                context=state.context,
                business_category=business_context.get("category"),
                business_id=state.business_id
            )
            
            # Enhance response with business-specific data
            response["chat_type"] = "dedicated"
            response["business_id"] = state.business_id
            response["business_context"] = business_context
            
            return response
            
        except Exception as e:
            logger.error(f"Error in dedicated chat processing: {e}")
            return {
                "response": "I'm having trouble accessing business information. Please try again.",
                "agent_used": "error_handler",
                "error": str(e),
                "chat_type": "dedicated"
            }
    
    async def _handle_dashboard_chat(self, state: ConversationState, message: str, 
                                   user_id: str = None) -> Dict[str, Any]:
        """Handle dashboard management chat"""
        logger.info(f"Processing dashboard chat for business {state.business_id}")
        
        try:
            # Get business management context
            management_context = await self._get_management_context(state.business_id, user_id)
            
            # Process with specialized dashboard agent
            response = await self.crewai_orchestrator.process_request(
                message=message,
                user_id=user_id or state.user_id,
                session_id=state.conversation_id,
                conversation_history=state.messages,
                context={**state.context, **management_context},
                business_category="dashboard_management",
                business_id=state.business_id
            )
            
            # Enhance response with management capabilities
            response["chat_type"] = "dashboard"
            response["management_context"] = management_context
            response["available_actions"] = self._get_dashboard_actions(management_context)
            
            return response
            
        except Exception as e:
            logger.error(f"Error in dashboard chat processing: {e}")
            return {
                "response": "I'm having trouble accessing dashboard features. Please try again.",
                "agent_used": "error_handler",
                "error": str(e),
                "chat_type": "dashboard"
            }
    
    async def _handle_global_chat(self, state: ConversationState, message: str, 
                                user_id: str = None) -> Dict[str, Any]:
        """Handle global assessment and comparison chat"""
        logger.info("Processing global chat for multi-business assessment")
        
        try:
            # Get global context with multiple businesses
            global_context = await self._get_global_context(state.context)
            
            # Process with CrewAI for cross-business analysis
            response = await self.crewai_orchestrator.process_request(
                message=message,
                user_id=user_id or state.user_id,
                session_id=state.conversation_id,
                conversation_history=state.messages,
                context={**state.context, **global_context}
            )
            
            # Enhance response with comparison capabilities
            response["chat_type"] = "global"
            response["businesses_analyzed"] = len(global_context.get("businesses", []))
            response["comparison_available"] = True
            
            return response
            
        except Exception as e:
            logger.error(f"Error in global chat processing: {e}")
            return {
                "response": "I'm having trouble analyzing businesses. Please try again.",
                "agent_used": "error_handler",
                "error": str(e),
                "chat_type": "global"
            }
    
    async def _enhance_initial_context(self, conversation_type: str, 
                                     initial_context: Dict[str, Any], 
                                     user_id: str, business_id: str) -> Dict[str, Any]:
        """Enhance initial context based on conversation type"""
        enhanced = initial_context.copy() if initial_context else {}
        
        # Load user context if available
        if user_id:
            user_context = await self.redis_manager.load_user_context(user_id)
            if user_context:
                enhanced["user_preferences"] = user_context
        
        # Load business context for dedicated/dashboard chats
        if business_id and conversation_type in ["dedicated", "dashboard"]:
            business_context = await self._get_business_context(business_id)
            enhanced["business_info"] = business_context
        
        # Add conversation type specific enhancements
        if conversation_type == "global":
            enhanced["enable_comparison"] = True
            enhanced["multi_business_search"] = True
        elif conversation_type == "dashboard":
            enhanced["management_mode"] = True
            enhanced["admin_capabilities"] = True
        
        enhanced["conversation_type"] = conversation_type
        enhanced["enhanced_at"] = datetime.now().isoformat()
        
        return enhanced
    
    async def _get_business_context(self, business_id: str) -> Dict[str, Any]:
        """Get business context from database"""
        try:
            # Try Redis cache first
            cached_context = await self.redis_manager.load_business_state(business_id)
            if cached_context:
                return cached_context
            
            # Fallback to database query (would need Supabase client)
            # For now, return basic context
            context = {
                "business_id": business_id,
                "category": "general",
                "status": "active",
                "loaded_at": datetime.now().isoformat()
            }
            
            # Cache for future use
            await self.redis_manager.save_business_state(business_id, context)
            
            return context
            
        except Exception as e:
            logger.error(f"Failed to get business context for {business_id}: {e}")
            return {"business_id": business_id, "error": str(e)}
    
    async def _get_management_context(self, business_id: str, user_id: str) -> Dict[str, Any]:
        """Get management context for dashboard chat"""
        try:
            business_context = await self._get_business_context(business_id)
            
            return {
                "management_mode": True,
                "business_id": business_id,
                "user_id": user_id,
                "permissions": ["read", "write", "manage"],  # Would be determined by user role
                "available_operations": [
                    "update_business_info",
                    "manage_menu",
                    "view_analytics",
                    "manage_staff",
                    "update_hours"
                ],
                "business_context": business_context
            }
            
        except Exception as e:
            logger.error(f"Failed to get management context: {e}")
            return {"error": str(e)}
    
    async def _get_global_context(self, current_context: Dict[str, Any]) -> Dict[str, Any]:
        """Get global context for multi-business analysis"""
        try:
            # This would query all businesses for comparison
            # For now, return basic global context
            return {
                "businesses": [],  # Would be populated from database
                "comparison_enabled": True,
                "search_radius": current_context.get("search_radius", "10km"),
                "filters": current_context.get("filters", {}),
                "global_mode": True
            }
            
        except Exception as e:
            logger.error(f"Failed to get global context: {e}")
            return {"error": str(e)}
    
    def _get_dashboard_actions(self, management_context: Dict[str, Any]) -> List[str]:
        """Get available dashboard actions based on context"""
        base_actions = [
            "view_business_info",
            "update_business_hours",
            "view_customer_feedback"
        ]
        
        if "manage" in management_context.get("permissions", []):
            base_actions.extend([
                "update_menu",
                "manage_staff",
                "view_analytics",
                "update_pricing"
            ])
        
        return base_actions
    
    async def _trigger_temporal_workflow(self, state: ConversationState):
        """Trigger Temporal workflow based on conversation state"""
        try:
            workflow_type = state.context.get("workflow_type")
            workflow_data = state.context.get("workflow_data", {})
            
            if workflow_type:
                workflow_id = await self.temporal_manager.start_workflow(
                    workflow_type=workflow_type,
                    workflow_data=workflow_data,
                    conversation_id=state.conversation_id
                )
                
                # Update state with workflow info
                state.context["workflow_id"] = workflow_id
                state.context["workflow_started_at"] = datetime.now().isoformat()
                
                logger.info(f"Started {workflow_type} workflow {workflow_id} for conversation {state.conversation_id}")
                
        except Exception as e:
            logger.error(f"Failed to trigger workflow: {e}")
            state.context["workflow_error"] = str(e)
    
    def _serialize_conversation_state(self, state: ConversationState) -> Dict[str, Any]:
        """Serialize conversation state for Redis storage"""
        return {
            "conversation_id": state.conversation_id,
            "user_id": state.user_id,
            "business_id": state.business_id,
            "conversation_type": state.conversation_type,
            "current_stage": state.current_stage,
            "context": state.context,
            "messages": state.messages,
            "agent_history": state.agent_history,
            "turn_count": state.turn_count,
            "created_at": state.created_at.isoformat() if state.created_at else None,
            "updated_at": state.updated_at.isoformat() if state.updated_at else None,
            "metadata": state.metadata
        }
    
    # Public API methods
    
    async def get_conversation_context(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation context"""
        try:
            # Try Redis first
            redis_state = await self.redis_manager.load_conversation_state(conversation_id)
            if redis_state:
                return redis_state
            
            # Fallback to flow engine
            state = await self.flow_engine.get_conversation_state(conversation_id)
            if state:
                return self._serialize_conversation_state(state)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get conversation context {conversation_id}: {e}")
            return None
    
    async def switch_agent(self, conversation_id: str, agent_name: str) -> bool:
        """Switch to a different agent"""
        try:
            state = await self.flow_engine.get_conversation_state(conversation_id)
            if not state:
                return False
            
            # Update agent in context
            await self.flow_engine.update_conversation_context(
                conversation_id,
                {
                    "selected_agent": agent_name,
                    "agent_switched_at": datetime.now().isoformat()
                }
            )
            
            # Add to agent history
            state.agent_history.append(agent_name)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to switch agent in conversation {conversation_id}: {e}")
            return False
    
    async def get_available_agents(self) -> List[Dict[str, Any]]:
        """Get information about available agents"""
        return [
            {
                "name": "RestaurantAgent",
                "description": "Specialized in restaurant and food service interactions",
                "capabilities": ["booking", "menu_analysis", "food_recommendations"]
            },
            {
                "name": "BeautyAgent", 
                "description": "Expert in beauty and wellness services",
                "capabilities": ["appointment_booking", "service_recommendations", "stylist_matching"]
            },
            {
                "name": "GeneralPurposeAgent",
                "description": "Handles general inquiries and fallback scenarios",
                "capabilities": ["general_chat", "information_lookup", "basic_assistance"]
            },
            {
                "name": "DashboardAgent",
                "description": "Business management and dashboard operations",
                "capabilities": ["business_management", "analytics", "configuration"]
            }
        ]
