# app/services/ai/__init__.py
"""
AI services package - Central Brain Architecture

Exposes the central AI handler for all chat types.
"""
from .central_ai_handler import CentralAIHandler, ChatType

# Keep backward compatibility  
from .simple_ai_handler import SimpleAIHandler

__all__ = [
    "CentralAIHandler", 
    "ChatType",
    "SimpleAIHandler",  # For backward compatibility during transition
]