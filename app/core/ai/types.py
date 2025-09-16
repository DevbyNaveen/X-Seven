"""
Shared types for AI services
"""
from __future__ import annotations

from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field


class ChatContext(str, Enum):
    """Unified chat context types"""
    GLOBAL = "global"
    DEDICATED = "dedicated"
    DASHBOARD = "dashboard"


@dataclass
class RichContext:
    """Rich context container for AI processing"""
    chat_context: ChatContext
    session_id: str
    user_message: str
    business_id: Optional[int] = None
    user_id: Optional[str] = None
    
    # Core business data
    all_businesses: List[Dict] = field(default_factory=list)
    current_business: Optional[Dict] = None
    business_menu: List[Dict] = field(default_factory=list)
    business_categories: List[Dict] = field(default_factory=list)
    
    # Dashboard-specific data
    live_orders: List[Dict] = field(default_factory=list)
    inventory_status: Dict[str, Any] = field(default_factory=dict)
    sales_analytics: Dict[str, Any] = field(default_factory=dict)
    staff_data: List[Dict] = field(default_factory=list)
    
    # Conversation and user data
    conversation_history: List[Dict] = field(default_factory=list)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    
    # Context metadata
    current_time: datetime = field(default_factory=datetime.now)
    request_metadata: Dict[str, Any] = field(default_factory=dict)
