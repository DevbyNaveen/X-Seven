"""Fixed Supabase database configuration with proper options format."""
from typing import Optional
import logging
from app.config.settings import settings

# Global client instances
_supabase_client: Optional[object] = None
_supabase_service_client: Optional[object] = None

logger = logging.getLogger(__name__)

def get_supabase_client():
    """
    Get Supabase client for user-authenticated requests.
    This client uses the anon key and relies on user sessions for authentication.
    """
    global _supabase_client
    
    if _supabase_client is None:
        try:
            from supabase import create_client, Client
            
            # Get credentials from settings
            SUPABASE_URL = settings.SUPABASE_URL
            # Use anon key for user-authenticated requests
            SUPABASE_ANON_KEY = settings.SUPABASE_KEY or settings.SUPABASE_API_KEY
            
            # Validate credentials exist
            if not SUPABASE_URL or not SUPABASE_ANON_KEY:
                raise ValueError("Supabase credentials missing in .env file")
                
            # Create client with simple configuration (no complex options)
            _supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
            logger.info("Supabase client (anon) initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            raise
    
    return _supabase_client

def get_supabase_service_client():
    """
    Get Supabase client with service role for admin operations.
    This bypasses RLS and should only be used for system operations.
    """
    global _supabase_service_client
    
    if _supabase_service_client is None:
        try:
            from supabase import create_client, Client
            
            # Get credentials from settings
            SUPABASE_URL = settings.SUPABASE_URL
            SUPABASE_SERVICE_KEY = settings.SUPABASE_SERVICE_ROLE_KEY
            
            # Validate credentials exist
            if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
                logger.warning("Service role key not available - some admin operations may not work")
                return None
                
            # Create client with service role key (simple configuration)
            _supabase_service_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
            logger.info("Supabase service client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Supabase service client: {e}")
            return None
    
    return _supabase_service_client

def get_authenticated_supabase_client(access_token: str):
    """
    Get a Supabase client with authentication context for a specific request.
    This creates a client instance with the user's session for this request only.
    """
    try:
        from supabase import create_client
        
        # Get credentials from settings
        SUPABASE_URL = settings.SUPABASE_URL
        SUPABASE_ANON_KEY = settings.SUPABASE_KEY or settings.SUPABASE_API_KEY
        
        # Create a new client instance for this request (simple configuration)
        client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        
        # Set the session with the provided access token
        try:
            client.auth.set_session(access_token, None)
            logger.debug(f"Set session for authenticated request")
        except Exception as session_error:
            logger.error(f"Failed to set session: {session_error}")
            raise
        
        return client
        
    except Exception as e:
        logger.error(f"Failed to create authenticated Supabase client: {e}")
        raise

def test_supabase_connection():
    """
    Test Supabase connection and authentication.
    Returns True if connection is successful, False otherwise.
    """
    try:
        client = get_supabase_client()
        
        # Try a simple query that doesn't require authentication
        response = client.table("businesses").select("id").limit(1).execute()
        
        logger.info("Supabase connection test successful")
        return True
        
    except Exception as e:
        logger.error(f"Supabase connection test failed: {e}")
        return False

# For backward compatibility - but prefer using get_supabase_client() directly
def get_db():
    """
    Deprecated: Use get_supabase_client() instead.
    Kept for backward compatibility.
    """
    logger.warning("get_db() is deprecated. Use get_supabase_client() instead.")
    return get_supabase_client()