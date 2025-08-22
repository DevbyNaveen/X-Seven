"""Universal entry endpoints.

These endpoints serve the universal number/ID routing. For now we expose a
basic health check and a placeholder that can be expanded with WhatsApp/web chat
webhooks.
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "universal"}
