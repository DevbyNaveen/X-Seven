"""Common dependencies for API endpoints."""
from typing import Generator, Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError 
from app.config.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.models.business import Business

# This scheme is for dependencies that REQUIRE a token
oauth2_scheme_strict = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# This scheme is for OPTIONAL tokens. It won't error if the token is missing.
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: str = Depends(oauth2_scheme_strict),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token. This is a strict dependency
    and will raise an error if the user is not found or the token is invalid.
    """
    try:
        payload = decode_access_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get email from token (sub field)
    email: str = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    
    # Find user by email
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )
    
    return user


async def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Gets the current user if a token is provided, but returns None
    instead of raising an error if the token is missing or invalid.
    """
    if token is None:
        return None
    try:
        payload = decode_access_token(token)
        if not payload:
            return None

        # Get email from token (sub field)
        email: str = payload.get("sub")
        if not email:
            return None

        user = db.query(User).filter(User.email == email).first()
        if not user or not user.is_active:
            return None

        return user
    except (JWTError, Exception):
        # If any error occurs during token processing, treat as a guest user.
        return None


async def get_current_business(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Business:
    """
    Get the business associated with current user.
    """
    business = db.query(Business).filter(Business.id == current_user.business_id).first()
    
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found"
        )
    
    if not business.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Business is inactive"
        )
    
    return business


async def get_current_business_optional(
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
) -> Optional[Business]:
    """
    Get the business associated with current user (optional).
    Returns None if no user or business found.
    """
    if not current_user:
        return None
    
    business = db.query(Business).filter(Business.id == current_user.business_id).first()
    return business if business and business.is_active else None


def get_multi_tenant_filter(business_id: int):
    """
    Create a filter for multi-tenant data access.
    """
    return {"business_id": business_id}