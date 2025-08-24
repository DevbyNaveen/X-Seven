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

    class Config:
        json_schema_extra = {
            "example": {
                "business_name": "Sunrise Cafe",
                "business_slug": "sunrise-cafe",
                "admin_name": "John Doe",
                "admin_email": "john@sunrisecafe.com",
                "admin_password": "securepassword123",
                "admin_phone": "+1234567890",
                "business_category": "food_hospitality"
            }
        }


class LoginRequest(BaseModel):
    """Request schema for login."""
    email: EmailStr
    password: str

    class Config:
        json_schema_extra = {
            "example": {
                "email": "john@sunrisecafe.com",
                "password": "securepassword123"
            }
        }


class Token(BaseModel):
    """Token response schema."""
    access_token: str
    token_type: str
    business_id: int
    user_role: UserRole

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "business_id": 1,
                "user_role": "owner"
            }
        }