from typing import Optional
from app.config.settings import settings
import logging

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
                logging.warning("Supabase credentials missing, creating mock client for development")
                # Create a mock client for development
                class MockSupabaseClient:
                    def table(self, *args, **kwargs):
                        class MockTable:
                            def select(self, *args, **kwargs): return self
                            def insert(self, *args, **kwargs): return self
                            def update(self, *args, **kwargs): return self
                            def delete(self, *args, **kwargs): return self
                            def execute(self): return {"data": [], "error": None}
                        return MockTable()
                    def auth(self):
                        class MockAuth:
                            def sign_up(self, *args, **kwargs): return {"user": None, "error": "Mock client"}
                            def sign_in_with_password(self, *args, **kwargs): return {"user": None, "error": "Mock client"}
                        return MockAuth()
                _supabase_client = MockSupabaseClient()
                return _supabase_client
                
            # Create client - use basic initialization to avoid proxy issues
            _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
            logging.info("✅ Supabase client initialized successfully")
            
        except Exception as e:
            logging.error(f"❌ Failed to initialize Supabase: {e}")
            # Return mock client as fallback
            class MockSupabaseClient:
                def table(self, *args, **kwargs):
                    class MockTable:
                        def select(self, *args, **kwargs): return self
                        def insert(self, *args, **kwargs): return self
                        def update(self, *args, **kwargs): return self
                        def delete(self, *args, **kwargs): return self
                        def execute(self): return {"data": [], "error": None}
                    return MockTable()
                def auth(self):
                    class MockAuth:
                        def sign_up(self, *args, **kwargs): return {"user": None, "error": "Mock client"}
                        def sign_in_with_password(self, *args, **kwargs): return {"user": None, "error": "Mock client"}
                    return MockAuth()
            _supabase_client = MockSupabaseClient()
    
    return _supabase_client

# ❌ REMOVE THIS CONFUSING FUNCTION:
# def get_db():
#     return get_supabase_client()
