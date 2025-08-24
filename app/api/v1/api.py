"""Main API router - Clean and Simple Version."""
from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth,
    business,
    menu,
    tables,
    orders,
    central_chat_endpoints as simple_chat,
    global_chat_endpoints as global_chat,
    dedicated_chat_endpoints as dedicated_chat,
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
    simple_chat.router,
    prefix="/chat",
    tags=["Simple Chat"]
)

api_router.include_router(
    global_chat.router,
    prefix="/global-chat",
    tags=["Global Chat"]
)

api_router.include_router(
    dedicated_chat.router,
    prefix="/dedicated-chat",
    tags=["Dedicated Chat"]
)