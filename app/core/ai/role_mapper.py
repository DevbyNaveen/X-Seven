"""
Dynamic role mapping utility for chat messages.

This module provides a centralized way to map sender types to chat roles,
supporting extensibility for future sender types.
"""
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class RoleMapper:
    """Maps sender types to standardized chat roles."""
    
    # Standard role mappings
    ROLE_MAPPINGS = {
        # Customer-facing roles
        "customer": "user",
        "user": "user",
        "client": "user",
        "guest": "user",
        
        # AI/Bot roles
        "assistant": "assistant",
        "bot": "assistant",
        "ai": "assistant",
        "system": "assistant",
        
        # Business roles
        "business": "assistant",
        "staff": "assistant",
        "admin": "assistant",
        "manager": "assistant",
        
        # Support roles
        "support": "assistant",
        "agent": "assistant",
    }
    
    @classmethod
    def get_chat_role(cls, sender_type: str, default_role: str = "user") -> str:
        """
        Map a sender type to a standardized chat role.
        
        Args:
            sender_type: The type of message sender (e.g., 'customer', 'bot', 'staff')
            default_role: Default role to return if sender_type is not recognized
            
        Returns:
            Standardized chat role: "user" or "assistant"
            
        Examples:
            >>> RoleMapper.get_chat_role("customer")
            "user"
            >>> RoleMapper.get_chat_role("bot")
            "assistant"
            >>> RoleMapper.get_chat_role("unknown_type")
            "user"  # default
        """
        if not sender_type:
            logger.warning("Empty sender_type provided, using default role")
            return default_role
            
        sender_type = sender_type.lower().strip()
        
        # Direct mapping
        if sender_type in cls.ROLE_MAPPINGS:
            return cls.ROLE_MAPPINGS[sender_type]
            
        # Handle variations and edge cases
        for key, role in cls.ROLE_MAPPINGS.items():
            if key in sender_type or sender_type in key:
                return role
                
        logger.warning(f"Unknown sender_type '{sender_type}', using default role '{default_role}'")
        return default_role
    
    @classmethod
    def add_custom_mapping(cls, sender_type: str, chat_role: str) -> None:
        """
        Add a custom role mapping.
        
        Args:
            sender_type: The sender type to map
            chat_role: The target chat role ("user" or "assistant")
        """
        if chat_role not in ["user", "assistant"]:
            raise ValueError("chat_role must be either 'user' or 'assistant'")
            
        cls.ROLE_MAPPINGS[sender_type.lower()] = chat_role
        logger.info(f"Added custom role mapping: {sender_type} -> {chat_role}")
    
    @classmethod
    def get_all_mappings(cls) -> Dict[str, str]:
        """Get all current role mappings."""
        return cls.ROLE_MAPPINGS.copy()
    
    @classmethod
    def is_customer_role(cls, sender_type: str) -> bool:
        """
        Check if a sender type represents a customer/user.
        
        Args:
            sender_type: The type of message sender
            
        Returns:
            True if the sender is a customer/user, False otherwise
        """
        return cls.get_chat_role(sender_type) == "user"
    
    @classmethod
    def is_ai_role(cls, sender_type: str) -> bool:
        """
        Check if a sender type represents an AI/assistant.
        
        Args:
            sender_type: The type of message sender
            
        Returns:
            True if the sender is an AI/assistant, False otherwise
        """
        return cls.get_chat_role(sender_type) == "assistant"


# Convenience functions for common use cases
def map_sender_to_role(sender_type: str) -> str:
    """Convenience function to map sender type to chat role."""
    return RoleMapper.get_chat_role(sender_type)


def is_user_message(sender_type: str) -> bool:
    """Check if message is from a user/customer."""
    return RoleMapper.is_customer_role(sender_type)


def is_assistant_message(sender_type: str) -> bool:
    """Check if message is from an assistant/AI."""
    return RoleMapper.is_ai_role(sender_type)
