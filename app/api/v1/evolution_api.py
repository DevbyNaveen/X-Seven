"""Evolution API endpoints for multi-tenant WhatsApp and phone management."""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.models.business import Business
from app.models.evolution_instance import EvolutionInstance, EvolutionMessage
from app.services.evolution.manager import EvolutionManager, EvolutionManagerError
from app.services.evolution.webhook_handler import EvolutionWebhookHandler
from app.core.auth import get_current_business, get_current_user
from app.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/evolution", tags=["Evolution API"])


# Pydantic Models for Request/Response

class EvolutionSetupRequest(BaseModel):
    """Request model for Evolution API setup."""
    country_code: str = Field(..., description="Country code for phone number (e.g., 'US', 'LV')")
    enable_whatsapp: bool = Field(True, description="Enable WhatsApp Business integration")
    business_profile: Optional[Dict[str, Any]] = Field(None, description="WhatsApp Business profile data")


class EvolutionStatusResponse(BaseModel):
    """Response model for Evolution API status."""
    configured: bool
    instance_name: Optional[str] = None
    phone_number: Optional[str] = None
    status: Optional[str] = None
    whatsapp_enabled: Optional[bool] = None
    whatsapp_status: Optional[str] = None
    monthly_cost: Optional[float] = None
    usage_stats: Optional[Dict[str, Any]] = None
    last_activity: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    connection_info: Optional[Dict[str, Any]] = None


class SendMessageRequest(BaseModel):
    """Request model for sending messages."""
    customer_number: str = Field(..., description="Customer phone number")
    message: str = Field(..., description="Message content")
    message_type: str = Field("text", description="Message type")


class MessageResponse(BaseModel):
    """Response model for message operations."""
    success: bool
    message_id: Optional[str] = None
    status: Optional[str] = None
    error: Optional[str] = None


# Business Evolution API Management Endpoints

@router.post("/{business_id}/setup", response_model=Dict[str, Any])
async def setup_business_evolution(
    business_id: int,
    setup_request: EvolutionSetupRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_business: Business = Depends(get_current_business)
):
    """
    Setup Evolution API instance for a business.
    
    This endpoint handles the complete onboarding process:
    1. Phone number provisioning
    2. Evolution instance creation
    3. WhatsApp Business setup
    4. AI integration configuration
    """
    try:
        # Verify business ownership or admin access
        if current_business.id != business_id:
            raise HTTPException(status_code=403, detail="Access denied to this business")
        
        # Check if business plan supports Evolution API
        if current_business.subscription_plan == "basic":
            raise HTTPException(
                status_code=400, 
                detail="Evolution API requires Pro or Enterprise subscription"
            )
        
        async with EvolutionManager(db) as evolution_manager:
            result = await evolution_manager.onboard_business_evolution(
                business_id=business_id,
                country_code=setup_request.country_code,
                enable_whatsapp=setup_request.enable_whatsapp,
                business_profile=setup_request.business_profile
            )
        
        logger.info(f"Evolution API setup completed for business {business_id}")
        
        return {
            "success": True,
            "message": "Evolution API setup completed successfully",
            "data": result
        }
        
    except EvolutionManagerError as e:
        logger.error(f"Evolution setup failed for business {business_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during Evolution setup for business {business_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{business_id}/status", response_model=EvolutionStatusResponse)
async def get_business_evolution_status(
    business_id: int,
    db: Session = Depends(get_db),
    current_business: Business = Depends(get_current_business)
):
    """Get Evolution API status for a business."""
    try:
        # Verify business ownership or admin access
        if current_business.id != business_id:
            raise HTTPException(status_code=403, detail="Access denied to this business")
        
        async with EvolutionManager(db) as evolution_manager:
            status = await evolution_manager.get_business_evolution_status(business_id)
        
        return EvolutionStatusResponse(**status)
        
    except Exception as e:
        logger.error(f"Failed to get Evolution status for business {business_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get status")


