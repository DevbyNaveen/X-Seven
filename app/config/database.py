"""Database configuration and session management."""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session
from typing import Generator, Optional
import logging

from app.config.settings import settings

# Database URLs
SQLALCHEMY_DATABASE_URL = "sqlite:///./cafe2211.db"

# Create SQLAlchemy engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for SQLAlchemy models
Base = declarative_base()

# Supabase client (lazy initialization)
_supabase_client: Optional['Client'] = None

def get_supabase_client() -> Optional['Client']:
    """Get Supabase client with error handling."""
    global _supabase_client
    
    if _supabase_client is None:
        try:
            from supabase import create_client, Client
            
            SUPABASE_URL = settings.SUPABASE_URL
            SUPABASE_KEY = settings.SUPABASE_API_KEY
            
            if SUPABASE_URL and SUPABASE_KEY:
                _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
            else:
                logging.warning("Supabase credentials not configured")
                return None
                
        except ImportError:
            logging.error("Supabase client not installed")
            return None
        except Exception as e:
            logging.error(f"Failed to initialize Supabase client: {e}")
            return None
    
    return _supabase_client

# Backward compatibility
supabase = get_supabase_client()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get database session.
    
    This is a generator that:
    1. Creates a new session
    2. Yields it to the endpoint
    3. Closes it after the request
    
    Usage:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()