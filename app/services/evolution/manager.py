"""Evolution API manager for business integration and orchestration."""
import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.business import Business
from app.models.evolution_instance import EvolutionInstance, EvolutionMessage, InstanceStatus, WhatsAppStatus
from app.services.evolution.client import EvolutionAPIClient, EvolutionAPIError
from app.services.phone.providers.multi_provider_manager import MultiProviderPhoneManager
from app.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EvolutionManagerError(Exception):
    """Custom exception for Evolution Manager errors."""
    pass


class EvolutionManager:
    """
    Evolution API manager for business integration and orchestration.
    
    This manager handles the complete lifecycle of Evolution API instances
    for businesses, including phone provisioning, WhatsApp setup, and AI integration.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.evolution_client = EvolutionAPIClient()
        self.phone_manager = MultiProviderPhoneManager(db)
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.evolution_client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.evolution_client.__aexit__(exc_type, exc_val, exc_tb)
    
    # Business Onboarding Methods
    
    async def onboard_business_evolution(
        self, 
        business_id: int, 
        country_code: str = "US",
        enable_whatsapp: bool = True,
        business_profile: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Complete business onboarding to Evolution API.
        
        This method handles:
        1. Phone number provisioning
        2. Evolution instance creation
        3. WhatsApp Business setup
        4. AI integration configuration
        """
        try:
            # Get business
            business = self.db.query(Business).filter(Business.id == business_id).first()
            if not business:
                raise EvolutionManagerError(f"Business {business_id} not found")
            
            # Check if business already has Evolution instance
            existing_instance = self.db.query(EvolutionInstance).filter(
                and_(
                    EvolutionInstance.business_id == business_id,
                    EvolutionInstance.status != InstanceStatus.DELETED
                )
            ).first()
            
            if existing_instance:
                logger.warning(f"Business {business_id} already has Evolution instance: {existing_instance.instance_name}")
                return await self.get_business_evolution_status(business_id)
            
            # Step 1: Provision phone number
            logger.info(f"Provisioning phone number for business {business_id}")
            phone_result = await self.phone_manager.provision_number(
                business_id=business_id,
                country_code=country_code
            )
            
            if not phone_result.get("success"):
                raise EvolutionManagerError(f"Failed to provision phone number: {phone_result.get('error')}")
            
            phone_number = phone_result["phone_number"]
            phone_sid = phone_result.get("phone_sid")
            
            # Step 2: Create Evolution instance
            instance_name = f"business_{business_id}"
            webhook_url = f"{settings.BASE_URL}/api/v1/evolution/webhook/{instance_name}"
            
            logger.info(f"Creating Evolution instance: {instance_name}")
            instance_result = await self.evolution_client.create_instance(
                instance_name=instance_name,
                phone_number=phone_number,
                webhook_url=webhook_url
            )
            
            # Step 3: Create database record
            evolution_instance = EvolutionInstance(
                business_id=business_id,
                instance_name=instance_name,
                instance_token=instance_result.get("token"),
                phone_number=phone_number,
                phone_country_code=country_code,
                phone_provider=phone_result.get("provider"),
                phone_sid=phone_sid,
                status=InstanceStatus.CREATING,
                whatsapp_enabled=enable_whatsapp,
                webhook_url=webhook_url,
                evolution_config=instance_result,
                monthly_cost=self._calculate_monthly_cost(business.subscription_plan, enable_whatsapp),
                usage_limits=self._get_usage_limits(business.subscription_plan),
                current_usage={}
            )
            
            self.db.add(evolution_instance)
            self.db.commit()
            self.db.refresh(evolution_instance)
            
            # Step 4: Update business record
            business.evolution_instance_id = evolution_instance.id
            business.evolution_enabled = True
            business.custom_phone_number = phone_number
            business.phone_config_status = "configured"
            self.db.commit()
            
            # Step 5: Setup webhook
            try:
                await self.evolution_client.set_webhook(instance_name, webhook_url)
                logger.info(f"Webhook configured for instance {instance_name}")
            except Exception as e:
                logger.warning(f"Failed to set webhook for {instance_name}: {e}")
            
            # Step 6: Setup WhatsApp Business (if enabled)
            if enable_whatsapp:
                try:
                    await self._setup_whatsapp_business(evolution_instance, business_profile)
                except Exception as e:
                    logger.warning(f"Failed to setup WhatsApp Business for {instance_name}: {e}")
            
            # Step 7: Wait for instance to be ready
            await self._wait_for_instance_ready(instance_name, timeout=60)
            
            logger.info(f"Successfully onboarded business {business_id} to Evolution API")
            
            return {
                "success": True,
                "business_id": business_id,
                "instance_name": instance_name,
                "phone_number": phone_number,
                "whatsapp_enabled": enable_whatsapp,
                "monthly_cost": evolution_instance.monthly_cost,
                "status": evolution_instance.status,
                "qr_code_url": f"/api/v1/evolution/qr/{instance_name}" if enable_whatsapp else None
            }
            
        except Exception as e:
            logger.error(f"Failed to onboard business {business_id} to Evolution API: {e}")
            # Cleanup on failure
            try:
                await self._cleanup_failed_onboarding(business_id, instance_name if 'instance_name' in locals() else None)
            except Exception as cleanup_error:
                logger.error(f"Failed to cleanup after onboarding failure: {cleanup_error}")
            
            raise EvolutionManagerError(f"Business onboarding failed: {str(e)}")
    
    async def _setup_whatsapp_business(
        self, 
        evolution_instance: EvolutionInstance, 
        business_profile: Optional[Dict[str, Any]] = None
    ):
        """Setup WhatsApp Business profile for an instance."""
        instance_name = evolution_instance.instance_name
        
        # Get business details
        business = self.db.query(Business).filter(Business.id == evolution_instance.business_id).first()
        
        # Prepare business profile data
        profile_data = {
            "description": business_profile.get("description", business.description or f"{business.name} - AI-powered customer service"),
            "category": business_profile.get("category", self._map_business_category(business.category)),
            "email": business_profile.get("email", business.email),
            "website": business_profile.get("website", ""),
            "address": business_profile.get("address", "")
        }
        
        # Create business profile
        try:
            profile_result = await self.evolution_client.create_business_profile(
                instance_name, profile_data
            )
            
            evolution_instance.whatsapp_business_profile = profile_result
            evolution_instance.whatsapp_status = WhatsAppStatus.CONNECTING
            self.db.commit()
            
            logger.info(f"WhatsApp Business profile created for {instance_name}")
            
        except Exception as e:
            logger.error(f"Failed to create WhatsApp Business profile for {instance_name}: {e}")
            raise
    
    async def _wait_for_instance_ready(self, instance_name: str, timeout: int = 60):
        """Wait for Evolution instance to be ready."""
        start_time = datetime.utcnow()
        
        while (datetime.utcnow() - start_time).seconds < timeout:
            try:
                status_result = await self.evolution_client.get_instance_status(instance_name)
                
                if status_result.get("instance", {}).get("state") == "open":
                    # Update database status
                    evolution_instance = self.db.query(EvolutionInstance).filter(
                        EvolutionInstance.instance_name == instance_name
                    ).first()
                    
                    if evolution_instance:
                        evolution_instance.status = InstanceStatus.ACTIVE
                        evolution_instance.last_seen = datetime.utcnow()
                        self.db.commit()
                    
                    logger.info(f"Instance {instance_name} is ready")
                    return
                
            except Exception as e:
                logger.debug(f"Waiting for instance {instance_name} to be ready: {e}")
            
            await asyncio.sleep(2)
        
        logger.warning(f"Instance {instance_name} not ready after {timeout} seconds")
    
    async def _cleanup_failed_onboarding(self, business_id: int, instance_name: Optional[str] = None):
        """Cleanup resources after failed onboarding."""
        try:
            # Delete Evolution instance if created
            if instance_name:
                try:
                    await self.evolution_client.delete_instance(instance_name)
                except Exception as e:
                    logger.warning(f"Failed to delete Evolution instance {instance_name}: {e}")
            
            # Remove database records
            evolution_instance = self.db.query(EvolutionInstance).filter(
                EvolutionInstance.business_id == business_id
            ).first()
            
            if evolution_instance:
                evolution_instance.status = InstanceStatus.ERROR
                evolution_instance.last_error = "Onboarding failed"
                self.db.commit()
            
            # Reset business configuration
            business = self.db.query(Business).filter(Business.id == business_id).first()
            if business:
                business.evolution_enabled = False
                business.phone_config_status = "failed"
                self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to cleanup after onboarding failure: {e}")
    
    # Instance Management Methods
    
    async def get_business_evolution_status(self, business_id: int) -> Dict[str, Any]:
        """Get Evolution API status for a business."""
        evolution_instance = self.db.query(EvolutionInstance).filter(
            and_(
                EvolutionInstance.business_id == business_id,
                EvolutionInstance.status != InstanceStatus.DELETED
            )
        ).first()
        
        if not evolution_instance:
            return {
                "configured": False,
                "status": "not_configured",
                "message": "Evolution API not configured for this business"
            }
        
        # Get live status from Evolution API
        try:
            live_status = await self.evolution_client.get_instance_status(evolution_instance.instance_name)
            
            # Update database with live status
            connection_state = live_status.get("instance", {}).get("state", "unknown")
            if connection_state == "open":
                evolution_instance.status = InstanceStatus.CONNECTED
                evolution_instance.whatsapp_status = WhatsAppStatus.CONNECTED
            elif connection_state == "connecting":
                evolution_instance.status = InstanceStatus.CONNECTING
                evolution_instance.whatsapp_status = WhatsAppStatus.CONNECTING
            else:
                evolution_instance.status = InstanceStatus.DISCONNECTED
                evolution_instance.whatsapp_status = WhatsAppStatus.DISCONNECTED
            
            evolution_instance.last_seen = datetime.utcnow()
            self.db.commit()
            
        except Exception as e:
            logger.warning(f"Failed to get live status for instance {evolution_instance.instance_name}: {e}")
            live_status = {}
        
        return {
            "configured": True,
            "instance_name": evolution_instance.instance_name,
            "phone_number": evolution_instance.phone_number,
            "status": evolution_instance.status,
            "whatsapp_enabled": evolution_instance.whatsapp_enabled,
            "whatsapp_status": evolution_instance.whatsapp_status,
            "monthly_cost": evolution_instance.monthly_cost,
            "usage_stats": {
                "messages_sent": evolution_instance.messages_sent,
                "messages_received": evolution_instance.messages_received,
                "calls_handled": evolution_instance.calls_handled
            },
            "last_activity": evolution_instance.last_activity,
            "last_seen": evolution_instance.last_seen,
            "live_status": live_status,
            "connection_info": evolution_instance.get_connection_info()
        }
    
    async def restart_business_instance(self, business_id: int) -> Dict[str, Any]:
        """Restart Evolution instance for a business."""
        evolution_instance = self.db.query(EvolutionInstance).filter(
            EvolutionInstance.business_id == business_id
        ).first()
        
        if not evolution_instance:
            raise EvolutionManagerError(f"No Evolution instance found for business {business_id}")
        
        try:
            result = await self.evolution_client.restart_instance(evolution_instance.instance_name)
            
            evolution_instance.status = InstanceStatus.CONNECTING
            evolution_instance.last_seen = datetime.utcnow()
            self.db.commit()
            
            return {
                "success": True,
                "instance_name": evolution_instance.instance_name,
                "status": "restarting",
                "result": result
            }
            
        except Exception as e:
            logger.error(f"Failed to restart instance for business {business_id}: {e}")
            raise EvolutionManagerError(f"Failed to restart instance: {str(e)}")
    
    async def get_whatsapp_qr_code(self, business_id: int) -> Dict[str, Any]:
        """Get WhatsApp QR code for business instance."""
        evolution_instance = self.db.query(EvolutionInstance).filter(
            EvolutionInstance.business_id == business_id
        ).first()
        
        if not evolution_instance:
            raise EvolutionManagerError(f"No Evolution instance found for business {business_id}")
        
        if not evolution_instance.whatsapp_enabled:
            raise EvolutionManagerError("WhatsApp is not enabled for this business")
        
        try:
            qr_result = await self.evolution_client.get_qr_code(evolution_instance.instance_name)
            
            # Update QR code in database
            evolution_instance.whatsapp_qr_code = qr_result.get("qrcode", {}).get("code")
            evolution_instance.whatsapp_status = WhatsAppStatus.QR_CODE
            self.db.commit()
            
            return {
                "success": True,
                "qr_code": evolution_instance.whatsapp_qr_code,
                "qr_image": qr_result.get("qrcode", {}).get("base64"),
                "instance_name": evolution_instance.instance_name
            }
            
        except Exception as e:
            logger.error(f"Failed to get QR code for business {business_id}: {e}")
            raise EvolutionManagerError(f"Failed to get QR code: {str(e)}")
    
    # Messaging Methods
    
    async def send_message_to_customer(
        self, 
        business_id: int, 
        customer_number: str, 
        message: str,
        message_type: str = "text"
    ) -> Dict[str, Any]:
        """Send message to customer via business Evolution instance."""
        evolution_instance = self.db.query(EvolutionInstance).filter(
            EvolutionInstance.business_id == business_id
        ).first()
        
        if not evolution_instance:
            raise EvolutionManagerError(f"No Evolution instance found for business {business_id}")
        
        if not evolution_instance.is_whatsapp_connected():
            raise EvolutionManagerError("WhatsApp is not connected for this business")
        
        try:
            # Send message via Evolution API
            result = await self.evolution_client.send_text_message(
                evolution_instance.instance_name,
                customer_number,
                message
            )
            
            # Log message in database
            evolution_message = EvolutionMessage(
                evolution_instance_id=evolution_instance.id,
                business_id=business_id,
                message_id=result.get("key", {}).get("id", f"msg_{datetime.now().timestamp()}"),
                message_type=message_type,
                content=message,
                from_number=evolution_instance.phone_number,
                to_number=customer_number,
                direction="outbound",
                status="sent",
                sent_at=datetime.utcnow()
            )
            
            self.db.add(evolution_message)
            
            # Update usage statistics
            evolution_instance.update_usage("sent", 1)
            self.db.commit()
            
            logger.info(f"Message sent from business {business_id} to {customer_number}")
            
            return {
                "success": True,
                "message_id": evolution_message.message_id,
                "status": "sent",
                "result": result
            }
            
        except Exception as e:
            logger.error(f"Failed to send message from business {business_id}: {e}")
            raise EvolutionManagerError(f"Failed to send message: {str(e)}")
    
    # Utility Methods
    
    def _calculate_monthly_cost(self, subscription_plan: str, whatsapp_enabled: bool) -> float:
        """Calculate monthly cost for Evolution instance."""
        base_costs = {
            "basic": 0.0,  # No Evolution API for basic
            "pro": 25.0,   # Phone + WhatsApp
            "enterprise": 50.0  # Phone + WhatsApp + Premium features
        }
        
        base_cost = base_costs.get(subscription_plan, 25.0)
        
        # Additional cost for WhatsApp Business
        if whatsapp_enabled and subscription_plan != "basic":
            base_cost += 10.0
        
        return base_cost
    
    def _get_usage_limits(self, subscription_plan: str) -> Dict[str, int]:
        """Get usage limits based on subscription plan."""
        limits = {
            "basic": {
                "messages_per_month": 1000,
                "calls_per_month": 100,
                "contacts": 500
            },
            "pro": {
                "messages_per_month": 5000,
                "calls_per_month": 500,
                "contacts": 2000
            },
            "enterprise": {
                "messages_per_month": -1,  # Unlimited
                "calls_per_month": -1,     # Unlimited
                "contacts": -1             # Unlimited
            }
        }
        
        return limits.get(subscription_plan, limits["pro"])
    
    def _map_business_category(self, category: Optional[str]) -> str:
        """Map business category to WhatsApp Business category."""
        category_mapping = {
            "food_hospitality": "FOOD_BEVERAGE",
            "beauty_personal_care": "BEAUTY_PERSONAL_CARE",
            "automotive_services": "AUTOMOTIVE",
            "health_medical": "HEALTH",
            "local_services": "OTHER"
        }
        
        return category_mapping.get(category, "OTHER")
    
    async def get_business_messages(
        self, 
        business_id: int, 
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get messages for a business."""
        messages = self.db.query(EvolutionMessage).filter(
            EvolutionMessage.business_id == business_id
        ).order_by(EvolutionMessage.created_at.desc()).offset(offset).limit(limit).all()
        
        return [
            {
                "id": msg.id,
                "message_id": msg.message_id,
                "content": msg.content,
                "direction": msg.direction,
                "from_number": msg.from_number,
                "to_number": msg.to_number,
                "status": msg.status,
                "created_at": msg.created_at,
                "ai_processed": msg.ai_processed,
                "ai_response_content": msg.ai_response_content
            }
            for msg in messages
        ]
    
    async def get_business_analytics(self, business_id: int, days: int = 30) -> Dict[str, Any]:
        """Get analytics for a business Evolution instance."""
        evolution_instance = self.db.query(EvolutionInstance).filter(
            EvolutionInstance.business_id == business_id
        ).first()
        
        if not evolution_instance:
            return {"error": "No Evolution instance found"}
        
        # Get message statistics
        start_date = datetime.utcnow() - timedelta(days=days)
        
        messages = self.db.query(EvolutionMessage).filter(
            and_(
                EvolutionMessage.business_id == business_id,
                EvolutionMessage.created_at >= start_date
            )
        ).all()
        
        inbound_messages = [msg for msg in messages if msg.direction == "inbound"]
        outbound_messages = [msg for msg in messages if msg.direction == "outbound"]
        ai_processed_messages = [msg for msg in messages if msg.ai_processed]
        
        return {
            "instance_info": evolution_instance.get_connection_info(),
            "period_days": days,
            "total_messages": len(messages),
            "inbound_messages": len(inbound_messages),
            "outbound_messages": len(outbound_messages),
            "ai_processed_messages": len(ai_processed_messages),
            "ai_processing_rate": len(ai_processed_messages) / len(inbound_messages) if inbound_messages else 0,
            "average_response_time": sum(msg.ai_processing_time or 0 for msg in ai_processed_messages) / len(ai_processed_messages) if ai_processed_messages else 0,
            "monthly_cost": evolution_instance.monthly_cost,
            "usage_within_limits": evolution_instance.is_within_limits()
        }