@router.post("/{business_id}/restart")
async def restart_business_instance(
    business_id: int,
    db: Session = Depends(get_db),
    current_business: Business = Depends(get_current_business)
):
    """Restart Evolution API instance for a business."""
    try:
        # Verify business ownership or admin access
        if current_business.id != business_id:
            raise HTTPException(status_code=403, detail="Access denied to this business")
        
        async with EvolutionManager(db) as evolution_manager:
            result = await evolution_manager.restart_business_instance(business_id)
        
        return {
            "success": True,
            "message": "Instance restart initiated",
            "data": result
        }
        
    except EvolutionManagerError as e:
        logger.error(f"Failed to restart instance for business {business_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error restarting instance for business {business_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{business_id}/qr-code")
async def get_whatsapp_qr_code(
    business_id: int,
    db: Session = Depends(get_db),
    current_business: Business = Depends(get_current_business)
):
    """Get WhatsApp QR code for business instance."""
    try:
        # Verify business ownership or admin access
        if current_business.id != business_id:
            raise HTTPException(status_code=403, detail="Access denied to this business")
        
        async with EvolutionManager(db) as evolution_manager:
            qr_result = await evolution_manager.get_whatsapp_qr_code(business_id)
        
        return {
            "success": True,
            "data": qr_result
        }
        
    except EvolutionManagerError as e:
        logger.error(f"Failed to get QR code for business {business_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting QR code for business {business_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Messaging Endpoints

@router.post("/{business_id}/send-message", response_model=MessageResponse)
async def send_message_to_customer(
    business_id: int,
    message_request: SendMessageRequest,
    db: Session = Depends(get_db),
    current_business: Business = Depends(get_current_business)
):
    """Send message to customer via business Evolution instance."""
    try:
        # Verify business ownership or admin access
        if current_business.id != business_id:
            raise HTTPException(status_code=403, detail="Access denied to this business")
        
        async with EvolutionManager(db) as evolution_manager:
            result = await evolution_manager.send_message_to_customer(
                business_id=business_id,
                customer_number=message_request.customer_number,
                message=message_request.message,
                message_type=message_request.message_type
            )
        
        return MessageResponse(**result)
        
    except EvolutionManagerError as e:
        logger.error(f"Failed to send message for business {business_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error sending message for business {business_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{business_id}/messages")
async def get_business_messages(
    business_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_business: Business = Depends(get_current_business)
):
    """Get messages for a business."""
    try:
        # Verify business ownership or admin access
        if current_business.id != business_id:
            raise HTTPException(status_code=403, detail="Access denied to this business")
        
        async with EvolutionManager(db) as evolution_manager:
            messages = await evolution_manager.get_business_messages(
                business_id=business_id,
                limit=limit,
                offset=offset
            )
        
        return {
            "success": True,
            "data": {
                "messages": messages,
                "limit": limit,
                "offset": offset,
                "total": len(messages)
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get messages for business {business_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get messages")


# Analytics and Monitoring Endpoints

@router.get("/{business_id}/analytics")
async def get_business_analytics(
    business_id: int,
    days: int = 30,
    db: Session = Depends(get_db),
    current_business: Business = Depends(get_current_business)
):
    """Get analytics for a business Evolution instance."""
    try:
        # Verify business ownership or admin access
        if current_business.id != business_id:
            raise HTTPException(status_code=403, detail="Access denied to this business")
        
        async with EvolutionManager(db) as evolution_manager:
            analytics = await evolution_manager.get_business_analytics(
                business_id=business_id,
                days=days
            )
        
        return {
            "success": True,
            "data": analytics
        }
        
    except Exception as e:
        logger.error(f"Failed to get analytics for business {business_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get analytics")


# Webhook Endpoints

@router.post("/webhook/{instance_name}")
async def handle_evolution_webhook(
    instance_name: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Handle incoming webhooks from Evolution API.
    
    This endpoint processes all webhook events from Evolution API instances
    and triggers appropriate actions like AI responses, status updates, etc.
    """
    try:
        # Get request data
        event_data = await request.json()
        headers = dict(request.headers)
        
        # Log webhook receipt
        logger.info(f"Received webhook for instance {instance_name}: {event_data.get('event', 'unknown')}")
        
        # Process webhook in background
        background_tasks.add_task(
            process_webhook_background,
            instance_name,
            event_data,
            headers,
            db
        )
        
        return {"success": True, "message": "Webhook received and queued for processing"}
        
    except Exception as e:
        logger.error(f"Failed to handle webhook for {instance_name}: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Failed to process webhook"}
        )


async def process_webhook_background(
    instance_name: str,
    event_data: Dict[str, Any],
    headers: Dict[str, str],
    db: Session
):
    """Background task to process webhook events."""
    try:
        webhook_handler = EvolutionWebhookHandler(db)
        result = await webhook_handler.process_webhook(instance_name, event_data, headers)
        
        if result.get("success"):
            logger.info(f"Successfully processed webhook for {instance_name}")
        else:
            logger.error(f"Failed to process webhook for {instance_name}: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"Background webhook processing failed for {instance_name}: {e}")


# Admin Endpoints (for platform administrators)

@router.get("/admin/instances")
async def list_all_evolution_instances(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """List all Evolution instances (admin only)."""
    try:
        # Check if user is admin (implement your admin check logic)
        if not getattr(current_user, 'is_admin', False):
            raise HTTPException(status_code=403, detail="Admin access required")
        
        instances = db.query(EvolutionInstance).all()
        
        return {
            "success": True,
            "data": [
                {
                    "id": instance.id,
                    "business_id": instance.business_id,
                    "instance_name": instance.instance_name,
                    "phone_number": instance.phone_number,
                    "status": instance.status,
                    "whatsapp_status": instance.whatsapp_status,
                    "monthly_cost": instance.monthly_cost,
                    "created_at": instance.created_at,
                    "last_activity": instance.last_activity
                }
                for instance in instances
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to list Evolution instances: {e}")
        raise HTTPException(status_code=500, detail="Failed to list instances")


@router.get("/admin/webhook-stats")
async def get_webhook_statistics(
    days: int = 7,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get webhook processing statistics (admin only)."""
    try:
        # Check if user is admin
        if not getattr(current_user, 'is_admin', False):
            raise HTTPException(status_code=403, detail="Admin access required")
        
        webhook_handler = EvolutionWebhookHandler(db)
        stats = await webhook_handler.get_webhook_statistics(days)
        
        return {
            "success": True,
            "data": stats
        }
        
    except Exception as e:
        logger.error(f"Failed to get webhook statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")


@router.post("/admin/cleanup-webhooks")
async def cleanup_old_webhook_events(
    days: int = 30,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Clean up old webhook events (admin only)."""
    try:
        # Check if user is admin
        if not getattr(current_user, 'is_admin', False):
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Run cleanup in background
        background_tasks.add_task(cleanup_webhooks_background, days, db)
        
        return {
            "success": True,
            "message": f"Webhook cleanup initiated for events older than {days} days"
        }
        
    except Exception as e:
        logger.error(f"Failed to initiate webhook cleanup: {e}")
        raise HTTPException(status_code=500, detail="Failed to initiate cleanup")


async def cleanup_webhooks_background(days: int, db: Session):
    """Background task to clean up old webhook events."""
    try:
        webhook_handler = EvolutionWebhookHandler(db)
        await webhook_handler.cleanup_old_webhook_events(days)
        logger.info(f"Webhook cleanup completed for events older than {days} days")
    except Exception as e:
        logger.error(f"Webhook cleanup failed: {e}")


# Health Check Endpoint

@router.get("/health")
async def evolution_health_check():
    """Health check endpoint for Evolution API integration."""
    try:
        from app.services.evolution.client import EvolutionAPIClient
        
        async with EvolutionAPIClient() as client:
            health_result = await client.health_check()
        
        return {
            "success": True,
            "status": "healthy",
            "evolution_api": health_result,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Evolution health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
