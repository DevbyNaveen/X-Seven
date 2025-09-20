# app/services/ai/__init__.py
"""
AI services package - Unified Brain Architecture

Exposes the unified AI handler for all chat types.
"""
# GlobalAIHandler removed during CrewAI integration
from .dedicated_ai_handler import DedicatedAIHandler
from .dashboard_ai_handler import DashboardAIHandler
from app.core.ai.types import ChatContext as ChatType

__all__ = [
    # "GlobalAIHandler",  # Removed during CrewAI integration
    "DedicatedAIHandler",
    "DashboardAIHandler",
    "ChatType",
]