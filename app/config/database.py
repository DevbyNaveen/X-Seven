"""Pure Supabase database configuration."""
from typing import Optional
import logging
from app.config.settings import settings

# Supabase client (singleton)
_supabase_client: Optional['Client'] = None

def get_supabase_client():
    """Get Supabase client with proper error handling."""
    global _supabase_client
    
    if _supabase_client is None:
        try:
            from supabase import create_client, Client
            
            # Get credentials from settings
            SUPABASE_URL = settings.SUPABASE_URL
            SUPABASE_KEY = (
                settings.SUPABASE_SERVICE_ROLE_KEY or 
                settings.SUPABASE_KEY or 
                settings.SUPABASE_API_KEY
            )
            
            # Validate credentials exist
            if not SUPABASE_URL or not SUPABASE_KEY:
                raise ValueError("❌ Supabase credentials missing in .env file")
                
            # Create client
            _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
            logging.info("✅ Supabase client initialized successfully")
            
        except Exception as e:
            logging.error(f"❌ Failed to initialize Supabase: {e}")
            raise
    
    return _supabase_client

# ❌ REMOVE THIS CONFUSING FUNCTION:
# def get_db():
#     return get_supabase_client()