"""
Advanced Conversation Graph Structures for LangGraph
Provides complex conversation flows with branching, loops, and dynamic routing
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Union, Callable
from enum import Enum
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from .conversation_state import ConversationGraph, ConversationNode, ConversationEdge, ConversationNodeType


class ConversationFlowType(Enum):
    """Types of conversation flows"""
    LINEAR = "linear"           # Simple sequential flow
    BRANCHING = "branching"     # Multiple paths based on conditions
    CYCLIC = "cyclic"          # Loops and cycles
    DYNAMIC = "dynamic"        # AI-powered dynamic routing
    HIERARCHICAL = "hierarchical"  # Multi-level conversation structure


@dataclass
class ConversationCondition:
    """Condition for conversation flow control"""
    condition_type: str  # "equals", "contains", "regex", "function", "intent"
    variable: str
    value: Any
    operator: str = "=="  # ==, !=, >, <, >=, <=, contains, regex, etc.

    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate condition against context"""
        try:
            var_value = context.get(self.variable)

            if self.condition_type == "equals":
                return var_value == self.value
            elif self.condition_type == "contains":
                return self.value in str(var_value)
            elif self.condition_type == "regex":
                import re
                return bool(re.search(self.value, str(var_value)))
            elif self.condition_type == "function":
                # Call a function to evaluate
                if callable(self.value):
                    return self.value(context)
                return False
            elif self.condition_type == "intent":
                # Intent-based matching (simplified)
                return self._match_intent(var_value, self.value)
            else:
                # Simple comparison
                return eval(f"var_value {self.operator} self.value")
        except:
            return False

    def _match_intent(self, user_input: str, intent_pattern: str) -> bool:
        """Simple intent matching"""
        if not user_input:
            return False

        user_input = user_input.lower()
        intent_pattern = intent_pattern.lower()

        # Keyword matching for intents
        keywords = intent_pattern.split(",")
        return any(keyword.strip() in user_input for keyword in keywords)


