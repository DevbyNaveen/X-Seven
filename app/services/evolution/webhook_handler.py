"""Evolution API webhook handler for processing incoming events."""
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import timedelta

from app.models.business import Business
from app.models.evolution_instance import (
    EvolutionInstance, 
    EvolutionMessage, 
    EvolutionWebhookEvent,
    InstanceStatus,
    WhatsAppStatus,
    MessageType
)
from app.services.ai.dashboard_ai_handler import DashboardAIHandler
from app.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EvolutionWebhookHandler:
    """
    Evolution API webhook handler for processing incoming events.
    
    This handler processes webhooks from Evolution API and triggers
    appropriate actions like AI responses, status updates, etc.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.ai_handler = DashboardAIHandler()
    
    async def process_webhook(
        self, 
        instance_name: str, 
        event_data: Dict[str, Any],
        headers: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Process incoming webhook from Evolution API.
        
        Args:
            instance_name: Name of the Evolution instance
            event_data: Webhook event data
            headers: HTTP headers from webhook request
            
        Returns:
            Processing result dictionary
        """
        try:
            # Log webhook event
            webhook_event = EvolutionWebhookEvent(
                instance_name=instance_name,
                event_type=event_data.get("event", "unknown"),
                event_data=event_data,
                raw_payload=event_data,
                headers=headers or {}
            )
            
            self.db.add(webhook_event)
            self.db.commit()
            self.db.refresh(webhook_event)
            
            # Get Evolution instance
            evolution_instance = self.db.query(EvolutionInstance).filter(
                EvolutionInstance.instance_name == instance_name
            ).first()
            
            if evolution_instance:
                webhook_event.evolution_instance_id = evolution_instance.id
                self.db.commit()
            
            # Process event based on type
            event_type = event_data.get("event", "")
            result = {"success": True, "processed": False}
            
            if event_type == "messages.upsert":
                result = await self._handle_message_event(evolution_instance, event_data)
            elif event_type == "connection.update":
                result = await self._handle_connection_event(evolution_instance, event_data)
            elif event_type == "qrcode.updated":
                result = await self._handle_qr_code_event(evolution_instance, event_data)
            elif event_type == "messages.update":
                result = await self._handle_message_status_event(evolution_instance, event_data)
            else:
                logger.info(f"Unhandled webhook event type: {event_type}")
                result = {"success": True, "processed": False, "message": f"Unhandled event type: {event_type}"}
            
            # Mark webhook as processed
            webhook_event.mark_processed(
                error=result.get("error") if not result.get("success") else None
            )
            self.db.commit()
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to process webhook for {instance_name}: {e}")
            
            # Mark webhook as failed
            if 'webhook_event' in locals():
                webhook_event.mark_processed(error=str(e))
                self.db.commit()
            
            return {"success": False, "error": str(e)}
    
    async def _handle_message_event(
        self, 
        evolution_instance: Optional[EvolutionInstance], 
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle incoming message events."""
        try:
            if not evolution_instance:
                return {"success": False, "error": "Evolution instance not found"}
            
            messages = event_data.get("data", [])
            processed_count = 0
            
            for message_data in messages:
                try:
                    # Extract message information
                    message_info = message_data.get("message", {})
                    key_info = message_data.get("key", {})
                    
                    message_id = key_info.get("id", "")
                    from_me = key_info.get("fromMe", False)
                    remote_jid = key_info.get("remoteJid", "")
                    
                    # Skip messages from the business (outbound messages we sent)
                    if from_me:
                        continue
                    
                    # Extract message content
                    message_content = ""
                    message_type = MessageType.TEXT
                    media_url = None
                    
                    if "conversation" in message_info:
                        message_content = message_info["conversation"]
                    elif "extendedTextMessage" in message_info:
                        message_content = message_info["extendedTextMessage"].get("text", "")
                    elif "imageMessage" in message_info:
                        message_type = MessageType.IMAGE
                        message_content = message_info["imageMessage"].get("caption", "[Image]")
                        media_url = message_info["imageMessage"].get("url")
                    elif "audioMessage" in message_info:
                        message_type = MessageType.AUDIO
                        message_content = "[Audio Message]"
                        media_url = message_info["audioMessage"].get("url")
                    elif "videoMessage" in message_info:
                        message_type = MessageType.VIDEO
                        message_content = message_info["videoMessage"].get("caption", "[Video]")
                        media_url = message_info["videoMessage"].get("url")
                    elif "documentMessage" in message_info:
                        message_type = MessageType.DOCUMENT
                        message_content = f"[Document: {message_info['documentMessage'].get('fileName', 'Unknown')}]"
                        media_url = message_info["documentMessage"].get("url")
                    else:
                        message_content = "[Unsupported message type]"
                    
                    # Check if message already exists
                    existing_message = self.db.query(EvolutionMessage).filter(
                        EvolutionMessage.message_id == message_id
                    ).first()
                    
                    if existing_message:
                        continue
                    
                    # Create message record
                    evolution_message = EvolutionMessage(
                        evolution_instance_id=evolution_instance.id,
                        business_id=evolution_instance.business_id,
                        message_id=message_id,
                        whatsapp_message_id=message_id,
                        message_type=message_type,
                        content=message_content,
                        media_url=media_url,
                        from_number=remote_jid,
                        to_number=evolution_instance.phone_number,
                        direction="inbound",
                        status="received",
                        sent_at=datetime.fromtimestamp(message_data.get("messageTimestamp", 0)),
                        conversation_context={"webhook_data": message_data}
                    )
                    
                    self.db.add(evolution_message)
                    
                    # Update instance usage
                    evolution_instance.update_usage("received", 1)
                    
                    processed_count += 1
                    
                    # Process with AI if it's a text message
                    if message_type == MessageType.TEXT and message_content.strip():
                        await self._process_message_with_ai(evolution_instance, evolution_message)
                    
                except Exception as e:
                    logger.error(f"Failed to process individual message: {e}")
                    continue
            
            self.db.commit()
            
            return {
                "success": True,
                "processed": True,
                "messages_processed": processed_count
            }
            
        except Exception as e:
            logger.error(f"Failed to handle message event: {e}")
            return {"success": False, "error": str(e)}
    
    async def _process_message_with_ai(
        self, 
        evolution_instance: EvolutionInstance, 
        evolution_message: EvolutionMessage
    ):
        """Process message with AI and send response."""
        try:
            start_time = datetime.utcnow()
            
            # Get business context
            business = self.db.query(Business).filter(
                Business.id == evolution_instance.business_id
            ).first()
            
            if not business:
                logger.error(f"Business not found for Evolution instance {evolution_instance.id}")
                return
            
            # Prepare context for AI
            conversation_context = {
                "business_name": business.name,
                "business_category": business.category,
                "customer_number": evolution_message.from_number,
                "message_history": await self._get_recent_messages(evolution_instance.id, evolution_message.from_number)
            }
            
            # Generate AI response
            ai_response = await self.ai_handler.generate_response(
                message=evolution_message.content,
                business_id=evolution_instance.business_id,
                context=conversation_context
            )
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            if ai_response and ai_response.get("response"):
                # Send response via Evolution API
                from app.services.evolution.client import EvolutionAPIClient
                
                async with EvolutionAPIClient() as client:
                    send_result = await client.send_text_message(
                        evolution_instance.instance_name,
                        evolution_message.from_number,
                        ai_response["response"]
                    )
                
                # Create outbound message record
                response_message = EvolutionMessage(
                    evolution_instance_id=evolution_instance.id,
                    business_id=evolution_instance.business_id,
                    message_id=send_result.get("key", {}).get("id", f"ai_response_{datetime.now().timestamp()}"),
                    message_type=MessageType.TEXT,
                    content=ai_response["response"],
                    from_number=evolution_instance.phone_number,
                    to_number=evolution_message.from_number,
                    direction="outbound",
                    status="sent",
                    sent_at=datetime.utcnow(),
                    ai_processed=True,
                    ai_response_generated=True,
                    conversation_context={"ai_context": ai_response.get("context", {})}
                )
                
                self.db.add(response_message)
                
                # Update original message
                evolution_message.mark_ai_processed(
                    response_content=ai_response["response"],
                    processing_time=processing_time
                )
                
                # Update instance usage
                evolution_instance.update_usage("sent", 1)
                
                logger.info(f"AI response sent for message {evolution_message.message_id}")
            
            else:
                # Mark as processed but no response generated
                evolution_message.mark_ai_processed(processing_time=processing_time)
                logger.info(f"AI processed message {evolution_message.message_id} but no response generated")
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to process message with AI: {e}")
            evolution_message.mark_ai_processed(processing_time=0)
            self.db.commit()
    
    async def _get_recent_messages(
        self, 
        evolution_instance_id: int, 
        customer_number: str, 
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get recent messages for context."""
        messages = self.db.query(EvolutionMessage).filter(
            and_(
                EvolutionMessage.evolution_instance_id == evolution_instance_id,
                or_(
                    EvolutionMessage.from_number == customer_number,
                    EvolutionMessage.to_number == customer_number
                )
            )
        ).order_by(EvolutionMessage.created_at.desc()).limit(limit).all()
        
        return [
            {
                "content": msg.content,
                "direction": msg.direction,
                "timestamp": msg.created_at.isoformat(),
                "ai_processed": msg.ai_processed
            }
            for msg in reversed(messages)  # Reverse to get chronological order
        ]
    
    async def _handle_connection_event(
        self, 
        evolution_instance: Optional[EvolutionInstance], 
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle connection status events."""
        try:
            if not evolution_instance:
                return {"success": False, "error": "Evolution instance not found"}
            
            connection_data = event_data.get("data", {})
            state = connection_data.get("state", "")
            
            # Update instance status based on connection state
            if state == "open":
                evolution_instance.status = InstanceStatus.CONNECTED
                evolution_instance.whatsapp_status = WhatsAppStatus.CONNECTED
            elif state == "connecting":
                evolution_instance.status = InstanceStatus.CONNECTING
                evolution_instance.whatsapp_status = WhatsAppStatus.CONNECTING
            elif state == "close":
                evolution_instance.status = InstanceStatus.DISCONNECTED
                evolution_instance.whatsapp_status = WhatsAppStatus.DISCONNECTED
            
            evolution_instance.last_seen = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"Connection state updated for {evolution_instance.instance_name}: {state}")
            
            return {
                "success": True,
                "processed": True,
                "new_state": state
            }
            
        except Exception as e:
            logger.error(f"Failed to handle connection event: {e}")
            return {"success": False, "error": str(e)}
    
    async def _handle_qr_code_event(
        self, 
        evolution_instance: Optional[EvolutionInstance], 
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle QR code update events."""
        try:
            if not evolution_instance:
                return {"success": False, "error": "Evolution instance not found"}
            
            qr_data = event_data.get("data", {})
            qr_code = qr_data.get("qrcode", "")
            
            # Update QR code in database
            evolution_instance.whatsapp_qr_code = qr_code
            evolution_instance.whatsapp_status = WhatsAppStatus.QR_CODE
            evolution_instance.last_seen = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"QR code updated for {evolution_instance.instance_name}")
            
            return {
                "success": True,
                "processed": True,
                "qr_code_updated": True
            }
            
        except Exception as e:
            logger.error(f"Failed to handle QR code event: {e}")
            return {"success": False, "error": str(e)}
    
    async def _handle_message_status_event(
        self, 
        evolution_instance: Optional[EvolutionInstance], 
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle message status update events."""
        try:
            if not evolution_instance:
                return {"success": False, "error": "Evolution instance not found"}
            
            status_data = event_data.get("data", [])
            updated_count = 0
            
            for status_info in status_data:
                try:
                    key_info = status_info.get("key", {})
                    message_id = key_info.get("id", "")
                    status = status_info.get("status", "")
                    
                    # Find message in database
                    evolution_message = self.db.query(EvolutionMessage).filter(
                        and_(
                            EvolutionMessage.message_id == message_id,
                            EvolutionMessage.evolution_instance_id == evolution_instance.id
                        )
                    ).first()
                    
                    if evolution_message:
                        # Update message status
                        evolution_message.status = status
                        
                        if status == "delivered":
                            evolution_message.delivered_at = datetime.utcnow()
                        elif status == "read":
                            evolution_message.read_at = datetime.utcnow()
                        
                        updated_count += 1
                
                except Exception as e:
                    logger.error(f"Failed to process message status update: {e}")
                    continue
            
            self.db.commit()
            
            return {
                "success": True,
                "processed": True,
                "messages_updated": updated_count
            }
            
        except Exception as e:
            logger.error(f"Failed to handle message status event: {e}")
            return {"success": False, "error": str(e)}
    
    async def cleanup_old_webhook_events(self, days: int = 30):
        """Clean up old webhook events to prevent database bloat."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            deleted_count = self.db.query(EvolutionWebhookEvent).filter(
                EvolutionWebhookEvent.created_at < cutoff_date
            ).delete()
            
            self.db.commit()
            
            logger.info(f"Cleaned up {deleted_count} old webhook events")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old webhook events: {e}")
    
    async def get_webhook_statistics(self, days: int = 7) -> Dict[str, Any]:
        """Get webhook processing statistics."""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            events = self.db.query(EvolutionWebhookEvent).filter(
                EvolutionWebhookEvent.created_at >= start_date
            ).all()
            
            total_events = len(events)
            processed_events = len([e for e in events if e.processed])
            failed_events = len([e for e in events if e.processing_error])
            
            event_types = {}
            for event in events:
                event_type = event.event_type
                if event_type not in event_types:
                    event_types[event_type] = 0
                event_types[event_type] += 1
            
            return {
                "period_days": days,
                "total_events": total_events,
                "processed_events": processed_events,
                "failed_events": failed_events,
                "success_rate": processed_events / total_events if total_events > 0 else 0,
                "event_types": event_types
            }
            
        except Exception as e:
            logger.error(f"Failed to get webhook statistics: {e}")
            return {"error": str(e)}
