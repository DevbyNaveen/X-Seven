"""Main API router - Clean and Simple Version."""
from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth,
    business,
    menu,
    tables,
    orders,
    dashboard,
    central_chat_endpoints as central_chat,
    global_chat_endpoints as global_chat,
)

# Create main router
api_router = APIRouter()

# Include only essential endpoint routers
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"]
)

api_router.include_router(
    business.router,
    prefix="/business",
    tags=["Business Management"]
)

api_router.include_router(
    menu.router,
    prefix="/menu",
    tags=["Menu Management"]
)

api_router.include_router(
    tables.router,
    prefix="/tables",
    tags=["Table Management"]
)

api_router.include_router(
    orders.router,
    prefix="/orders",
    tags=["Order Management"]
)

api_router.include_router(
    dashboard.router,
    prefix="/dashboard",
    tags=["Dashboard"]
)

api_router.include_router(
    central_chat.router,
    prefix="/chat",
    tags=["Central Chat"]
)

api_router.include_router(
    global_chat.router,
    prefix="/global",
    tags=["Global Chat"]
)



