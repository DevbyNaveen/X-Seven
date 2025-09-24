"""
Conversation State Management for LangGraph
Handles conversation state, nodes, and transitions
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from enum import Enum
from dataclasses import dataclass, field
from abc import ABC, abstractmethod


class ConversationNodeType(Enum):
    """Types of conversation nodes"""
    START = "start"
    END = "end"
    DECISION = "decision"
    ACTION = "action"
    BRANCH = "branch"
    MERGE = "merge"


@dataclass
class ConversationNode:
    """Represents a node in the conversation graph"""
    id: str
    node_type: ConversationNodeType
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "node_type": self.node_type.value,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationNode':
        return cls(
            id=data["id"],
            node_type=ConversationNodeType(data["node_type"]),
            content=data["content"],
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"])
        )


@dataclass
class ConversationEdge:
    """Represents an edge between conversation nodes"""
    id: str
    source_node_id: str
    target_node_id: str
    condition: Optional[str] = None
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "condition": self.condition,
            "weight": self.weight,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationEdge':
        return cls(
            id=data["id"],
            source_node_id=data["source_node_id"],
            target_node_id=data["target_node_id"],
            condition=data.get("condition"),
            weight=data.get("weight", 1.0),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"])
        )


@dataclass
class ConversationState:
    """Current state of a conversation"""
    conversation_id: str
    current_node_id: str
    context: Dict[str, Any] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)
    history: List[str] = field(default_factory=list)  # List of visited node IDs
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "current_node_id": self.current_node_id,
            "context": self.context,
            "variables": self.variables,
            "history": self.history,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationState':
        return cls(
            conversation_id=data["conversation_id"],
            current_node_id=data["current_node_id"],
            context=data.get("context", {}),
            variables=data.get("variables", {}),
            history=data.get("history", []),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"])
        )

    def update_timestamp(self):
        """Update the updated_at timestamp"""
        self.updated_at = datetime.now()

    def add_to_history(self, node_id: str):
        """Add a node to the conversation history"""
        if node_id not in self.history:
            self.history.append(node_id)
        self.update_timestamp()

    def set_variable(self, key: str, value: Any):
        """Set a conversation variable"""
        self.variables[key] = value
        self.update_timestamp()

    def get_variable(self, key: str, default: Any = None) -> Any:
        """Get a conversation variable"""
        return self.variables.get(key, default)


class ConversationGraph:
    """Represents a conversation flow graph"""

    def __init__(self, graph_id: str, name: str = "", description: str = ""):
        self.graph_id = graph_id
        self.name = name
        self.description = description
        self.nodes: Dict[str, ConversationNode] = {}
        self.edges: Dict[str, ConversationEdge] = {}
        self.start_node_id: Optional[str] = None
        self.end_node_ids: List[str] = []
        self.metadata: Dict[str, Any] = {}
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    def add_node(self, node: ConversationNode) -> bool:
        """Add a node to the graph"""
        if node.id in self.nodes:
            return False

        self.nodes[node.id] = node
        self.updated_at = datetime.now()

        # Set as start node if it's the first node or marked as start
        if not self.start_node_id or node.node_type == ConversationNodeType.START:
            self.start_node_id = node.id

        # Add to end nodes if marked as end
        if node.node_type == ConversationNodeType.END:
            if node.id not in self.end_node_ids:
                self.end_node_ids.append(node.id)

        return True

    def add_edge(self, edge: ConversationEdge) -> bool:
        """Add an edge to the graph"""
        if edge.id in self.edges:
            return False

        # Validate that source and target nodes exist
        if edge.source_node_id not in self.nodes or edge.target_node_id not in self.nodes:
            return False

        self.edges[edge.id] = edge
        self.updated_at = datetime.now()
        return True

    def get_node(self, node_id: str) -> Optional[ConversationNode]:
        """Get a node by ID"""
        return self.nodes.get(node_id)

    def get_edge(self, edge_id: str) -> Optional[ConversationEdge]:
        """Get an edge by ID"""
        return self.edges.get(edge_id)

    def get_outgoing_edges(self, node_id: str) -> List[ConversationEdge]:
        """Get all edges coming out from a node"""
        return [edge for edge in self.edges.values() if edge.source_node_id == node_id]

    def get_incoming_edges(self, node_id: str) -> List[ConversationEdge]:
        """Get all edges coming into a node"""
        return [edge for edge in self.edges.values() if edge.target_node_id == node_id]

    def get_neighbors(self, node_id: str) -> List[str]:
        """Get neighbor node IDs"""
        outgoing = [edge.target_node_id for edge in self.get_outgoing_edges(node_id)]
        incoming = [edge.source_node_id for edge in self.get_incoming_edges(node_id)]
        return list(set(outgoing + incoming))

    def to_dict(self) -> Dict[str, Any]:
        """Convert graph to dictionary"""
        return {
            "graph_id": self.graph_id,
            "name": self.name,
            "description": self.description,
            "nodes": {node_id: node.to_dict() for node_id, node in self.nodes.items()},
            "edges": {edge_id: edge.to_dict() for edge_id, edge in self.edges.items()},
            "start_node_id": self.start_node_id,
            "end_node_ids": self.end_node_ids,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationGraph':
        """Create graph from dictionary"""
        graph = cls(
            graph_id=data["graph_id"],
            name=data.get("name", ""),
            description=data.get("description", "")
        )

        # Load nodes
        for node_id, node_data in data.get("nodes", {}).items():
            node = ConversationNode.from_dict(node_data)
            graph.nodes[node_id] = node

        # Load edges
        for edge_id, edge_data in data.get("edges", {}).items():
            edge = ConversationEdge.from_dict(edge_data)
            graph.edges[edge_id] = edge

        graph.start_node_id = data.get("start_node_id")
        graph.end_node_ids = data.get("end_node_ids", [])
        graph.metadata = data.get("metadata", {})
        graph.created_at = datetime.fromisoformat(data["created_at"])
        graph.updated_at = datetime.fromisoformat(data["updated_at"])

        return graph

    def validate(self) -> List[str]:
        """Validate the graph structure"""
        errors = []

        # Check if start node exists
        if not self.start_node_id:
            errors.append("Graph has no start node")
        elif self.start_node_id not in self.nodes:
            errors.append(f"Start node {self.start_node_id} does not exist")

        # Check if end nodes exist
        for end_node_id in self.end_node_ids:
            if end_node_id not in self.nodes:
                errors.append(f"End node {end_node_id} does not exist")

        # Check for orphaned nodes (nodes with no edges)
        all_connected_nodes = set()
        for edge in self.edges.values():
            all_connected_nodes.add(edge.source_node_id)
            all_connected_nodes.add(edge.target_node_id)

        orphaned_nodes = set(self.nodes.keys()) - all_connected_nodes
        if orphaned_nodes and self.start_node_id not in orphaned_nodes:
            errors.append(f"Orphaned nodes found: {orphaned_nodes}")

        return errors


class ConversationStateManager:
    """Manages conversation states and transitions"""

    def __init__(self):
        self.active_states: Dict[str, ConversationState] = {}
        self.graphs: Dict[str, ConversationGraph] = {}

    def create_state(self, conversation_id: str, graph_id: str) -> Optional[ConversationState]:
        """Create a new conversation state"""
        graph = self.graphs.get(graph_id)
        if not graph or not graph.start_node_id:
            return None

        state = ConversationState(
            conversation_id=conversation_id,
            current_node_id=graph.start_node_id,
            metadata={"graph_id": graph_id}
        )

        self.active_states[conversation_id] = state
        return state

    def get_state(self, conversation_id: str) -> Optional[ConversationState]:
        """Get conversation state"""
        return self.active_states.get(conversation_id)

    def update_state(self, state: ConversationState):
        """Update conversation state"""
        state.update_timestamp()
        self.active_states[state.conversation_id] = state

    def transition(self, conversation_id: str, target_node_id: str, condition_data: Dict[str, Any] = None) -> bool:
        """Transition to a new node"""
        state = self.get_state(conversation_id)
        if not state:
            return False

        # Validate transition
        graph = self.graphs.get(state.metadata.get("graph_id"))
        if not graph:
            return False

        # Check if target node exists
        if target_node_id not in graph.nodes:
            return False

        # Check if there's a valid edge
        outgoing_edges = graph.get_outgoing_edges(state.current_node_id)
        valid_transition = False

        for edge in outgoing_edges:
            if edge.target_node_id == target_node_id:
                # Check condition if present
                if edge.condition:
                    try:
                        condition_met = eval(edge.condition, {"state": state, "data": condition_data or {}})
                        if condition_met:
                            valid_transition = True
                            break
                    except:
                        continue
                else:
                    valid_transition = True
                    break

        if not valid_transition:
            return False

        # Perform transition
        state.current_node_id = target_node_id
        state.add_to_history(target_node_id)
        self.update_state(state)

        return True

    def add_graph(self, graph: ConversationGraph) -> bool:
        """Add a conversation graph"""
        if graph.graph_id in self.graphs:
            return False

        # Validate graph
        errors = graph.validate()
        if errors:
            raise ValueError(f"Invalid graph: {errors}")

        self.graphs[graph.graph_id] = graph
        return True

    def get_graph(self, graph_id: str) -> Optional[ConversationGraph]:
        """Get a conversation graph"""
        return self.graphs.get(graph_id)

    def remove_state(self, conversation_id: str):
        """Remove a conversation state"""
        if conversation_id in self.active_states:
            del self.active_states[conversation_id]

    def get_active_conversations(self) -> List[str]:
        """Get list of active conversation IDs"""
        return list(self.active_states.keys())
