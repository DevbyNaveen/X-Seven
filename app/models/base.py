"""Base model for Supabase operations."""
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid


class SupabaseModel:
    """
    Base model for Supabase operations.
    
    Provides common functionality for interacting with Supabase tables.
    """
    
    table_name: str = ""
    
    def __init__(self, **kwargs):
        """Initialize model with data."""
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SupabaseModel':
        """Create model instance from dictionary."""
        return cls(**data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {key: value for key, value in self.__dict__.items() if not key.startswith('_')}
    
    def to_supabase_dict(self) -> Dict[str, Any]:
        """Convert model to Supabase-compatible dictionary."""
        data = self.to_dict()
        # Convert datetime objects to ISO strings
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
        return data
    
    @staticmethod
    def generate_uuid() -> str:
        """Generate a UUID string."""
        return str(uuid.uuid4())
    
    @staticmethod
    def generate_deterministic_uuid(namespace: str, name: str) -> str:
        """Generate a deterministic UUID from namespace and name."""
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{namespace}:{name}"))