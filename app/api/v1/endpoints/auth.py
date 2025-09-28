"""Authentication endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.schemas.auth import TokenResponse, LoginRequest
from app.core.dependencies import get_current_user
from app.config.database import get_supabase_client
import logging

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger(__name__)

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
        
        # Get business information - fix the query syntax
        business_response = supabase.table("businesses").select("*").or_(
            f"email.ilike.{credentials.email},owner_id.eq.{user.id}"
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
            role=user.user_metadata.get("role", "owner") if hasattr(user, 'user_metadata') else "owner",
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

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Refresh token endpoint."""
    supabase = get_supabase_client()
    
    try:
        # Use the access token to refresh session
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
            role=user.user_metadata.get("role", "owner") if hasattr(user, 'user_metadata') else "owner",
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
async def logout():
    """Logout endpoint - client will clear local storage."""
    return {"success": True, "message": "Logged out successfully"}