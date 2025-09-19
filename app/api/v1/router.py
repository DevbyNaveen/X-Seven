"""
Main API router - Mounts all AI service endpoints
"""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    global_endpoints,
    dedicated_endpoints,
    dashboard_endpoints,
    analytics_endpoints
)

# Create main router
api_router = APIRouter()

# Include all service routers
api_router.include_router(global_endpoints.router)
api_router.include_router(dedicated_endpoints.router)
api_router.include_router(dashboard_endpoints.router)
api_router.include_router(analytics_endpoints.router)
