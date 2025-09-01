from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import Any, Optional
import jwt
import logging
import requests
from jose import JWTError

from app.config.database import get_db
from app.config.settings import settings
from app.models import User, Business
from app.schemas.auth import Token
from app.core.security import create_access_token, create_refresh_token
from datetime import timedelta

router = APIRouter()

async def verify_supabase_token(supabase_token: str, db: Session) -> dict:
    """
    Verify Supabase JWT token using Supabase's GoTrue service
    """
    try:
        # For production, you should verify the token with Supabase's GoTrue service
        # This is a simplified version that decodes the token
        
        # Get the Supabase JWT secret (you need to get this from your Supabase dashboard)
        supabase_jwt_secret = getattr(settings, 'SUPABASE_JWT_SECRET', None)
        
        if not supabase_jwt_secret:
            # Fallback to using the public key for basic verification
            # In production, use the JWT secret from Supabase dashboard
            supabase_jwt_secret = settings.SUPABASE_API_KEY
            
        if not supabase_jwt_secret:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Supabase JWT configuration missing"
            )
        
        # Decode the token
        payload = jwt.decode(supabase_token, supabase_jwt_secret, algorithms=["HS256"])
        return payload
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Supabase token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Supabase token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logging.error(f"Error verifying Supabase token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not verify Supabase token",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.post("/supabase/login", response_model=Token)
async def login_with_supabase_token(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> Any:
    """
    Login using a Supabase JWT token from Authorization header and map to existing user system
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header with Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    supabase_token = authorization.split("Bearer ")[1]
    
    # Verify the Supabase token
    payload = await verify_supabase_token(supabase_token, db)
    
    # Extract user info from Supabase token
    supabase_user_id = payload.get("sub")
    email = payload.get("email")
    
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not found in Supabase token"
        )
    
    # Find user in your system
    user = db.query(User).filter(User.email == email).first()
    
    # If user doesn't exist, you might want to create them
    # This depends on your business logic
    if not user:
        # For now, we'll raise an error
        # You can modify this to auto-create users if needed
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in system. Please register first."
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    # Create your internal tokens
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "business_id": user.business_id, "supabase_uid": supabase_user_id},
        expires_delta=access_token_expires,
    )
    refresh_token = create_refresh_token(data={"sub": user.email, "business_id": user.business_id, "supabase_uid": supabase_user_id})
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        business_id=user.business_id,
        user_role=user.role,
        refresh_token=refresh_token,
    )

@router.post("/supabase/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register_with_supabase(
    email: str,
    name: str,
    business_name: str,
    business_slug: str,
    supabase_user_id: str,
    db: Session = Depends(get_db)
) -> Any:
    """
    Register a new user and business with Supabase user ID
    """
    from app.core.exceptions import DuplicateError
    from app.models import UserRole, SubscriptionPlan
    
    # Check if business slug already exists
    existing_business = db.query(Business).filter(
        Business.slug == business_slug
    ).first()
    
    if existing_business:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Business slug already exists"
        )
    
    # Check if email already exists
    existing_user = db.query(User).filter(
        User.email == email
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Create business with trial access
    business = Business(
        name=business_name,
        slug=business_slug,
        subscription_plan=SubscriptionPlan.BASIC,  # Start with basic plan (trial)
        subscription_status="trial",  # Mark as trial
        is_active=True,
        contact_info={
            "email": email
        }
    )
    db.add(business)
    db.commit()
    db.refresh(business)
    
    # Create user
    user = User(
        email=email,
        name=name,
        role=UserRole.OWNER,
        business_id=business.id,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create tokens
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "business_id": business.id, "supabase_uid": supabase_user_id},
        expires_delta=access_token_expires,
    )
    refresh_token = create_refresh_token(data={"sub": user.email, "business_id": business.id, "supabase_uid": supabase_user_id})
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        business_id=business.id,
        user_role=user.role,
        refresh_token=refresh_token,
    )
