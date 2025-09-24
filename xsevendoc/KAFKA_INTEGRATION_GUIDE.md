# Kafka Integration Guide for X-SevenAI

## Overview

This guide provides comprehensive documentation for the modern Kafka integration implemented in the X-SevenAI backend. The integration provides event-driven architecture, real-time messaging, and comprehensive monitoring capabilities.

## Architecture

### Core Components

1. **Kafka Manager** (`app/core/kafka/manager.py`)
   - Central coordination for all Kafka operations
   - Topic management and lifecycle
   - Producer/consumer coordination
   - Health monitoring integration

2. **Event System** (`app/core/kafka/events.py`)
   - Event-driven messaging patterns
   - Event bus for internal routing
   - Event handlers for different event types
   - Standardized event schemas

3. **Producer** (`app/core/kafka/producer.py`)
   - Async message publishing
   - Transaction support
   - Automatic retries with exponential backoff
   - Schema validation
   - Metrics collection

4. **Consumer** (`app/core/kafka/consumer.py`)
   - Async message consumption
   - Manual offset management
   - Dead letter queue handling
   - Batch processing support
   - Error recovery mechanisms

5. **Dead Letter Queue** (`app/core/kafka/dead_letter_queue.py`)
   - Failed message handling
   - Retry strategies (exponential backoff, fixed delay, linear backoff)
   - Error analysis and categorization
   - Recovery mechanisms

6. **Monitoring** (`app/core/kafka/monitoring.py`)
   - Prometheus metrics integration
   - Real-time health monitoring
   - Alert system with multiple severity levels
   - Performance tracking

7. **Service Integration** (`app/core/kafka/integration.py`)
   - Integration with existing X-SevenAI services
   - Event publishing convenience functions
   - Service-specific event handlers

## Topics and Event Types

### Configured Topics

1. **conversation.events**
   - Partitions: 3
   - Retention: 7 days (compacted)
   - Events: conversation started, message, ended

2. **ai.responses**
   - Partitions: 6
   - Retention: 3 days
   - Events: AI response generated, model switched

3. **business.analytics**
   - Partitions: 2
   - Retention: 30 days (compacted)
   - Events: business metrics updates

4. **system.monitoring**
   - Partitions: 1
   - Retention: 1 day
   - Events: system health, errors, monitoring data

5. **dead.letter.queue**
   - Partitions: 1
   - Retention: 7 days
   - Events: failed messages for retry/analysis

### Event Types

```python
class EventType(str, Enum):
    CONVERSATION_STARTED = "conversation.started"
    CONVERSATION_MESSAGE = "conversation.message"
    CONVERSATION_ENDED = "conversation.ended"
    AI_RESPONSE_GENERATED = "ai.response.generated"
    AI_MODEL_SWITCHED = "ai.model.switched"
    BUSINESS_ANALYTICS_UPDATE = "business.analytics.update"
    USER_ACTION = "user.action"
    SYSTEM_ERROR = "system.error"
    HEALTH_CHECK = "system.health_check"
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"
```

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS=["localhost:9092"]
KAFKA_SECURITY_PROTOCOL=PLAINTEXT
KAFKA_CONSUMER_GROUP_ID=xseven-ai-consumers

# Schema Registry
SCHEMA_REGISTRY_URL=http://localhost:8081

# Producer Settings
KAFKA_PRODUCER_ACKS=all
KAFKA_PRODUCER_RETRIES=3
KAFKA_PRODUCER_BATCH_SIZE=16384
KAFKA_PRODUCER_COMPRESSION_TYPE=gzip

# Consumer Settings
KAFKA_CONSUMER_AUTO_OFFSET_RESET=earliest
KAFKA_CONSUMER_ENABLE_AUTO_COMMIT=false
KAFKA_CONSUMER_MAX_POLL_RECORDS=500

# Event Sourcing
ENABLE_EVENT_SOURCING=true
```

### Docker Configuration

The `docker-compose.yml` includes:
- Zookeeper
- Kafka Broker
- Schema Registry
- Kafka Connect
- Kafka UI (management interface)
- Kafka Exporter (Prometheus metrics)

## Usage Examples

### Publishing Events

#### Conversation Events

```python
from app.core.kafka.integration import (
    publish_conversation_started,
    publish_conversation_message,
    publish_ai_response_generated
)

# Start conversation
await publish_conversation_started(
    conversation_id="conv_123",
    user_id="user_456",
    metadata={
        "conversation_type": "customer_support",
        "business_id": "biz_789"
    }
)

# Send message
await publish_conversation_message(
    conversation_id="conv_123",
    user_id="user_456",
    message_content="Hello, I need help with my order",
    message_type="user"
)

