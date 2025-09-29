"""
Redis Persistence Manager for LangGraph Conversations
Handles state persistence and synchronization across components
"""

from __future__ import annotations

import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
import logging

import redis.asyncio as redis
from app.config.settings import settings

logger = logging.getLogger(__name__)


class RedisPersistenceManager:
    """Redis-based persistence for conversation state and cross-component synchronization"""
    
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or settings.REDIS_URL or "redis://localhost:6379"
        self.redis_client: Optional[redis.Redis] = None
        self.connection_pool = None
        self._disabled = False
        
    async def _ensure_connection(self):
        """Ensure Redis connection is established"""
        if self.redis_client is None:
            try:
                self.connection_pool = redis.ConnectionPool.from_url(
                    self.redis_url,
                    decode_responses=True,
                    max_connections=20,
                    retry_on_timeout=True,
                    socket_connect_timeout=5.0,  # Short timeout for initial connection
                    health_check_interval=30.0   # Check connection health periodically
                )
                self.redis_client = redis.Redis(connection_pool=self.connection_pool)
                
                # Test connection
                await self.redis_client.ping()
                logger.info("✅ Redis connection established")
                
            except Exception as e:
                logger.error(f"❌ Redis connection failed: {e}")
                self.redis_client = None
                raise RuntimeError(f"Failed to connect to Redis: {e}")
            
        # Verify connection is still active
        try:
            await self.redis_client.ping()
        except Exception as e:
            logger.error(f"❌ Redis connection lost: {e}")
            self.redis_client = None
            raise RuntimeError(f"Lost connection to Redis: {e}")
    
    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
            if self.connection_pool:
                await self.connection_pool.disconnect()
            logger.info("Redis connection closed")
    
    # Conversation State Management
    
    async def save_conversation_state(self, conversation_id: str, state: Dict[str, Any], 
                                    ttl: int = 3600) -> bool:
        """Save conversation state to Redis"""
        await self._ensure_connection()
        
        try:
            key = f"conversation:{conversation_id}"
            state_json = json.dumps(state, default=str)
            
            await self.redis_client.setex(key, ttl, state_json)
            
            # Also save to conversation list
            await self.redis_client.sadd("conversations:active", conversation_id)
            
            logger.debug(f"Saved conversation state for {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save conversation state {conversation_id}: {e}")
            return False
    
    async def load_conversation_state(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Load conversation state from Redis"""
        await self._ensure_connection()
        
        try:
            key = f"conversation:{conversation_id}"
            state_json = await self.redis_client.get(key)
            
            if state_json:
                return json.loads(state_json)
            return None
            
        except Exception as e:
            logger.error(f"Failed to load conversation state {conversation_id}: {e}")
            return None
    
    async def delete_conversation_state(self, conversation_id: str) -> bool:
        """Delete conversation state from Redis"""
        await self._ensure_connection()
        
        try:
            key = f"conversation:{conversation_id}"
            await self.redis_client.delete(key)
            await self.redis_client.srem("conversations:active", conversation_id)
            
            logger.debug(f"Deleted conversation state for {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete conversation state {conversation_id}: {e}")
            return False
    
    async def get_conversation_list(self) -> List[str]:
        """Get list of active conversations"""
        await self._ensure_connection()
        
        try:
            conversations = await self.redis_client.smembers("conversations:active")
            return list(conversations) if conversations else []
            
        except Exception as e:
            logger.error(f"Failed to get conversation list: {e}")
            return []
    
    # Workflow State Management
    
    async def save_workflow_state(self, workflow_id: str, state: Dict[str, Any], 
                                ttl: int = 86400) -> bool:
        """Save Temporal workflow state"""
        await self._ensure_connection()
        
        try:
            key = f"workflow:{workflow_id}"
            state_json = json.dumps(state, default=str)
            
            await self.redis_client.setex(key, ttl, state_json)
            await self.redis_client.sadd("workflows:active", workflow_id)
            
            logger.debug(f"Saved workflow state for {workflow_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save workflow state {workflow_id}: {e}")
            return False
    
    async def load_workflow_state(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Load Temporal workflow state"""
        await self._ensure_connection()
        
        try:
            key = f"workflow:{workflow_id}"
            state_json = await self.redis_client.get(key)
            
            if state_json:
                return json.loads(state_json)
            return None
            
        except Exception as e:
            logger.error(f"Failed to load workflow state {workflow_id}: {e}")
            return None
    
    # Agent State Management
    
    async def save_agent_context(self, agent_id: str, context: Dict[str, Any], 
                                ttl: int = 1800) -> bool:
        """Save CrewAI agent context"""
        await self._ensure_connection()
        
        try:
            key = f"agent:{agent_id}"
            context_json = json.dumps(context, default=str)
            
            await self.redis_client.setex(key, ttl, context_json)
            
            logger.debug(f"Saved agent context for {agent_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save agent context {agent_id}: {e}")
            return False
    
    async def load_agent_context(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Load CrewAI agent context"""
        await self._ensure_connection()
        
        try:
            key = f"agent:{agent_id}"
            context_json = await self.redis_client.get(key)
            
            if context_json:
                return json.loads(context_json)
            return None
            
        except Exception as e:
            logger.error(f"Failed to load agent context {agent_id}: {e}")
            return None
    
    # Business State Management
    
    async def save_business_state(self, business_id: str, state: Dict[str, Any], 
                                ttl: int = 7200) -> bool:
        """Save business-specific state"""
        await self._ensure_connection()
        
        try:
            key = f"business:{business_id}"
            state_json = json.dumps(state, default=str)
            
            await self.redis_client.setex(key, ttl, state_json)
            
            logger.debug(f"Saved business state for {business_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save business state {business_id}: {e}")
            return False
    
    async def load_business_state(self, business_id: str) -> Optional[Dict[str, Any]]:
        """Load business-specific state"""
        await self._ensure_connection()
        
        try:
            key = f"business:{business_id}"
            state_json = await self.redis_client.get(key)
            
            if state_json:
                return json.loads(state_json)
            return None
            
        except Exception as e:
            logger.error(f"Failed to load business state {business_id}: {e}")
            return None
    
    # User Context Management
    
    async def save_user_context(self, user_id: str, context: Dict[str, Any], 
                              ttl: int = 86400) -> bool:
        """Save user preferences and context"""
        await self._ensure_connection()
        
        try:
            key = f"user:{user_id}"
            context_json = json.dumps(context, default=str)
            
            await self.redis_client.setex(key, ttl, context_json)
            
            logger.debug(f"Saved user context for {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save user context {user_id}: {e}")
            return False
    
    async def load_user_context(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Load user preferences and context"""
        await self._ensure_connection()
        
        try:
            key = f"user:{user_id}"
            context_json = await self.redis_client.get(key)
            
            if context_json:
                return json.loads(context_json)
            return None
            
        except Exception as e:
            logger.error(f"Failed to load user context {user_id}: {e}")
            return None
    
    # Cross-Component Synchronization
    
    async def publish_state_update(self, channel: str, data: Dict[str, Any]) -> bool:
        """Publish state update to Redis pub/sub"""
        await self._ensure_connection()
        
        try:
            message = json.dumps(data, default=str)
            await self.redis_client.publish(channel, message)
            
            logger.debug(f"Published update to channel {channel}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish to channel {channel}: {e}")
            return False
    
    async def subscribe_to_updates(self, channels: List[str]) -> redis.client.PubSub:
        """Subscribe to state update channels"""
        await self._ensure_connection()
        
        try:
            pubsub = self.redis_client.pubsub()
            await pubsub.subscribe(*channels)
            
            logger.info(f"Subscribed to channels: {channels}")
            return pubsub
            
        except Exception as e:
            logger.error(f"Failed to subscribe to channels {channels}: {e}")
            raise
    
    # Cache Management
    
    async def cache_set(self, key: str, value: Any, ttl: int = 900) -> bool:
        """Set cache value with TTL"""
        await self._ensure_connection()
        
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value, default=str)
            
            await self.redis_client.setex(f"cache:{key}", ttl, value)
            return True
            
        except Exception as e:
            logger.error(f"Failed to set cache {key}: {e}")
            return False
    
    async def cache_get(self, key: str) -> Optional[Any]:
        """Get cache value"""
        await self._ensure_connection()
        
        try:
            value = await self.redis_client.get(f"cache:{key}")
            
            if value:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return None
            
        except Exception as e:
            logger.error(f"Failed to get cache {key}: {e}")
            return None
    
    async def cache_delete(self, key: str) -> bool:
        """Delete cache value"""
        await self._ensure_connection()
        
        try:
            await self.redis_client.delete(f"cache:{key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete cache {key}: {e}")
            return False
    
    # Statistics and Monitoring
    
    async def get_conversation_stats(self) -> Dict[str, Any]:
        """Get conversation statistics"""
        await self._ensure_connection()
        
        try:
            active_conversations = await self.redis_client.scard("conversations:active")
            active_workflows = await self.redis_client.scard("workflows:active")
            
            # Get memory usage
            memory_info = await self.redis_client.info("memory")
            
            return {
                "active_conversations": active_conversations,
                "active_workflows": active_workflows,
                "memory_usage_bytes": memory_info.get("used_memory", 0),
                "memory_usage_human": memory_info.get("used_memory_human", "0B"),
                "connected_clients": memory_info.get("connected_clients", 0),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get conversation stats: {e}")
            return {}
    
    async def cleanup_expired_keys(self) -> int:
        """Clean up expired conversation keys"""
        try:
            await self._ensure_connection()
                
            # Clean up expired keys
            current_time = datetime.now()
            expired_keys = []
            
            # Get all conversation keys
            keys = await self.redis_client.keys("conversation:*")
            for key in keys:
                try:
                    data = await self.redis_client.get(key)
                    if data:
                        conversation_data = json.loads(data)
                        updated_at = datetime.fromisoformat(conversation_data.get('updated_at', current_time.isoformat()))
                        
                        # Check if expired (older than 7 days)
                        if current_time - updated_at > timedelta(days=7):
                            expired_keys.append(key)
                            
                except Exception as e:
                    logger.warning(f"Error processing key {key}: {e}")
            
            # Delete expired keys
            if expired_keys:
                await self.redis_client.delete(*expired_keys)
                logger.info(f"Cleaned up {len(expired_keys)} expired conversation keys")
                return len(expired_keys)
                
        except Exception as e:
            logger.warning(f"Failed to cleanup expired keys: {e}")
            return 0
    # Health Check
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform Redis health check"""
        try:
            await self._ensure_connection()
            # Redis client must be available at this point
            
            # Test basic operations
            test_key = "health_check_test"
            await self.redis_client.set(test_key, "ok", ex=10)
            value = await self.redis_client.get(test_key)
            await self.redis_client.delete(test_key)
            
            # Get Redis info
            info = await self.redis_client.info()
            
            return {
                "status": "healthy",
                "connected": True,
                "redis_version": info.get("redis_version", "unknown"),
                "used_memory": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
