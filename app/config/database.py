"""Supabase database configuration."""
from typing import Optional
import logging
from app.config.settings import settings

# Supabase client (singleton)
_supabase_client: Optional['Client'] = None

def get_supabase_client() -> Optional['Client']:
    """Get Supabase client with error handling."""
    global _supabase_client
    
    if _supabase_client is None:
        try:
            from supabase import create_client, Client
            
            SUPABASE_URL = settings.SUPABASE_URL
            # Prefer service role key for server‑side operations
            # Choose the most privileged key available for server‑side operations
            SUPABASE_KEY = (
                settings.SUPABASE_SERVICE_ROLE_KEY
                or settings.SUPABASE_KEY
                or settings.SUPABASE_API_KEY
            )
            # Log which key source is being used (masking the actual value for security)
            if settings.SUPABASE_SERVICE_ROLE_KEY:
                key_source = "service_role"
            elif settings.SUPABASE_KEY:
                key_source = "anon"
            else:
                key_source = "api_key"
            logging.info(f"Supabase client initialized using {key_source} key")
            
            if SUPABASE_URL and SUPABASE_KEY:
                # Explicitly pass an empty options dict to prevent proxy issues
                _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
            else:
                raise ValueError("Supabase credentials not configured")
                
        except ImportError:
            logging.error("Supabase client not installed")
            raise
        except Exception as e:
            logging.error(f"Failed to initialize Supabase client: {e}")
            raise
    
    return _supabase_client

# Global supabase client - lazy initialization
def get_db():
    """Get Supabase client for database operations."""
    return get_supabase_client()

# Backward compatibility for legacy code
# TODO: Migrate all usage to get_supabase_client()
SessionLocal = get_supabase_client