"""
UUID Validation Utilities
"""
import uuid
from typing import Optional

def is_valid_uuid(value: str) -> bool:
    """Check if a string is a valid UUID"""
    try:
        uuid.UUID(value)
        return True
    except (ValueError, TypeError):
        return False

def safe_uuid_conversion(value: Optional[str]) -> Optional[str]:
    """Safely convert string to UUID format or return None if invalid"""
    if not value or not isinstance(value, str):
        return None
    return value if is_valid_uuid(value) else None

def generate_test_uuid() -> str:
    """Generate a test UUID for testing purposes"""
    return str(uuid.uuid4())
