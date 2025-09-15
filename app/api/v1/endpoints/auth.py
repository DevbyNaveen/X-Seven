"""Authentication endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.schemas.auth import TokenResponse
from app.core.dependencies import get_current_user

router = APIRouter()
security = HTTPBearer()

@router.post("/login", response_model=TokenResponse)
async def login():
    """User login endpoint."""
    # Implementation would go here
    pass

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token():
    """Token refresh endpoint."""
    # Implementation would go here
    pass

@router.get("/me")
async def get_current_user_info(current_user=Depends(get_current_user)):
    """Get current user information."""
    return current_user
