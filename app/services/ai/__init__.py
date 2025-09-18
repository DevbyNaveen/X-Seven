# app/services/ai/__init__.py
"""
AI services package - Unified Brain Architecture

Exposes the unified AI handler for all chat types.
"""
from .global_ai import GlobalAIHandler
from .dedicated_ai_handler import DedicatedAIHandler
from .dashboard_ai_handler import DashboardAIHandler
from app.core.ai.types import ChatContext as ChatType

__all__ = [
    "GlobalAIHandler",
    "DedicatedAIHandler",
    "DashboardAIHandler",
    "ChatType",
]