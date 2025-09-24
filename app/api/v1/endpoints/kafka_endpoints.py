"""
Kafka Management and Monitoring API Endpoints
Provides REST API for Kafka operations, monitoring, and management
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from pydantic import BaseModel, Field

from app.core.kafka.manager import get_kafka_manager
from app.core.kafka.integration import get_kafka_service_integrator, publish_conversation_started, publish_ai_response_generated, publish_business_analytics_update
from app.core.kafka.events import Event, EventType, create_conversation_event

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic models for API
class EventPublishRequest(BaseModel):
    """Request model for publishing events"""
    event_type: str = Field(..., description="Type of event to publish")
    data: Dict[str, Any] = Field(..., description="Event data")
    user_id: Optional[str] = Field(None, description="User ID")
    correlation_id: Optional[str] = Field(None, description="Correlation ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Event metadata")


class ConversationEventRequest(BaseModel):
    """Request model for conversation events"""
    conversation_id: str = Field(..., description="Conversation ID")
    user_id: str = Field(..., description="User ID")
    action: str = Field(..., description="Action: started, message, ended")
    message_content: Optional[str] = Field(None, description="Message content for message events")
    message_type: Optional[str] = Field("user", description="Message type: user, assistant, system")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class AIResponseEventRequest(BaseModel):
    """Request model for AI response events"""
    model_name: str = Field(..., description="AI model name")
    user_id: str = Field(..., description="User ID")
    conversation_id: Optional[str] = Field(None, description="Conversation ID")
    prompt: str = Field(..., description="Input prompt")
    response: str = Field(..., description="AI response")
    tokens_used: Optional[int] = Field(None, description="Tokens used")
    response_time_ms: Optional[int] = Field(None, description="Response time in milliseconds")
    cost_usd: Optional[float] = Field(None, description="Cost in USD")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class BusinessAnalyticsEventRequest(BaseModel):
    """Request model for business analytics events"""
    business_id: str = Field(..., description="Business ID")
    metric_name: str = Field(..., description="Metric name")
    metric_value: Any = Field(..., description="Metric value")
    metric_type: str = Field("counter", description="Metric type: counter, gauge, histogram")
    dimensions: Dict[str, str] = Field(default_factory=dict, description="Metric dimensions")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class TopicCreateRequest(BaseModel):
    """Request model for creating topics"""
    name: str = Field(..., description="Topic name")
    partitions: int = Field(1, description="Number of partitions")
    replication_factor: int = Field(1, description="Replication factor")
    config: Dict[str, str] = Field(default_factory=dict, description="Topic configuration")


# Health and Status Endpoints
@router.get("/health", summary="Get Kafka health status")
async def get_kafka_health():
    """Get comprehensive Kafka health status"""
    try:
        kafka_manager = await get_kafka_manager()
        health_status = kafka_manager.get_health_status()
        
        return {
            "status": "success",
            "data": health_status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting Kafka health: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get Kafka health: {str(e)}")


@router.get("/metrics", summary="Get Kafka metrics")
async def get_kafka_metrics():
    """Get Kafka performance metrics"""
    try:
        kafka_manager = await get_kafka_manager()
        metrics = kafka_manager.get_metrics()
        
        return {
            "status": "success",
            "data": metrics,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting Kafka metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get Kafka metrics: {str(e)}")


@router.get("/status", summary="Get Kafka service status")
async def get_kafka_status():
    """Get overall Kafka service status"""
    try:
        kafka_manager = await get_kafka_manager()
        integrator = await get_kafka_service_integrator()
        
        status = {
            "kafka_manager": {
                "initialized": kafka_manager._initialized,
                "running": kafka_manager._running,
                "topics_created": len(kafka_manager._topics_created),
                "active_consumers": len(kafka_manager.consumers),
                "producer_active": kafka_manager.producer is not None and kafka_manager.producer.is_running()
            },
            "service_integrator": {
                "initialized": integrator._initialized,
                "integrations_count": len(integrator.integrations),
                "event_publishers_count": len(integrator.event_publishers)
            },
            "health": kafka_manager.get_health_status()
        }
        
        return {
            "status": "success",
            "data": status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting Kafka status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get Kafka status: {str(e)}")


# Topic Management Endpoints
@router.get("/topics", summary="List Kafka topics")
async def list_topics():
    """List all Kafka topics with metadata"""
    try:
        kafka_manager = await get_kafka_manager()
        
        topics_info = {}
        for topic_name in kafka_manager._topics_created:
            metadata = await kafka_manager.get_topic_metadata(topic_name)
            topics_info[topic_name] = metadata
        
        return {
            "status": "success",
            "data": {
                "topics": topics_info,
                "total_topics": len(topics_info)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error listing topics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list topics: {str(e)}")


@router.post("/topics", summary="Create a new Kafka topic")
async def create_topic(request: TopicCreateRequest):
    """Create a new Kafka topic"""
    try:
        kafka_manager = await get_kafka_manager()
        
        await kafka_manager.create_topic(
            name=request.name,
            partitions=request.partitions,
            replication_factor=request.replication_factor,
            config=request.config
        )
        
        return {
            "status": "success",
            "message": f"Topic '{request.name}' created successfully",
            "data": {
                "topic_name": request.name,
                "partitions": request.partitions,
                "replication_factor": request.replication_factor
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error creating topic: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create topic: {str(e)}")


@router.delete("/topics/{topic_name}", summary="Delete a Kafka topic")
async def delete_topic(topic_name: str):
    """Delete a Kafka topic"""
    try:
        kafka_manager = await get_kafka_manager()
        await kafka_manager.delete_topic(topic_name)
        
        return {
            "status": "success",
            "message": f"Topic '{topic_name}' deleted successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error deleting topic: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete topic: {str(e)}")


# Event Publishing Endpoints
@router.post("/events/conversation", summary="Publish conversation event")
async def publish_conversation_event(request: ConversationEventRequest):
    """Publish a conversation-related event"""
    try:
        if request.action == "started":
            await publish_conversation_started(
                conversation_id=request.conversation_id,
                user_id=request.user_id,
                metadata=request.metadata
            )
        elif request.action == "message":
            from app.core.kafka.integration import publish_conversation_message
            await publish_conversation_message(
                conversation_id=request.conversation_id,
                user_id=request.user_id,
                message_content=request.message_content or "",
                message_type=request.message_type or "user",
                metadata=request.metadata
            )
        elif request.action == "ended":
            from app.core.kafka.integration import publish_conversation_ended
            await publish_conversation_ended(
                conversation_id=request.conversation_id,
                user_id=request.user_id,
                metadata=request.metadata
            )
        else:
            raise HTTPException(status_code=400, detail=f"Invalid action: {request.action}")
        
        return {
            "status": "success",
            "message": f"Conversation {request.action} event published successfully",
            "data": {
                "conversation_id": request.conversation_id,
                "action": request.action,
                "user_id": request.user_id
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error publishing conversation event: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to publish conversation event: {str(e)}")


@router.post("/events/ai-response", summary="Publish AI response event")
async def publish_ai_response_event(request: AIResponseEventRequest):
    """Publish an AI response event"""
    try:
        response_data = {
            "prompt": request.prompt,
            "response": request.response,
            "tokens_used": request.tokens_used,
            "response_time_ms": request.response_time_ms,
            "cost_usd": request.cost_usd,
            **request.metadata
        }
        
        await publish_ai_response_generated(
            model_name=request.model_name,
            response_data=response_data,
            user_id=request.user_id,
            conversation_id=request.conversation_id
        )
        
        return {
            "status": "success",
            "message": "AI response event published successfully",
            "data": {
                "model_name": request.model_name,
                "user_id": request.user_id,
                "conversation_id": request.conversation_id,
                "tokens_used": request.tokens_used
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error publishing AI response event: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to publish AI response event: {str(e)}")


@router.post("/events/business-analytics", summary="Publish business analytics event")
async def publish_business_analytics_event(request: BusinessAnalyticsEventRequest):
    """Publish a business analytics event"""
    try:
        metadata = {
            "metric_type": request.metric_type,
            "dimensions": request.dimensions,
            **request.metadata
        }
        
        await publish_business_analytics_update(
            metric_name=request.metric_name,
            metric_value=request.metric_value,
            business_id=request.business_id,
            metadata=metadata
        )
        
        return {
            "status": "success",
            "message": "Business analytics event published successfully",
            "data": {
                "business_id": request.business_id,
                "metric_name": request.metric_name,
                "metric_value": request.metric_value
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error publishing business analytics event: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to publish business analytics event: {str(e)}")


@router.post("/events/generic", summary="Publish generic event")
async def publish_generic_event(request: EventPublishRequest):
    """Publish a generic event"""
    try:
        kafka_manager = await get_kafka_manager()
        
        # Create event
        event = Event(
            type=EventType(request.event_type),
            source="api_endpoint",
            data=request.data,
            metadata=request.metadata,
            user_id=request.user_id,
            correlation_id=request.correlation_id
        )
        
        # Determine topic based on event type
        topic_mapping = {
            "conversation.started": "conversation.events",
            "conversation.message": "conversation.events", 
            "conversation.ended": "conversation.events",
            "ai.response.generated": "ai.responses",
            "business.analytics.update": "business.analytics",
            "system.error": "system.monitoring",
            "system.health_check": "system.monitoring"
        }
        
        topic = topic_mapping.get(request.event_type, "system.monitoring")
        
        await kafka_manager.publish_event(topic, event)
        
        return {
            "status": "success",
            "message": f"Event published successfully to topic '{topic}'",
            "data": {
                "event_id": event.id,
                "event_type": request.event_type,
                "topic": topic
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error publishing generic event: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to publish generic event: {str(e)}")


# Consumer Management Endpoints
@router.get("/consumers", summary="Get consumer information")
async def get_consumers():
    """Get information about active consumers"""
    try:
        kafka_manager = await get_kafka_manager()
        
        consumers_info = {}
        for topic, consumer in kafka_manager.consumers.items():
            metrics = consumer.get_metrics()
            consumers_info[topic] = {
                "topic": topic,
                "group_id": consumer.group_id,
                "running": consumer.is_running(),
                "metrics": metrics
            }
        
        return {
            "status": "success",
            "data": {
                "consumers": consumers_info,
                "total_consumers": len(consumers_info)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting consumers: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get consumers: {str(e)}")


@router.post("/consumers/{topic}/reset-offset", summary="Reset consumer offset")
async def reset_consumer_offset(
    topic: str,
    partition: int = Query(..., description="Partition number"),
    offset: int = Query(..., description="Offset to reset to")
):
    """Reset consumer offset for a topic partition"""
    try:
        kafka_manager = await get_kafka_manager()
        await kafka_manager.reset_consumer_offset(topic, partition, offset)
        
        return {
            "status": "success",
            "message": f"Consumer offset reset for topic '{topic}' partition {partition} to offset {offset}",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error resetting consumer offset: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset consumer offset: {str(e)}")


# Dead Letter Queue Endpoints
@router.get("/dead-letter-queue/stats", summary="Get dead letter queue statistics")
async def get_dlq_stats():
    """Get dead letter queue statistics"""
    try:
        kafka_manager = await get_kafka_manager()
        
        # This would require accessing the DLQ manager from the producer
        # For now, return placeholder data
        stats = {
            "total_dead_letters": 0,
            "pending_retries": 0,
            "retry_success_rate": 0.0,
            "common_failure_reasons": {}
        }
        
        return {
            "status": "success",
            "data": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting DLQ stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get DLQ stats: {str(e)}")


# Monitoring and Alerting Endpoints
@router.get("/alerts", summary="Get active Kafka alerts")
async def get_kafka_alerts():
    """Get active Kafka alerts"""
    try:
        kafka_manager = await get_kafka_manager()
        
        if kafka_manager.monitor:
            active_alerts = kafka_manager.monitor.get_active_alerts()
            alert_data = [
                {
                    "id": alert.id,
                    "level": alert.level.value,
                    "title": alert.title,
                    "message": alert.message,
                    "timestamp": alert.timestamp.isoformat(),
                    "source": alert.source,
                    "resolved": alert.resolved
                }
                for alert in active_alerts
            ]
        else:
            alert_data = []
        
        return {
            "status": "success",
            "data": {
                "alerts": alert_data,
                "total_alerts": len(alert_data)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting Kafka alerts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get Kafka alerts: {str(e)}")


@router.get("/prometheus-metrics", summary="Get Prometheus metrics")
async def get_prometheus_metrics():
    """Get Kafka metrics in Prometheus format"""
    try:
        kafka_manager = await get_kafka_manager()
        
        if kafka_manager.monitor:
            metrics = kafka_manager.monitor.export_metrics("prometheus")
            return {
                "status": "success",
                "data": metrics,
                "content_type": "text/plain",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {
                "status": "success",
                "data": "# No metrics available\n",
                "content_type": "text/plain",
                "timestamp": datetime.utcnow().isoformat()
            }
        
    except Exception as e:
        logger.error(f"Error getting Prometheus metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get Prometheus metrics: {str(e)}")


# Administrative Endpoints
@router.post("/restart", summary="Restart Kafka services")
async def restart_kafka_services(background_tasks: BackgroundTasks):
    """Restart Kafka services (use with caution)"""
    try:
        async def restart_task():
            kafka_manager = await get_kafka_manager()
            await kafka_manager.stop()
            await asyncio.sleep(2)
            await kafka_manager.start()
        
        background_tasks.add_task(restart_task)
        
        return {
            "status": "success",
            "message": "Kafka services restart initiated",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error restarting Kafka services: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to restart Kafka services: {str(e)}")


@router.get("/config", summary="Get Kafka configuration")
async def get_kafka_config():
    """Get current Kafka configuration"""
    try:
        from app.config.settings import settings
        
        config = {
            "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "security_protocol": settings.KAFKA_SECURITY_PROTOCOL,
            "consumer_group_id": settings.KAFKA_CONSUMER_GROUP_ID,
            "topics": settings.KAFKA_TOPICS,
            "producer_config": {
                "acks": settings.KAFKA_PRODUCER_ACKS,
                "retries": settings.KAFKA_PRODUCER_RETRIES,
                "batch_size": settings.KAFKA_PRODUCER_BATCH_SIZE,
                "compression_type": settings.KAFKA_PRODUCER_COMPRESSION_TYPE
            },
            "consumer_config": {
                "auto_offset_reset": settings.KAFKA_CONSUMER_AUTO_OFFSET_RESET,
                "enable_auto_commit": settings.KAFKA_CONSUMER_ENABLE_AUTO_COMMIT,
                "max_poll_records": settings.KAFKA_CONSUMER_MAX_POLL_RECORDS
            }
        }
        
        return {
            "status": "success",
            "data": config,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting Kafka config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get Kafka config: {str(e)}")
