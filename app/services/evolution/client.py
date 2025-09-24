"""Evolution API client for direct API communication."""
import asyncio
import logging
from typing import Dict, Any, Optional, List
import aiohttp
import json
from datetime import datetime

from app.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EvolutionAPIError(Exception):
    """Custom exception for Evolution API errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data
        super().__init__(self.message)


class EvolutionAPIClient:
    """
    Evolution API client for managing WhatsApp instances and messaging.
    
    This client handles direct communication with the Evolution API server,
    providing methods for instance management, messaging, and status monitoring.
    """
    
    def __init__(self, base_url: str = None, api_key: str = None):
        self.base_url = base_url or settings.EVOLUTION_API_URL
        self.api_key = api_key or settings.EVOLUTION_API_KEY
        self.session: Optional[aiohttp.ClientSession] = None
        
        if not self.base_url or not self.api_key:
            raise ValueError("Evolution API URL and API key must be provided")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def _ensure_session(self):
        """Ensure aiohttp session is created."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    "Content-Type": "application/json",
                    "apikey": self.api_key
                }
            )
    
    async def close(self):
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to Evolution API."""
        await self._ensure_session()
        
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        try:
            async with self.session.request(
                method=method,
                url=url,
                json=data,
                params=params
            ) as response:
                response_text = await response.text()
                
                # Log request details
                logger.info(f"Evolution API {method} {url} - Status: {response.status}")
                
                if response.status >= 400:
                    logger.error(f"Evolution API error: {response.status} - {response_text}")
                    try:
                        error_data = json.loads(response_text)
                    except json.JSONDecodeError:
                        error_data = {"error": response_text}
                    
                    raise EvolutionAPIError(
                        f"Evolution API request failed: {response.status}",
                        status_code=response.status,
                        response_data=error_data
                    )
                
                try:
                    return json.loads(response_text)
                except json.JSONDecodeError:
                    return {"raw_response": response_text}
                    
        except aiohttp.ClientError as e:
            logger.error(f"Evolution API client error: {e}")
            raise EvolutionAPIError(f"Network error: {str(e)}")
    
    # Instance Management Methods
    
    async def create_instance(
        self, 
        instance_name: str, 
        phone_number: Optional[str] = None,
        webhook_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new Evolution API instance."""
        data = {
            "instanceName": instance_name,
            "token": f"token_{instance_name}_{datetime.now().timestamp()}",
            "qrcode": True,
            "integration": "WHATSAPP-BAILEYS"
        }
        
        if phone_number:
            data["number"] = phone_number
            
        if webhook_url:
            data["webhook"] = webhook_url
        
        logger.info(f"Creating Evolution instance: {instance_name}")
        return await self._make_request("POST", "/instance/create", data)
    
    async def delete_instance(self, instance_name: str) -> Dict[str, Any]:
        """Delete an Evolution API instance."""
        logger.info(f"Deleting Evolution instance: {instance_name}")
        return await self._make_request("DELETE", f"/instance/delete/{instance_name}")
    
    async def get_instance_status(self, instance_name: str) -> Dict[str, Any]:
        """Get status of an Evolution API instance."""
        return await self._make_request("GET", f"/instance/connectionState/{instance_name}")
    
    async def restart_instance(self, instance_name: str) -> Dict[str, Any]:
        """Restart an Evolution API instance."""
        logger.info(f"Restarting Evolution instance: {instance_name}")
        return await self._make_request("PUT", f"/instance/restart/{instance_name}")
    
    async def logout_instance(self, instance_name: str) -> Dict[str, Any]:
        """Logout WhatsApp session for an instance."""
        logger.info(f"Logging out Evolution instance: {instance_name}")
        return await self._make_request("DELETE", f"/instance/logout/{instance_name}")
    
    # WhatsApp Management Methods
    
    async def get_qr_code(self, instance_name: str) -> Dict[str, Any]:
        """Get QR code for WhatsApp connection."""
        return await self._make_request("GET", f"/instance/connect/{instance_name}")
    
    async def get_whatsapp_status(self, instance_name: str) -> Dict[str, Any]:
        """Get WhatsApp connection status."""
        return await self._make_request("GET", f"/instance/connectionState/{instance_name}")
    
    async def set_profile_name(self, instance_name: str, name: str) -> Dict[str, Any]:
        """Set WhatsApp profile name."""
        data = {"name": name}
        return await self._make_request("PUT", f"/chat/updateProfileName/{instance_name}", data)
    
    async def set_profile_status(self, instance_name: str, status: str) -> Dict[str, Any]:
        """Set WhatsApp profile status."""
        data = {"status": status}
        return await self._make_request("PUT", f"/chat/updateProfileStatus/{instance_name}", data)
    
    async def set_profile_picture(self, instance_name: str, picture_url: str) -> Dict[str, Any]:
        """Set WhatsApp profile picture."""
        data = {"picture": picture_url}
        return await self._make_request("PUT", f"/chat/updateProfilePicture/{instance_name}", data)
    
    # Business Profile Methods
    
    async def create_business_profile(
        self, 
        instance_name: str, 
        business_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create WhatsApp Business profile."""
        data = {
            "description": business_data.get("description", ""),
            "category": business_data.get("category", "OTHER"),
            "email": business_data.get("email", ""),
            "website": business_data.get("website", ""),
            "address": business_data.get("address", "")
        }
        return await self._make_request("POST", f"/chat/updateBusinessProfile/{instance_name}", data)
    
    async def get_business_profile(self, instance_name: str) -> Dict[str, Any]:
        """Get WhatsApp Business profile."""
        return await self._make_request("GET", f"/chat/fetchBusinessProfile/{instance_name}")
    
    # Messaging Methods
    
    async def send_text_message(
        self, 
        instance_name: str, 
        number: str, 
        message: str,
        delay: Optional[int] = None
    ) -> Dict[str, Any]:
        """Send text message via WhatsApp."""
        # Format number for WhatsApp (add @c.us if not present)
        if "@" not in number:
            number = f"{number}@c.us"
        
        data = {
            "number": number,
            "text": message
        }
        
        if delay:
            data["delay"] = delay
        
        logger.info(f"Sending text message via {instance_name} to {number}")
        return await self._make_request("POST", f"/message/sendText/{instance_name}", data)
    
    async def send_media_message(
        self, 
        instance_name: str, 
        number: str, 
        media_url: str,
        media_type: str,
        caption: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send media message via WhatsApp."""
        if "@" not in number:
            number = f"{number}@c.us"
        
        data = {
            "number": number,
            "mediatype": media_type,
            "media": media_url
        }
        
        if caption:
            data["caption"] = caption
        
        logger.info(f"Sending {media_type} message via {instance_name} to {number}")
        return await self._make_request("POST", f"/message/sendMedia/{instance_name}", data)
    
    async def send_template_message(
        self, 
        instance_name: str, 
        number: str, 
        template_name: str,
        template_params: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Send template message via WhatsApp."""
        if "@" not in number:
            number = f"{number}@c.us"
        
        data = {
            "number": number,
            "template": {
                "name": template_name,
                "language": {"code": "en"},
                "components": []
            }
        }
        
        if template_params:
            data["template"]["components"] = [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": param} for param in template_params]
                }
            ]
        
        logger.info(f"Sending template message via {instance_name} to {number}")
        return await self._make_request("POST", f"/message/sendTemplate/{instance_name}", data)
    
    # Contact and Chat Methods
    
    async def get_contacts(self, instance_name: str) -> Dict[str, Any]:
        """Get all contacts for an instance."""
        return await self._make_request("GET", f"/chat/findContacts/{instance_name}")
    
    async def get_chats(self, instance_name: str) -> Dict[str, Any]:
        """Get all chats for an instance."""
        return await self._make_request("GET", f"/chat/findChats/{instance_name}")
    
    async def get_chat_messages(
        self, 
        instance_name: str, 
        number: str,
        limit: int = 20
    ) -> Dict[str, Any]:
        """Get messages from a specific chat."""
        if "@" not in number:
            number = f"{number}@c.us"
        
        params = {"number": number, "limit": limit}
        return await self._make_request("GET", f"/chat/findMessages/{instance_name}", params=params)
    
    # Webhook Methods
    
    async def set_webhook(self, instance_name: str, webhook_url: str) -> Dict[str, Any]:
        """Set webhook URL for an instance."""
        data = {
            "url": webhook_url,
            "enabled": True,
            "events": [
                "APPLICATION_STARTUP",
                "QRCODE_UPDATED", 
                "CONNECTION_UPDATE",
                "MESSAGES_UPSERT",
                "MESSAGES_UPDATE",
                "SEND_MESSAGE"
            ]
        }
        return await self._make_request("POST", f"/webhook/set/{instance_name}", data)
    
    async def get_webhook(self, instance_name: str) -> Dict[str, Any]:
        """Get webhook configuration for an instance."""
        return await self._make_request("GET", f"/webhook/find/{instance_name}")
    
    # Health and Monitoring Methods
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Evolution API health."""
        return await self._make_request("GET", "/")
    
    async def get_instance_list(self) -> Dict[str, Any]:
        """Get list of all instances."""
        return await self._make_request("GET", "/instance/fetchInstances")
    
    # Utility Methods
    
    def format_phone_number(self, number: str, for_whatsapp: bool = True) -> str:
        """Format phone number for WhatsApp or regular use."""
        # Remove any non-digit characters except +
        clean_number = ''.join(c for c in number if c.isdigit() or c == '+')
        
        # Add + if not present
        if not clean_number.startswith('+'):
            clean_number = '+' + clean_number
        
        # Add @c.us for WhatsApp if needed
        if for_whatsapp and "@" not in clean_number:
            # Remove + for WhatsApp format
            whatsapp_number = clean_number[1:] if clean_number.startswith('+') else clean_number
            return f"{whatsapp_number}@c.us"
        
        return clean_number
    
    async def validate_instance_name(self, instance_name: str) -> bool:
        """Validate if instance name is available."""
        try:
            await self.get_instance_status(instance_name)
            return False  # Instance exists
        except EvolutionAPIError as e:
            if e.status_code == 404:
                return True  # Instance doesn't exist, name is available
            raise  # Other error, re-raise
