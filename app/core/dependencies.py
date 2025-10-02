"""Minimal changes to preserve original authentication while fixing session management."""
from typing import Generator, Optional, Dict, Any
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError 
from app.config.database import get_supabase_client
from app.core.supabase_auth import verify_supabase_token
from app.models.user import User
from app.models.business import Business
import logging

logger = logging.getLogger(__name__)

async def get_current_user(
    authorization: Optional[str] = Header(None),
    supabase = Depends(get_supabase_client)
) -> User:
    """
    Get current authenticated user from Supabase token only.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = authorization.split("Bearer ")[1]
    
    # Use the auth helper that already handles Google tokens correctly
    from app.core.supabase_auth import get_current_user_with_business
    
    try:
        user_data = await get_current_user_with_business(token)
        
        # Extract business data if present
        business_data = user_data.get("business")
        if not business_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Business not found for this user.",
            )
        
        if not business_data.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Business is inactive",
            )
        
        # Create User object
        user_obj_data = {
            "id": user_data.get("sub"),
            "email": user_data.get("email"),
            "business_id": business_data.get("id"),
            "is_active": business_data.get("is_active", True),
            "created_at": business_data.get("created_at"),
            "updated_at": business_data.get("updated_at")
        }
        
        logger.info(f"Authenticated user {user_data.get('email')} with business {business_data.get('id')}")
        return User.from_dict(user_obj_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate token",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    supabase = Depends(get_supabase_client)
) -> Optional[User]:
    """
    Gets the current user if a Supabase token is provided, but returns None
    instead of raising an error if the token is missing or invalid.
    """
    if authorization is None or not authorization.startswith("Bearer "):
        return None
    
    token = authorization.split("Bearer ")[1]
    
    # Set session for optional auth too
    try:
        supabase.auth.set_session(token, None)
    except Exception:
        pass  # Ignore session errors for optional auth
    
    try:
        # Verify Supabase token only
        supabase_payload = await verify_supabase_token(token)
        if supabase_payload:
            email: str = supabase_payload.get("email")
            if not email:
                return None

            business_response = supabase.table("businesses").select("*").eq("email", email).execute()
            if not business_response.data:
                return None
            
            business_data = business_response.data[0]
            if not business_data.get("is_active", True):
                return None

            # Create a User object from business data for backward compatibility
            user_data = {
                "id": business_data.get("owner_id"),
                "email": email,
                "business_id": business_data.get("id"),
                "is_active": business_data.get("is_active", True),
                "created_at": business_data.get("created_at"),
                "updated_at": business_data.get("updated_at")
            }
            return User.from_dict(user_data)
    except Exception:
        # If any error occurs during token processing, treat as a guest user.
        return None


async def get_current_business(
    current_user: User = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
) -> Business:
    """
    Get the business associated with current user.
    """
    
    if not current_user.business_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not associated with any business"
        )
    
    business_response = supabase.table("businesses").select("*").eq("id", current_user.business_id).execute()
    if not business_response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found"
        )
    
    business_data = business_response.data[0]
    if not business_data.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Business is inactive"
        )
    
    return Business.from_dict(business_data)

# New dependency: get_current_business_from_token
async def get_current_business_from_token(
    authorization: Optional[str] = Header(None),
    supabase = Depends(get_supabase_client)
) -> Business:
    """Validate JWT token and return Business directly using business_id from token payload.
    Useful for endpoints that only need business context without loading a User.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header with Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split("Bearer ")[1]
    
    # Set session for this request
    try:
        supabase.auth.set_session(token, None)
    except Exception as e:
        logger.error(f"Failed to set session: {e}")
    
    payload = await verify_supabase_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Supabase token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    business_id = payload.get("business_id")
    if not business_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token does not contain business_id",
        )
    business_response = supabase.table("businesses").select("*").eq("id", business_id).execute()
    if not business_response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found"
        )
    business_data = business_response.data[0]
    if not business_data.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Business is inactive"
        )
    return Business.from_dict(business_data)


async def get_current_business_optional(
    current_user: Optional[User] = Depends(get_current_user_optional),
    supabase = Depends(get_supabase_client)
) -> Optional[Business]:
    """
    Get the business associated with current user (optional).
    Returns None if no user or business found.
    """
    if not current_user:
        return None
    
    if not current_user or not current_user.business_id:
        return None
    
    business_response = supabase.table("businesses").select("*").eq("id", current_user.business_id).execute()
    if not business_response.data:
        return None
    
    business_data = business_response.data[0]
    return Business.from_dict(business_data) if business_data.get("is_active", True) else None


def get_multi_tenant_filter(business_id: str):
    """
    Create a filter for multi-tenant data access.
    """
    return {"business_id": business_id}