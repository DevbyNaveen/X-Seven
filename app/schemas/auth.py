"""Authentication schemas."""
from typing import Optional
from pydantic import BaseModel, EmailStr
from app.models import UserRole, BusinessCategory


class RegisterBusinessRequest(BaseModel):
    """Request schema for business registration."""
    business_name: str
    business_slug: str
    admin_name: str
    admin_email: EmailStr
    admin_password: str
    admin_phone: Optional[str] = None
    business_category: Optional[BusinessCategory] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "business_name": "Demo Business",
                "business_slug": "demo-business",
                "admin_name": "Admin User",
                "admin_email": "admin@example.com",
                "admin_password": "securepassword123",
                "admin_phone": "+1234567890",
                "business_category": "food_hospitality"
            }
        }
    }


class LoginRequest(BaseModel):
    """Request schema for login."""
    email: EmailStr
    password: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "admin@example.com",
                "password": "securepassword123"
            }
        }
    }


class TokenResponse(BaseModel):
    """Token response schema for Supabase authentication."""
    access_token: str
    token_type: str = "bearer"
    user_id: str  # Supabase auth user ID (UUID)
    email: str
    role: str  # User role from Supabase metadata
    business_id: Optional[str] = None  # UUID for associated business (nullable)
    expires_in: int = 3600  # Token expiration in seconds

    model_config = {
        "json_schema_extra": {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "admin@example.com",
                "role": "owner",
                "business_id": "a1b2c3d4-e5f6-7890-abcd-123456789012",
                "expires_in": 3600
            }
        }
    }


# Refresh tokens are handled by Supabase, no need for custom refresh endpoint