"""Authentication endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.schemas.auth import TokenResponse, LoginRequest
from app.core.dependencies import get_current_user
from app.config.database import get_supabase_client
from pydantic import BaseModel
from typing import Optional
import logging
import uuid
import time
import hashlib

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger(__name__)

# Add the new Google login model
class GoogleUserData(BaseModel):
    email: str
    name: str
    google_id: str
    image: Optional[str] = None

@router.post("/login", response_model=TokenResponse)
async def login(credentials: LoginRequest):
    """User login endpoint - validates with Supabase and returns token."""
    supabase = get_supabase_client()
    
    try:
        # Authenticate with Supabase
        auth_response = supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password
        })
        
        # Check if authentication was successful
        if not auth_response or not auth_response.user or not auth_response.session:
            logger.error("Authentication failed - no user or session returned")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        user = auth_response.user
        session = auth_response.session
        
        # Get business information - FIXED QUERY SYNTAX
        business_response = supabase.table("businesses").select("*").or_(
            f"email.eq.{credentials.email},owner_id.eq.{user.id}"
        ).execute()
        
        if not business_response.data:
            logger.error(f"No business found for user {user.email}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Business profile not found. Please complete your registration"
            )
        
        business_data = business_response.data[0]
        
        if not business_data.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been deactivated. Please contact support"
            )
        
        logger.info(f"Login successful for user {user.email}")
        
        # Get expires_in safely
        expires_in = getattr(session, 'expires_in', 3600) if session else 3600
        
        return TokenResponse(
            access_token=session.access_token,
            user_id=user.id,
            email=user.email,
            role=user.user_metadata.get("role", "owner") if hasattr(user, 'user_metadata') and user.user_metadata else "owner",
            business_id=business_data["id"],
            expires_in=expires_in
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )

@router.post("/google/login", response_model=TokenResponse)
async def google_login_simple(user_data: GoogleUserData):
    """
    Handle Google OAuth login by creating/finding user and returning session token
    """
    try:
        from app.config.database import get_supabase_service_client
        supabase = get_supabase_service_client()
        
        # Find business by email
        business_response = supabase.table("businesses").select("*").eq("email", user_data.email).execute()
        
        # If not found by email, try by google_id
        if not business_response.data:
            business_response = supabase.table("businesses").select("*").eq("google_id", user_data.google_id).execute()
        
        logger.info(f"Business query response for {user_data.email}: {len(business_response.data) if business_response.data else 0} records found")
        
        if not business_response.data:
            logger.error(f"No business found for user {user_data.email} or google_id {user_data.google_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Business profile not found. Please complete your registration"
            )
        
        business_data = business_response.data[0]
        
        if not business_data.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been deactivated. Please contact support"
            )
        
        # CRITICAL: Use owner_id from the business record (the Supabase Auth user ID)
        user_id = business_data["owner_id"]
        business_id = business_data["id"]
        
        logger.info(f"Google login successful for user {user_data.email}, user_id: {user_id}, business_id: {business_id}")
        
        # Generate unique session token
        session_token = str(uuid.uuid4())
        expires_at = int(time.time()) + 3600
        
        # Delete old sessions
        supabase.table("google_sessions").delete().eq("user_id", user_id).execute()
        
        # Store new session with the correct owner_id
        session_insert = supabase.table("google_sessions").insert({
            "session_token": session_token,
            "user_id": user_id,  # This now matches owner_id from businesses table
            "email": user_data.email,
            "google_id": user_data.google_id,
            "expires_at": expires_at
        }).execute()
        
        if not session_insert.data:
            raise HTTPException(status_code=500, detail="Failed to create session")
        
        logger.info(f"Google session created for user {user_data.email}, token: {session_token[:8]}...")
        
        return TokenResponse(
            access_token=f"google_session_{session_token}",
            user_id=user_id,
            email=user_data.email,
            role="owner",
            business_id=business_id,
            expires_in=3600
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )
    
          
@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Refresh token endpoint."""
    supabase = get_supabase_client()
    
    try:
        # Set the session first using the provided token
        supabase.auth.set_session(credentials.credentials, None)
        
        # Use the refresh token to get a new session
        refresh_response = supabase.auth.refresh_session()
        
        if not refresh_response or not refresh_response.user or not refresh_response.session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        user = refresh_response.user
        session = refresh_response.session
        
        # Get business information
        business_response = supabase.table("businesses").select("id").eq(
            "owner_id", user.id
        ).execute()
        
        business_id = business_response.data[0]["id"] if business_response.data else None
        
        expires_in = getattr(session, 'expires_in', 3600) if session else 3600
        
        return TokenResponse(
            access_token=session.access_token,
            user_id=user.id,
            email=user.email,
            role=user.user_metadata.get("role", "owner") if hasattr(user, 'user_metadata') and user.user_metadata else "owner",
            business_id=business_id,
            expires_in=expires_in
        )
        
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token refresh failed"
        )

@router.get("/me")
async def get_current_user_info(current_user=Depends(get_current_user)):
    """Get current user information."""
    return current_user

@router.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Logout endpoint - signs out user from Supabase."""
    supabase = get_supabase_client()
    
    try:
        # Set the session first
        supabase.auth.set_session(credentials.credentials, None)
        
        # Sign out from Supabase
        supabase.auth.sign_out()
        
        return {"success": True, "message": "Logged out successfully"}
    except Exception as e:
        logger.warning(f"Logout warning: {str(e)}")
        # Even if logout fails on server side, we return success
        # since client will clear tokens anyway
        return {"success": True, "message": "Logged out successfully"}
@router.post("/google/logout")

async def google_logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Logout Google user by deleting their session"""
    try:
        token = credentials.credentials
        
        if not token.startswith("google_session_"):
            raise HTTPException(status_code=400, detail="Not a Google session")
        
        session_token = token.replace("google_session_", "")
        
        supabase = get_supabase_client()
        supabase.table("google_sessions").delete().eq("session_token", session_token).execute()
        
        logger.info(f"Google session deleted: {session_token[:8]}...")
        return {"success": True, "message": "Logged out successfully"}
        
    except Exception as e:
        logger.warning(f"Google logout warning: {str(e)}")
        return {"success": True, "message": "Logged out successfully"}