# AI response
await publish_ai_response_generated(
    model_name="gpt-4",
    response_data={
        "prompt": "Hello, I need help with my order",
        "response": "I'd be happy to help you with your order...",
        "tokens_used": 150,
        "response_time_ms": 1200,
        "cost_usd": 0.003
    },
    user_id="user_456",
    conversation_id="conv_123"
)
```

#### Business Analytics Events

```python
from app.core.kafka.integration import publish_business_analytics_update

await publish_business_analytics_update(
    metric_name="daily_active_users",
    metric_value=1250,
    business_id="biz_789",
    metadata={
        "metric_type": "gauge",
        "dimensions": {
            "region": "us-east-1",
            "plan": "premium"
        }
    }
)
```

### Custom Event Handlers

```python
from app.core.kafka.events import EventHandler, Event, EventType

class CustomAnalyticsHandler(EventHandler):
    def __init__(self):
        super().__init__("custom_analytics")
    
    def can_handle(self, event: Event) -> bool:
        return event.type == EventType.BUSINESS_ANALYTICS_UPDATE
    
    async def handle(self, event: Event) -> None:
        # Process analytics event
        metric_name = event.data.get('metric_name')
        metric_value = event.data.get('metric_value')
        
        # Store in analytics database
        await self.store_metric(metric_name, metric_value)
        
        # Update real-time dashboard
        await self.update_dashboard(metric_name, metric_value)

# Register handler
kafka_manager = await get_kafka_manager()
handler = CustomAnalyticsHandler()
kafka_manager.event_bus.subscribe(EventType.BUSINESS_ANALYTICS_UPDATE, handler)
```

## API Endpoints

### Kafka Management API

All endpoints are available under `/api/v1/kafka/`:

#### Health and Status
- `GET /health` - Get Kafka health status
- `GET /metrics` - Get performance metrics
- `GET /status` - Get overall service status

#### Topic Management
- `GET /topics` - List all topics
- `POST /topics` - Create new topic
- `DELETE /topics/{topic_name}` - Delete topic

#### Event Publishing
- `POST /events/conversation` - Publish conversation event
- `POST /events/ai-response` - Publish AI response event
- `POST /events/business-analytics` - Publish analytics event
- `POST /events/generic` - Publish generic event

#### Consumer Management
- `GET /consumers` - Get consumer information
- `POST /consumers/{topic}/reset-offset` - Reset consumer offset

#### Monitoring
- `GET /alerts` - Get active alerts
- `GET /prometheus-metrics` - Get Prometheus metrics
- `GET /dead-letter-queue/stats` - Get DLQ statistics

### Example API Calls

```bash
# Check Kafka health
curl http://localhost:8000/api/v1/kafka/health

# Publish conversation event
curl -X POST http://localhost:8000/api/v1/kafka/events/conversation \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "conv_123",
    "user_id": "user_456",
    "action": "started",
    "metadata": {
      "conversation_type": "support"
    }
  }'

# Get metrics
curl http://localhost:8000/api/v1/kafka/metrics
```

## Monitoring and Observability

### Prometheus Metrics

The integration exposes comprehensive metrics:

- **Producer Metrics**
  - `kafka_producer_messages_sent_total`
  - `kafka_producer_messages_failed_total`
  - `kafka_producer_send_duration_seconds`
  - `kafka_producer_batch_size`

- **Consumer Metrics**
  - `kafka_consumer_messages_consumed_total`
  - `kafka_consumer_messages_processed_total`
  - `kafka_consumer_processing_duration_seconds`
  - `kafka_consumer_lag`

- **System Metrics**
  - `kafka_system_health_score`
  - `kafka_active_alerts_count`
  - `kafka_topic_partition_count`

### Health Checks

The system provides multiple health check endpoints:

- **Liveness**: `/api/v1/kafka/health` - Basic service availability
- **Readiness**: Integrated into main health check
- **Deep Health**: Comprehensive component status

### Alerting

Built-in alerting system with configurable thresholds:

- **Consumer Lag**: Alert when lag exceeds thresholds
- **Error Rates**: Alert on high error rates
- **Response Times**: Alert on slow processing
- **System Resources**: Alert on resource usage

## Dead Letter Queue

### Failure Handling

The DLQ system handles various failure scenarios:

1. **Deserialization Errors**: Invalid message format
2. **Schema Validation Errors**: Message doesn't match schema
3. **Processing Errors**: Handler execution failures
4. **Timeout Errors**: Processing takes too long
5. **Dependency Errors**: External service unavailable

### Retry Strategies

- **Exponential Backoff**: Increasing delays (default)
- **Fixed Delay**: Constant retry interval
- **Linear Backoff**: Linearly increasing delays
- **No Retry**: Send directly to DLQ

### Recovery

Failed messages can be:
- Automatically retried with backoff
- Manually retried via API
- Analyzed for error patterns
- Permanently archived after max retries

## Performance Tuning

### Producer Optimization

```python
# High throughput settings
KAFKA_PRODUCER_BATCH_SIZE=32768
KAFKA_PRODUCER_LINGER_MS=20
KAFKA_PRODUCER_COMPRESSION_TYPE=lz4

