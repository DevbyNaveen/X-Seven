"""
Dashboard AI Package

This package contains the dashboard AI functionality that routes from the central AI handler
to manage business dashboard features like inventory, menu, categories, live orders, and reminders.
"""

from .dashboard_ai_handler import DashboardAIHandler

__all__ = [
    "DashboardAIHandler",
]