@dataclass
class ConversationAction:
    """Action to be performed at a conversation node"""
    action_type: str  # "set_variable", "call_api", "send_message", "execute_function"
    parameters: Dict[str, Any]
    async_action: bool = False

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the action"""
        try:
            if self.action_type == "set_variable":
                key = self.parameters.get("key")
                value = self.parameters.get("value")
                context[key] = value
                return context

            elif self.action_type == "call_api":
                # API call logic would go here
                api_url = self.parameters.get("url")
                method = self.parameters.get("method", "GET")
                # Implementation would depend on specific API requirements
                return context

            elif self.action_type == "send_message":
                # Message sending logic
                message = self.parameters.get("message")
                recipient = self.parameters.get("recipient")
                # Implementation would depend on messaging system
                return context

            elif self.action_type == "execute_function":
                function_name = self.parameters.get("function")
                if callable(function_name):
                    result = function_name(context, self.parameters)
                    return result
                return context

            return context

        except Exception as e:
            context["error"] = str(e)
            return context


class AdvancedConversationNode(ConversationNode):
    """Enhanced conversation node with actions and conditions"""

    def __init__(self, id: str, node_type: ConversationNodeType, content: str,
                 actions: List[ConversationAction] = None,
                 conditions: List[ConversationCondition] = None,
                 **kwargs):
        super().__init__(id, node_type, content, **kwargs)
        self.actions = actions or []
        self.conditions = conditions or []

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["actions"] = [{"action_type": a.action_type, "parameters": a.parameters} for a in self.actions]
        data["conditions"] = [{"condition_type": c.condition_type, "variable": c.variable,
                              "value": c.value, "operator": c.operator} for c in self.conditions]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AdvancedConversationNode':
        node = super().from_dict(data)

        # Reconstruct actions
        actions = []
        for action_data in data.get("actions", []):
            action = ConversationAction(
                action_type=action_data["action_type"],
                parameters=action_data["parameters"]
            )
            actions.append(action)

        # Reconstruct conditions
        conditions = []
        for condition_data in data.get("conditions", []):
            condition = ConversationCondition(
                condition_type=condition_data["condition_type"],
                variable=condition_data["variable"],
                value=condition_data["value"],
                operator=condition_data.get("operator", "==")
            )
            conditions.append(condition)

        node.actions = actions
        node.conditions = conditions
        return node


class ComplexConversationGraph(ConversationGraph):
    """Advanced conversation graph with complex flow control"""

    def __init__(self, graph_id: str, name: str = "", description: str = "",
                 flow_type: ConversationFlowType = ConversationFlowType.LINEAR):
        super().__init__(graph_id, name, description)
        self.flow_type = flow_type
        self.context_variables: Dict[str, Any] = {}
        self.global_actions: List[ConversationAction] = []
        self.event_handlers: Dict[str, Callable] = {}

    def add_advanced_node(self, node: AdvancedConversationNode) -> bool:
        """Add an advanced node to the graph"""
        return self.add_node(node)

    def add_conditional_edge(self, source_node_id: str, target_node_id: str,
                           condition: ConversationCondition) -> Optional[str]:
        """Add a conditional edge between nodes"""
        edge = ConversationEdge(
            id=f"edge_{source_node_id}_{target_node_id}_{len(self.edges)}",
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            condition=condition
        )
        return edge.id if self.add_edge(edge) else None

    def add_dynamic_edge(self, source_node_id: str, target_node_id: str,
                        dynamic_function: Callable) -> Optional[str]:
        """Add a dynamic edge with custom routing logic"""
        edge = ConversationEdge(
            id=f"dynamic_edge_{source_node_id}_{target_node_id}_{len(self.edges)}",
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            condition=f"dynamic_{len(self.edges)}"
        )

        # Store the dynamic function
        self.event_handlers[f"dynamic_{len(self.edges)}"] = dynamic_function

        return edge.id if self.add_edge(edge) else None

    def evaluate_node_conditions(self, node: AdvancedConversationNode,
                               context: Dict[str, Any]) -> List[str]:
        """Evaluate conditions for a node and return matching edge targets"""
        matching_targets = []

        for condition in node.conditions:
            if condition.evaluate(context):
                # Find edges that match this condition
                for edge in self.edges.values():
                    if (edge.source_node_id == node.id and
                        edge.condition == condition):
                        matching_targets.append(edge.target_node_id)

        return matching_targets

    def execute_node_actions(self, node: AdvancedConversationNode,
                           context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute actions associated with a node"""
        for action in node.actions:
            if action.async_action:
                # For async actions, we'd need an event loop
                asyncio.create_task(action.execute(context))
            else:
                context = action.execute(context)

        return context

    def create_branching_conversation(self, base_content: str,
                                    branches: Dict[str, str]) -> List[str]:
        """Create a branching conversation structure"""
        node_ids = []

        # Create start node
        start_node = AdvancedConversationNode(
            id=f"branch_start_{len(self.nodes)}",
            node_type=ConversationNodeType.DECISION,
            content=base_content
        )
        self.add_advanced_node(start_node)
        node_ids.append(start_node.id)

        # Create branch nodes
        for branch_name, branch_content in branches.items():
            branch_node = AdvancedConversationNode(
                id=f"branch_{branch_name}_{len(self.nodes)}",
                node_type=ConversationNodeType.ACTION,
                content=branch_content
            )
            self.add_advanced_node(branch_node)
            node_ids.append(branch_node.id)

            # Add conditional edge
            condition = ConversationCondition(
                condition_type="equals",
                variable="selected_branch",
                value=branch_name
            )
            self.add_conditional_edge(start_node.id, branch_node.id, condition)

        return node_ids

    def create_cyclic_conversation(self, cycle_content: List[str],
                                 max_cycles: int = 3) -> List[str]:
        """Create a cyclic conversation structure"""
        node_ids = []

        for i, content in enumerate(cycle_content):
            node = AdvancedConversationNode(
                id=f"cycle_{i}_{len(self.nodes)}",
                node_type=ConversationNodeType.ACTION,
                content=content
            )
            self.add_advanced_node(node)
            node_ids.append(node.id)

            # Add cycle counter condition
            if i < len(cycle_content) - 1:
                # Continue to next node
                condition = ConversationCondition(
                    condition_type="function",
                    variable="cycle_count",
                    value=lambda ctx: ctx.get("cycle_count", 0) < max_cycles
                )
                self.add_conditional_edge(node.id, node_ids[i + 1], condition)
            else:
                # Loop back to first node
                condition = ConversationCondition(
                    condition_type="function",
                    variable="cycle_count",
                    value=lambda ctx: ctx.get("cycle_count", 0) < max_cycles
                )
                self.add_conditional_edge(node.id, node_ids[0], condition)

        return node_ids

    def create_dynamic_routing(self, router_content: str,
                             routing_function: Callable) -> str:
        """Create a node with dynamic routing"""
        node = AdvancedConversationNode(
            id=f"dynamic_router_{len(self.nodes)}",
            node_type=ConversationNodeType.DECISION,
            content=router_content
        )
        self.add_advanced_node(node)

        # Add dynamic edge (target will be determined at runtime)
        self.add_dynamic_edge(node.id, "dynamic_target", routing_function)

        return node.id

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with advanced features"""
        data = super().to_dict()
        data["flow_type"] = self.flow_type.value
        data["context_variables"] = self.context_variables
        data["global_actions"] = [{"action_type": a.action_type, "parameters": a.parameters}
                                for a in self.global_actions]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ComplexConversationGraph':
        """Create from dictionary"""
        flow_type = ConversationFlowType(data.get("flow_type", "linear"))
        graph = cls(
            graph_id=data["graph_id"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            flow_type=flow_type
        )

        # Load nodes
        for node_id, node_data in data.get("nodes", {}).items():
            if "actions" in node_data or "conditions" in node_data:
                node = AdvancedConversationNode.from_dict(node_data)
            else:
                node = ConversationNode.from_dict(node_data)
            graph.nodes[node_id] = node

        # Load edges
        for edge_id, edge_data in data.get("edges", {}).items():
            edge = ConversationEdge.from_dict(edge_data)
            graph.edges[edge_id] = edge

        graph.start_node_id = data.get("start_node_id")
        graph.end_node_ids = data.get("end_node_ids", [])
        graph.metadata = data.get("metadata", {})
        graph.context_variables = data.get("context_variables", {})
        graph.created_at = datetime.fromisoformat(data["created_at"])
        graph.updated_at = datetime.fromisoformat(data["updated_at"])

        return graph


# Pre-built conversation templates
class ConversationTemplates:
    """Pre-built conversation graph templates"""

    @staticmethod
    def create_customer_service_flow() -> ComplexConversationGraph:
        """Create a customer service conversation flow"""
        graph = ComplexConversationGraph(
            graph_id="customer_service",
            name="Customer Service Flow",
            description="Handles customer inquiries with branching logic",
            flow_type=ConversationFlowType.BRANCHING
        )

        # Greeting node
        greeting = AdvancedConversationNode(
            id="greeting",
            node_type=ConversationNodeType.START,
            content="Hello! How can I help you today?"
        )
        graph.add_advanced_node(greeting)

        # Category selection
        categories = {
            "billing": "I can help you with billing questions, payments, and invoices.",
            "technical": "I can assist with technical issues, troubleshooting, and product support.",
            "general": "I can help with general inquiries, account information, and other questions."
        }

        category_nodes = graph.create_branching_conversation(
            "What type of assistance do you need?",
            categories
        )

        # Add edges from greeting to category nodes
        for i, category in enumerate(categories.keys()):
            condition = ConversationCondition(
                condition_type="equals",
                variable="inquiry_type",
                value=category
            )
            graph.add_conditional_edge("greeting", category_nodes[i + 1], condition)

        return graph

    @staticmethod
    def create_restaurant_booking_flow() -> ComplexConversationGraph:
        """Create a restaurant booking conversation flow"""
        graph = ComplexConversationGraph(
            graph_id="restaurant_booking",
            name="Restaurant Booking Flow",
            description="Handles restaurant reservations with dynamic routing",
            flow_type=ConversationFlowType.DYNAMIC
        )

        # Initial inquiry
        inquiry = AdvancedConversationNode(
            id="restaurant_inquiry",
            node_type=ConversationNodeType.START,
            content="I'd be happy to help you find and book a restaurant. What type of cuisine are you interested in?"
        )
        graph.add_advanced_node(inquiry)

        # Dynamic routing based on cuisine type
        def cuisine_router(context):
            cuisine = context.get("cuisine_type", "").lower()
            if "italian" in cuisine:
                return "italian_specialist"
            elif "asian" in cuisine or "chinese" in cuisine or "japanese" in cuisine:
                return "asian_specialist"
            elif "mexican" in cuisine or "spanish" in cuisine:
                return "mexican_specialist"
            else:
                return "general_restaurant"

        graph.create_dynamic_routing(
            "Let me find the perfect restaurant for your {cuisine_type} preference.",
            cuisine_router
        )

        return graph

    @staticmethod
    def create_complaint_handling_flow() -> ComplexConversationGraph:
        """Create a complaint handling conversation flow"""
        graph = ComplexConversationGraph(
            graph_id="complaint_handling",
            name="Complaint Resolution Flow",
            description="Handles customer complaints with escalation logic",
            flow_type=ConversationFlowType.HIERARCHICAL
        )

        # Initial complaint intake
        complaint = AdvancedConversationNode(
            id="complaint_intake",
            node_type=ConversationNodeType.START,
            content="I'm sorry to hear you're experiencing an issue. Can you please describe what's wrong?"
        )
        graph.add_advanced_node(complaint)

        # Assessment node
        assessment = AdvancedConversationNode(
            id="issue_assessment",
            node_type=ConversationNodeType.DECISION,
            content="Thank you for explaining the issue. Let me assess the severity and determine the best resolution path."
        )
        graph.add_advanced_node(assessment)

        # Add conditional edges based on severity
        high_severity_condition = ConversationCondition(
            condition_type="equals",
            variable="severity",
            value="high"
        )
        graph.add_conditional_edge("issue_assessment", "escalation_manager", high_severity_condition)

        medium_severity_condition = ConversationCondition(
            condition_type="equals",
            variable="severity",
            value="medium"
        )
        graph.add_conditional_edge("issue_assessment", "standard_resolution", medium_severity_condition)

        low_severity_condition = ConversationCondition(
            condition_type="equals",
            variable="severity",
            value="low"
        )
        graph.add_conditional_edge("issue_assessment", "simple_fix", low_severity_condition)

        return graph
