"""
Services package for X-SevenAI backend.

This package contains all business logic services organized by domain:
- ai: AI/ML services for conversation, intent detection, etc.
- business: Business-specific services (menu, orders, etc.)
- external: External API integrations (Twilio, WhatsApp, Stripe, etc.)
- notifications: Notification and messaging services
- phone: Phone number management services
- utils: Utility services
- websocket: WebSocket connection management
"""

# IMPORTANT: Do not eager-import subpackages or modules here.
# Import services explicitly where needed (e.g., `from app.services.ai import ConversationHandler`).

# Keeping __all__ empty to avoid accidental imports of heavy optional dependencies
__all__: list[str] = []
