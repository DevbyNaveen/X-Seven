from typing import Optional, Dict, Any
from fastapi import HTTPException, status
import jwt
import logging
import requests
import time
from jose import jwk, jwt
from jose.utils import base64url_decode
from app.config.settings import settings

# Cache for JWKS keys
_JWKS_CACHE = None
_JWKS_CACHE_TIME = 0
_JWKS_CACHE_DURATION = 300  # 5 minutes


def refresh_jwks_cache():
    """Manually refresh the JWKS cache."""
    global _JWKS_CACHE, _JWKS_CACHE_TIME
    _JWKS_CACHE = None
    _JWKS_CACHE_TIME = 0
    try:
        jwks = get_supabase_jwks()
        return jwks is not None
    except:
        return False


def get_supabase_jwks():
    """Fetch Supabase JWKS (JSON Web Key Set) for token verification with caching."""
    global _JWKS_CACHE, _JWKS_CACHE_TIME
    
    # Check if we have a valid cached version
    current_time = time.time()
    if _JWKS_CACHE and (current_time - _JWKS_CACHE_TIME) < _JWKS_CACHE_DURATION:
        return _JWKS_CACHE
    
    if not settings.SUPABASE_URL:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase URL not configured"
        )
    
    jwks_url = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
    try:
        response = requests.get(jwks_url, timeout=10)
        response.raise_for_status()
        jwks_data = response.json()
        
        # Update cache
        _JWKS_CACHE = jwks_data
        _JWKS_CACHE_TIME = current_time
        
        return jwks_data
    except Exception as e:
        logging.error(f"Failed to fetch Supabase JWKS: {e}")
        # If we have a cached version, use it even if it's expired
        if _JWKS_CACHE:
            logging.warning("Using expired JWKS cache due to fetch failure")
            return _JWKS_CACHE
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch Supabase JWKS keys"
        )

async def verify_supabase_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify a Supabase JWT token using either HS256 (with JWT secret) or RS256 (with JWKS).
    
    Args:
        token: Supabase JWT token
        
    Returns:
        Token payload if valid, None otherwise
    """
    try:
        # First, decode without verification to get the kid (key ID) and algorithm
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        alg = unverified_header.get("alg", "HS256")
        
        # If it's HS256, verify using the JWT secret
        if alg == "HS256":
            if not settings.SUPABASE_JWT_SECRET:
                logging.error("Supabase JWT secret not configured for HS256 token verification")
                return None
                
            # Verify the token using HS256 and the JWT secret
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
                issuer=f"{settings.SUPABASE_URL}/auth/v1"
            )
            return payload
            
        # If it's RS256, verify using JWKS
        elif alg == "RS256":
            if not kid:
                logging.error("No 'kid' in token header for RS256 token")
                return None
                
            # Get the JWKS and find the matching key
            try:
                jwks = get_supabase_jwks()
                if not jwks:
                    logging.error("Failed to fetch Supabase JWKS")
                    return None
                    
                key = None
                for jwk_key in jwks.get("keys", []):
                    if jwk_key.get("kid") == kid:
                        key = jwk_key
                        break
                        
                if not key:
                    logging.error(f"No matching key found for kid: {kid}")
                    # Force refresh cache and try again
                    global _JWKS_CACHE, _JWKS_CACHE_TIME
                    _JWKS_CACHE = None
                    _JWKS_CACHE_TIME = 0
                    jwks = get_supabase_jwks()
                    if jwks:
                        for jwk_key in jwks.get("keys", []):
                            if jwk_key.get("kid") == kid:
                                key = jwk_key
                                break
                    
                    if not key:
                        logging.error(f"Still no matching key found for kid: {kid} after cache refresh")
                        return None
                
                # Verify the token
                public_key = jwk.construct(key)
                payload = jwt.decode(
                    token,
                    key=public_key.to_pem().decode('utf-8') if hasattr(public_key, 'to_pem') else public_key,
                    algorithms=["RS256"],
                    audience="authenticated",
                    issuer=f"{settings.SUPABASE_URL}/auth/v1"
                )
                return payload
            except Exception as e:
                logging.error(f"Error during RS256 token verification: {e}", exc_info=True)
                return None
            
        else:
            logging.error(f"Unsupported algorithm: {alg}")
            return None
        
    except jwt.ExpiredSignatureError:
        logging.warning("Supabase token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Supabase token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTClaimsError as e:
        logging.error(f"Token claims error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token claims: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTError as e:
        logging.error(f"JWT validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logging.error(f"Error verifying Supabase token: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not verify Supabase token",
            headers={"WWW-Authenticate": "Bearer"},
        )
