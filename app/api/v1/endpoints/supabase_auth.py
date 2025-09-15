"""
Direct Supabase registration endpoint - handles business registration 
and user creation with JWT token return.
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import Any
import uuid
import logging
from datetime import datetime

from app.config.database import get_supabase_client
from app.schemas.auth import RegisterBusinessRequest, TokenResponse, LoginRequest

router = APIRouter()

@router.post("/supabase/register", status_code=status.HTTP_201_CREATED, response_model=TokenResponse)
async def direct_supabase_register(
    request: RegisterBusinessRequest,
    supabase = Depends(get_supabase_client)
) -> Any:
    """
    Direct Supabase registration - creates both business record and admin user,
    then returns a JWT token for immediate authentication.
    
    This endpoint allows users to register their business and get authenticated
    immediately with a JWT token.
    
    Returns: JWT token and user/business details for immediate use
    """
    try:
        # Check if business slug already exists
        business_response = supabase.table("businesses").select("*").eq("slug", request.business_slug).execute()
        if business_response.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Business slug already exists"
            )

        # Check if business with this email already exists
        email_business_response = supabase.table("businesses").select("*").eq("contact_info->>email", request.admin_email).execute()
        if email_business_response.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Business with this email already exists"
            )

        # Create Supabase auth user
        try:
            auth_response = supabase.auth.sign_up({
                "email": request.admin_email,
                "password": request.admin_password,
                "options": {
                    "data": {
                        "full_name": request.admin_name,
                        "phone": request.admin_phone
                    }
                }
            })
            
            if not auth_response or not auth_response.user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create auth user"
                )
                
            user_id = auth_response.user.id
            
        except Exception as auth_error:
            logging.error(f"Error creating Supabase auth user: {auth_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user account"
            )

        # Create business with trial access
        business_id = str(uuid.uuid4())
        business_data = {
            "id": business_id,
            "name": request.business_name,
            "slug": request.business_slug,
            "subscription_plan": "basic",
            "subscription_status": "trial",
            "is_active": True,
            "contact_info": {"email": request.admin_email},
            "category": request.business_category.value if request.business_category else None,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        business_response = supabase.table("businesses").insert(business_data).execute()
        if not business_response.data:
            # Try to clean up the auth user if business creation fails
            try:
                supabase.auth.admin.delete_user(user_id)
            except Exception as cleanup_error:
                logging.error(f"Failed to cleanup auth user after business creation failure: {cleanup_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create business"
            )

        # Update business with owner info
        business_update_data = {
            "owner_id": user_id,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        business_update_response = supabase.table("businesses").update(business_update_data).eq("id", business_id).execute()
        if not business_update_response.data:
            # Try to clean up both auth user and business if update fails
            try:
                supabase.auth.admin.delete_user(user_id)
                supabase.table("businesses").delete().eq("id", business_id).execute()
            except Exception as cleanup_error:
                logging.error(f"Failed to cleanup after business update failure: {cleanup_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update business with owner info"
            )

        # Sign in the user to get JWT token
        try:
            sign_in_response = supabase.auth.sign_in_with_password({
                "email": request.admin_email,
                "password": request.admin_password
            })
            
            if not sign_in_response or not sign_in_response.session:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to authenticate user after registration"
                )
                
            session = sign_in_response.session
            
        except Exception as sign_in_error:
            logging.error(f"Error signing in user after registration: {sign_in_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to authenticate user after registration"
            )

        # Return token response
        return {
            "access_token": session.access_token,
            "token_type": "bearer",
            "user_id": str(user_id),
            "email": request.admin_email,
            "role": "owner",
            "business_id": business_id,
            "expires_in": session.expires_in
        }

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in direct registration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@router.post("/supabase/login", status_code=status.HTTP_200_OK, response_model=TokenResponse)
async def supabase_login(
    request: LoginRequest,
    supabase = Depends(get_supabase_client)
) -> Any:
    """
    Login endpoint that authenticates user with Supabase Auth and returns JWT token.
    
    Returns: JWT token and user details for authenticated requests
    """
    try:
        # Authenticate user with Supabase
        try:
            auth_response = supabase.auth.sign_in_with_password({
                "email": request.email,
                "password": request.password
            })
            
            if not auth_response or not auth_response.session:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials"
                )
                
            session = auth_response.session
            user = auth_response.user
            
        except Exception as auth_error:
            logging.error(f"Error authenticating user: {auth_error}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        # Get business details for the user
        try:
            business_response = supabase.table("businesses").select("*").eq("owner_id", user.id).execute()
            business_data = business_response.data[0] if business_response.data else None
            
        except Exception as business_error:
            logging.error(f"Error fetching business details: {business_error}")
            business_data = None

        # Return token response
        return {
            "access_token": session.access_token,
            "token_type": "bearer",
            "user_id": str(user.id),
            "email": user.email,
            "role": "owner" if business_data else "user",
            "business_id": business_data.get("id") if business_data else None,
            "expires_in": session.expires_in
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in login: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )
