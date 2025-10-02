"""Simplified Supabase authentication helper with Google token support."""
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
import logging
import hashlib
import time
from app.config.database import get_supabase_client

logger = logging.getLogger(__name__)


async def verify_supabase_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify a Supabase access token using Supabase's built-in auth methods.
    Also handles JWT tokens created for Google users.
    """
    try:
        # Check if this is a Google session token FIRST
        if token.startswith("google_session_"):
            return await verify_google_session_token(token)
        
        from app.config.database import get_supabase_client
        
        # Get the Supabase client
        supabase = get_supabase_client()
        
        # Try Supabase's built-in token verification
        try:
            user_response = supabase.auth.get_user(token)
            
            if user_response and user_response.user:
                user = user_response.user
                
                return {
                    "sub": user.id,
                    "email": user.email,
                    "aud": "authenticated",
                    "role": "authenticated",
                    "user_metadata": user.user_metadata if hasattr(user, 'user_metadata') else {},
                    "app_metadata": user.app_metadata if hasattr(user, 'app_metadata') else {},
                    "iat": None,
                    "exp": None,
                }
            
        except Exception as auth_error:
            logger.warning(f"Supabase auth failed: {auth_error}")
            return None
            
        return None
            
    except Exception as e:
        logger.error(f"Error verifying token: {e}")
        return None
        
async def verify_google_session_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify a Google session token and return user information.
    Looks up the session in the database.
    """
    try:
        if not token.startswith("google_session_"):
            return None
            
        # Extract session token
        session_token = token.replace("google_session_", "")
        
        # Use service role client to bypass RLS
        from app.config.database import get_supabase_service_client
        supabase = get_supabase_service_client()
        
        # Look up session in database
        session_response = supabase.table("google_sessions").select("*").eq(
            "session_token", session_token
        ).execute()
        
        if not session_response.data:
            logger.warning(f"Google session not found: {session_token[:8]}...")
            return None
        
        session_data = session_response.data[0]
        
        # Check if session is expired
        current_time = int(time.time())
        if session_data["expires_at"] < current_time:
            logger.info(f"Google session expired for user {session_data['email']}")
            # Delete expired session
            supabase.table("google_sessions").delete().eq(
                "session_token", session_token
            ).execute()
            return None
        
        logger.info(f"Valid Google session found for user {session_data['email']}")
        
        # Parse created_at timestamp if it exists
        created_at_timestamp = None
        if session_data.get("created_at"):
            try:
                from datetime import datetime
                created_at_dt = datetime.fromisoformat(session_data["created_at"].replace('Z', '+00:00'))
                created_at_timestamp = int(created_at_dt.timestamp())
            except Exception as e:
                logger.warning(f"Could not parse created_at timestamp: {e}")
                created_at_timestamp = int(time.time())
        else:
            created_at_timestamp = int(time.time())
        
        return {
            "sub": session_data["user_id"],
            "email": session_data["email"],
            "aud": "authenticated",
            "role": "authenticated",
            "user_metadata": {
                "provider": "google",
                "google_id": session_data["google_id"]
            },
            "app_metadata": {},
            "iat": created_at_timestamp,
            "exp": session_data["expires_at"],
        }
        
    except Exception as e:
        logger.error(f"Error verifying Google session token: {e}")
        return None    
async def get_current_supabase_user(token: str) -> Dict[str, Any]:
    """
    Get current authenticated Supabase user from access token.
    Now supports both Supabase tokens and Google session tokens.
    
    Args:
        token: Supabase access token or Google session token
        
    Returns:
        User information dictionary
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No access token provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_data = await verify_supabase_token(token)
    
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user_data

async def get_current_user_with_business(token: str) -> dict:
    # Always use service role for business lookups
    from app.config.database import get_supabase_service_client
    supabase = get_supabase_service_client()
    
    payload = await verify_supabase_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    email = payload.get("email")
    user_id = payload.get("sub")  # This is from google_sessions
    
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    logger.info(f"Looking up business for user: {email}")

    try:
        # For Google users, we need to find by owner_id (from google_sessions)
        business_response = supabase.table("businesses").select("*").eq("owner_id", user_id).execute()
        
        if not business_response.data:
            # Fallback: try by email
            business_response = supabase.table("businesses").select("*").eq("email", email).execute()

        if business_response.data:
            business = business_response.data[0]
            logger.info(f"Found business: {business['id']} for user {email}")
            return {**payload, "business": business}
            
    except Exception as e:
        logger.error(f"Business query error: {e}")

    logger.error(f"Business not found for user {email}")
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Business account not found."
    )

async def get_google_user_with_business(token: str) -> Dict[str, Any]:
    """
    Get Google OAuth user with their business information.
    """
    try:
        user_data = await verify_google_session_token(token)
        
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired Google session",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        from app.config.database import get_supabase_service_client
        supabase = get_supabase_service_client()
        
        # Query by owner_id (NOT email)
        business_response = supabase.table("businesses").select("*").eq(
            "owner_id", user_data["sub"]  # user_data["sub"] is the user_id from google_sessions
        ).execute()
        
        if business_response.data:
            user_data["business"] = business_response.data[0]
        else:
            logger.warning(f"No business found for owner_id {user_data['sub']}")
        
        return user_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Google user with business: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google session",
            headers={"WWW-Authenticate": "Bearer"},
        ) 
# Legacy function for backward compatibility
def refresh_jwks_cache():
    """
    Legacy function kept for backward compatibility.
    Not needed with the new simplified authentication system.
    """
    logger.info("refresh_jwks_cache called - this function is deprecated and does nothing")
    return True

# Keep the manual JWT verification as a fallback (but we won't use it)
def _manual_jwt_verification_fallback(token: str) -> Optional[Dict[str, Any]]:
    """
    Fallback manual JWT verification (not recommended for production).
    This is kept for reference but we use Supabase's built-in methods instead.
    """
    logger.warning("Using manual JWT verification fallback - this should not happen in normal operation")
    
    try:
        import jwt
        from app.config.settings import settings
        
        if not settings.SUPABASE_JWT_SECRET:
            logger.error("JWT secret not configured for manual verification")
            return None
            
        # Simple HS256 verification without audience/issuer validation
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False, "verify_iss": False}
        )
        
        logger.info("Manual JWT verification successful")
        return payload
        
    except Exception as e:
        logger.error(f"Manual JWT verification failed: {e}")
        return None