# Low latency settings
KAFKA_PRODUCER_BATCH_SIZE=1
KAFKA_PRODUCER_LINGER_MS=0
KAFKA_PRODUCER_ACKS=1
```

### Consumer Optimization

```python
# High throughput settings
KAFKA_CONSUMER_MAX_POLL_RECORDS=1000
KAFKA_CONSUMER_FETCH_MIN_BYTES=50000

# Low latency settings
KAFKA_CONSUMER_MAX_POLL_RECORDS=1
KAFKA_CONSUMER_FETCH_MIN_BYTES=1
```

## Security

### Authentication

For production environments, configure SASL authentication:

```bash
KAFKA_SECURITY_PROTOCOL=SASL_SSL
KAFKA_SASL_MECHANISM=PLAIN
KAFKA_SASL_USERNAME=your_username
KAFKA_SASL_PASSWORD=your_password
```

### SSL/TLS

Configure SSL certificates:

```bash
KAFKA_SSL_CAFILE=/path/to/ca-cert
KAFKA_SSL_CERTFILE=/path/to/client-cert
KAFKA_SSL_KEYFILE=/path/to/client-key
```

## Deployment

### Development

```bash
# Start services
docker-compose up -d

# Check Kafka UI
open http://localhost:8080

# Start application
python -m uvicorn app.main:app --reload
```

### Production

1. **Resource Allocation**
   - Kafka: 4+ CPU cores, 8+ GB RAM
   - Zookeeper: 2+ CPU cores, 4+ GB RAM

2. **Replication**
   - Set replication factor ≥ 3
   - Configure min.insync.replicas ≥ 2

3. **Monitoring**
   - Deploy Prometheus + Grafana
   - Configure alerting rules
   - Set up log aggregation

## Troubleshooting

### Common Issues

1. **Connection Errors**
   ```bash
   # Check Kafka connectivity
   docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092
   ```

2. **Consumer Lag**
   ```bash
   # Check consumer group status
   docker exec kafka kafka-consumer-groups --bootstrap-server localhost:9092 --describe --group xseven-ai-consumers
   ```

3. **Topic Issues**
   ```bash
   # List topics
   docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list
   
   # Describe topic
   docker exec kafka kafka-topics --bootstrap-server localhost:9092 --describe --topic conversation.events
   ```

### Debug Mode

Enable debug logging:

```python
import logging
logging.getLogger('app.core.kafka').setLevel(logging.DEBUG)
```

## Migration Guide

### From Existing System

1. **Phase 1**: Deploy Kafka infrastructure
2. **Phase 2**: Add event publishing (non-blocking)
3. **Phase 3**: Add event consumers
4. **Phase 4**: Migrate existing integrations
5. **Phase 5**: Enable full event-driven architecture

### Data Migration

Use Kafka Connect for migrating existing data:

```json
{
  "name": "supabase-source-connector",
  "config": {
    "connector.class": "io.confluent.connect.jdbc.JdbcSourceConnector",
    "connection.url": "jdbc:postgresql://localhost:5432/xsevenai",
    "mode": "incrementing",
    "incrementing.column.name": "id",
    "topic.prefix": "supabase-"
  }
}
```

## Best Practices

1. **Event Design**
   - Use consistent event schemas
   - Include correlation IDs
   - Add metadata for debugging
   - Version your events

2. **Error Handling**
   - Implement circuit breakers
   - Use dead letter queues
   - Log errors with context
   - Monitor error rates

3. **Performance**
   - Batch operations when possible
   - Use appropriate partitioning
   - Monitor consumer lag
   - Tune producer/consumer settings

4. **Security**
   - Use authentication in production
   - Encrypt sensitive data
   - Implement access controls
   - Audit event access

## Support

For issues or questions:

1. Check the logs: `docker-compose logs kafka`
2. Use Kafka UI: http://localhost:8080
3. Monitor metrics: `/api/v1/kafka/metrics`
4. Check health: `/api/v1/kafka/health`

## Future Enhancements

Planned improvements:

1. **Schema Evolution**: Automatic schema migration
2. **Multi-Region**: Cross-region replication
3. **Stream Processing**: Real-time analytics with Kafka Streams
4. **Advanced Security**: OAuth2, mTLS support
5. **Performance**: Optimized serialization, compression
6. **Observability**: Distributed tracing integration
