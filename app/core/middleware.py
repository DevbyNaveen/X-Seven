"""Middleware for request processing, error handling, and rate limiting."""
import time
import logging
from typing import Callable
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import redis.asyncio as redis
from app.config.settings import settings

logger = logging.getLogger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware to ensure each request has a correlation ID.
    Adds/propagates `X-Request-ID` header and stores it in request.state.request_id.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            import uuid
            request_id = str(uuid.uuid4())

        # Attach to state for downstream usage
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware for handling unhandled exceptions."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            logger.error(f"Unhandled exception: {exc}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "error_type": type(exc).__name__
                }
            )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging all requests."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Log request
        logger.info(
            f"Request: {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'}"
        )
        
        response = await call_next(request)
        
        # Log response
        process_time = time.time() - start_time
        logger.info(
            f"Response: {response.status_code} "
            f"took {process_time:.3f}s"
        )
        
        # Add timing header
        response.headers["X-Process-Time"] = str(process_time)
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting requests."""
    
    def __init__(self, app: ASGIApp, redis_client: redis.Redis = None):
        super().__init__(app)
        self.redis = redis_client
        self.rate_limit_requests = 100  # requests per window
        self.rate_limit_window = 60  # seconds
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.redis:
            # Skip rate limiting if Redis is not available
            return await call_next(request)
        
        # Get client identifier (IP address or user ID)
        client_id = self._get_client_id(request)
        
        # Check rate limit
        if await self._is_rate_limited(client_id):
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after": self.rate_limit_window
                }
            )
        
        # Increment request count
        await self._increment_request_count(client_id)
        
        return await call_next(request)
    
    def _get_client_id(self, request: Request) -> str:
        """Get unique client identifier for rate limiting."""
        # Try to get user ID from token first
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            # In production, decode JWT to get user ID
            return f"user:{auth_header[7:20]}"  # Simplified for demo
        
        # Fall back to IP address
        return f"ip:{request.client.host if request.client else 'unknown'}"
    
    async def _is_rate_limited(self, client_id: str) -> bool:
        """Check if client has exceeded rate limit."""
        try:
            current_count = await self.redis.get(f"rate_limit:{client_id}")
            return current_count and int(current_count) >= self.rate_limit_requests
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            return False
    
    async def _increment_request_count(self, client_id: str):
        """Increment request count for client."""
        try:
            key = f"rate_limit:{client_id}"
            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, self.rate_limit_window)
            await pipe.execute()
        except Exception as e:
            logger.error(f"Rate limit increment failed: {e}")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware for adding security headers."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if settings.ENVIRONMENT.lower() == "production":
            response.headers["X-Frame-Options"] = "DENY"
        else:
            response.headers["Content-Security-Policy"] = (
                "frame-ancestors 'self' http://localhost:* http://127.0.0.1:*"
            )
        
        return response

