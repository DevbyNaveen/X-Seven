"""
Core AI Library - Shared components for all AI services
"""
from .base_handler import BaseAIHandler
from .context_builders import (
    build_global_context,
    build_dedicated_context,
    build_dashboard_context
)
from .types import ChatContext, RichContext

__all__ = [
    "BaseAIHandler",
    "build_global_context",
    "build_dedicated_context", 
    "build_dashboard_context",
    "ChatContext",
    "RichContext"
]
