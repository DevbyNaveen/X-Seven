# Evolution API Integration Guide for X-SevenAI

## 📋 Overview

This guide documents the comprehensive Evolution API integration implemented in the X-SevenAI backend system. The integration provides multi-tenant WhatsApp Business API capabilities with AI-powered responses, enabling each business to have dedicated phone numbers and WhatsApp instances.

## 🎯 Key Features

### Core Capabilities
- **Multi-Tenant Architecture**: Each business gets a dedicated Evolution API instance
- **WhatsApp Business Integration**: Professional WhatsApp Business accounts with verified profiles
- **AI-Powered Responses**: Integration with existing DSPy modules for optimized responses
- **Phone Number Management**: Automatic provisioning via Twilio/Vonage
- **Real-time Webhooks**: Instant message processing and status updates
- **Scalable Design**: Support for 500+ businesses per Evolution API server

### Business Benefits
- **Dedicated Communication**: Each business has its own phone number and WhatsApp
- **Professional Branding**: WhatsApp Business profiles with custom branding
- **24/7 AI Support**: Intelligent responses using business-specific context
- **Multi-Channel**: Phone calls and WhatsApp messages in one platform
- **Analytics & Insights**: Comprehensive usage and performance metrics

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   X-SevenAI     │    │  Evolution API   │    │   External      │
│   Backend       │◄──►│   (Multi-Tenant) │◄──►│   Services      │
│                 │    │                  │    │                 │
│ • FastAPI       │    │ • WhatsApp API   │    │ • Twilio        │
│ • Business Logic│    │ • Instance Mgmt  │    │ • Vonage        │
│ • DSPy AI       │    │ • Webhook Handler│    │ • OpenAI/Groq   │
│ • Database      │    │ • Message Queue  │    │ • Anthropic     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 📁 File Structure

```
app/
├── models/
│   └── evolution_instance.py          # Evolution API data models
├── services/
│   └── evolution/
│       ├── __init__.py                # Service exports
│       ├── client.py                  # Evolution API client
│       ├── manager.py                 # Business integration manager
│       ├── webhook_handler.py         # Webhook event processor
│       └── ai_integration.py          # DSPy AI integration
├── api/
│   └── v1/
│       └── evolution_api.py           # REST API endpoints
└── config/
    └── settings.py                    # Configuration updates

db/
└── migrations/
    └── add_evolution_api_tables.sql   # Database schema

tests/
└── test_evolution_integration.py     # Comprehensive test suite
```

## 🗄️ Database Schema

### Evolution Instances Table
```sql
CREATE TABLE evolution_instances (
    id SERIAL PRIMARY KEY,
    business_id INTEGER REFERENCES businesses(id),
    instance_name VARCHAR(255) UNIQUE,
    phone_number VARCHAR(50),
    whatsapp_enabled BOOLEAN DEFAULT FALSE,
    status VARCHAR(50) DEFAULT 'creating',
    monthly_cost DECIMAL(10,2) DEFAULT 0.00,
    -- ... additional fields
);
```

### Evolution Messages Table
```sql
CREATE TABLE evolution_messages (
    id SERIAL PRIMARY KEY,
    evolution_instance_id INTEGER REFERENCES evolution_instances(id),
    business_id INTEGER REFERENCES businesses(id),
    message_id VARCHAR(255),
    content TEXT,
    direction VARCHAR(20), -- 'inbound' or 'outbound'
    ai_processed BOOLEAN DEFAULT FALSE,
    -- ... additional fields
);
```

### Evolution Webhook Events Table
```sql
CREATE TABLE evolution_webhook_events (
    id SERIAL PRIMARY KEY,
    instance_name VARCHAR(255),
    event_type VARCHAR(100),
    event_data JSONB DEFAULT '{}',
    processed BOOLEAN DEFAULT FALSE,
    -- ... additional fields
);
```

## 🔧 Configuration

### Environment Variables
```bash
# Evolution API Configuration
EVOLUTION_API_URL=http://localhost:8080
EVOLUTION_API_KEY=your_secure_evolution_api_key
EVOLUTION_DEFAULT_WEBHOOK=http://your-domain.com/api/v1/evolution/webhook
EVOLUTION_MAX_INSTANCES_PER_SERVER=500
EVOLUTION_SESSION_TIMEOUT=3600000
EVOLUTION_RATE_LIMIT_PER_INSTANCE=1000

# Base URL for webhook callbacks
BASE_URL=http://your-domain.com
```

### Settings Integration
The Evolution API configuration is integrated into the existing settings system:

```python
# app/config/settings.py
class Settings(BaseSettings):
    # Evolution API Configuration
    EVOLUTION_API_URL: Optional[str] = "http://localhost:8080"
    EVOLUTION_API_KEY: Optional[str] = None
    EVOLUTION_DEFAULT_WEBHOOK: Optional[str] = None
    # ... additional settings
```

## 🚀 API Endpoints

### Business Management Endpoints

#### Setup Evolution API for Business
```http
POST /api/v1/evolution/{business_id}/setup
Content-Type: application/json
Authorization: Bearer {token}

{
  "country_code": "LV",
  "enable_whatsapp": true,
  "business_profile": {
    "name": "Sunrise Cafe",
    "description": "Best coffee in Riga",
    "category": "food_hospitality"
  }
}
```

#### Get Business Evolution Status
```http
GET /api/v1/evolution/{business_id}/status
Authorization: Bearer {token}

Response:
{
  "configured": true,
  "instance_name": "business_123",
  "phone_number": "+37120123456",
  "status": "active",
  "whatsapp_enabled": true,
  "whatsapp_status": "connected",
  "monthly_cost": 35.0,
  "usage_stats": {
    "messages_sent": 150,
    "messages_received": 89,
    "calls_handled": 23
  }
}
```

#### Send Message to Customer
```http
POST /api/v1/evolution/{business_id}/send-message
Authorization: Bearer {token}
Content-Type: application/json

{
  "customer_number": "+37120987654",
  "message": "Thank you for your inquiry!",
  "message_type": "text"
}
```

#### Get WhatsApp QR Code
```http
GET /api/v1/evolution/{business_id}/qr-code
Authorization: Bearer {token}

Response:
{
  "success": true,
  "data": {
    "qr_code": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
    "qr_image": "base64_image_data",
    "instance_name": "business_123"
  }
}
```

### Webhook Endpoints

#### Evolution API Webhook Handler
```http
POST /api/v1/evolution/webhook/{instance_name}
Content-Type: application/json

{
  "event": "messages.upsert",
  "data": [{
    "key": {
      "id": "msg_123",
      "fromMe": false,
      "remoteJid": "37120987654@c.us"
    },
    "message": {
      "conversation": "Hello, I need help!"
    }
  }]
}
```

### Analytics Endpoints

#### Get Business Analytics
```http
GET /api/v1/evolution/{business_id}/analytics?days=30
Authorization: Bearer {token}

Response:
{
  "success": true,
  "data": {
    "period_days": 30,
    "total_messages": 245,
    "inbound_messages": 134,
    "outbound_messages": 111,
    "ai_processed_messages": 128,
    "ai_processing_rate": 0.955,
    "average_response_time": 0.847,
    "monthly_cost": 35.0
  }
}
```

## 🤖 AI Integration

### DSPy Integration
The Evolution API integration leverages the existing DSPy infrastructure for enhanced AI responses:

```python
# app/services/evolution/ai_integration.py
class EvolutionAIIntegration:
    def __init__(self, db: Session):
        self.intent_detector = IntentDetectionModule()
        self.response_generator = ResponseGenerationModule()
        self.business_intent_detector = BusinessSpecificIntentModule()
        self.conversation_summarizer = ConversationSummaryModule()
```

### AI Response Flow
1. **Message Receipt**: Webhook receives customer message
2. **Intent Detection**: DSPy modules classify customer intent
3. **Context Building**: Business and conversation context prepared
4. **Response Generation**: AI generates contextual response
5. **Message Sending**: Response sent via Evolution API
6. **Analytics Tracking**: Performance metrics recorded

### Business-Specific Optimization
```python
# Optimize DSPy modules for specific business
await ai_integration.optimize_responses(
    business_id=123,
    optimization_budget=20
)
```

## 📊 Usage Examples

### Complete Business Onboarding
```python
from app.services.evolution.manager import EvolutionManager

async with EvolutionManager(db) as manager:
    result = await manager.onboard_business_evolution(
        business_id=123,
        country_code="LV",
        enable_whatsapp=True,
        business_profile={
            "name": "Sunrise Cafe",
            "description": "Best coffee in Riga",
            "category": "food_hospitality"
        }
    )
    print(f"Setup complete: {result['phone_number']}")
```

### Processing Incoming Messages
```python
from app.services.evolution.webhook_handler import EvolutionWebhookHandler

handler = EvolutionWebhookHandler(db)
result = await handler.process_webhook(
    instance_name="business_123",
    event_data=webhook_data
)
```

### Sending AI-Generated Responses
```python
from app.services.evolution.ai_integration import EvolutionAIIntegration

ai_integration = EvolutionAIIntegration(db)
response = await ai_integration.generate_response(
    message="I want to make a reservation",
    business_id=123,
    customer_number="+37120987654",
    evolution_instance=instance
)
```

## 🔄 Webhook Event Types

### Message Events
- `messages.upsert`: New messages received
- `messages.update`: Message status updates (delivered, read)

### Connection Events
- `connection.update`: WhatsApp connection status changes
- `qrcode.updated`: New QR code generated for connection

### Instance Events
- `instance.created`: New instance created
- `instance.deleted`: Instance deleted

## 📈 Performance Metrics

### Key Performance Indicators
- **Message Processing Time**: Target < 800ms
- **WhatsApp Session Uptime**: Target > 99.9%
- **Message Delivery Rate**: Target > 98%
- **AI Response Accuracy**: 20-50% improvement with DSPy
- **Webhook Processing Success**: Target > 99%

### Monitoring
```python
# Health check endpoint
GET /api/v1/evolution/health

Response:
{
  "success": true,
  "status": "healthy",
  "evolution_api": {
    "status": "connected",
    "instances": 45,
    "uptime": "99.97%"
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## 🛠️ Development Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Database Migration
```bash
# Run the Evolution API migration
psql -d your_database -f db/migrations/add_evolution_api_tables.sql
```

### 3. Environment Configuration
```bash
# Copy and configure environment variables
cp .env.evolution.example .env
# Edit .env with your Evolution API settings
```

### 4. Start Evolution API Server
```bash
# Using Docker Compose
docker-compose -f docker-compose.evolution.yml up -d
```

### 5. Test Integration
```bash
# Run comprehensive test suite
python -m pytest test_evolution_integration.py -v
```

## 🧪 Testing

### Test Categories
- **Unit Tests**: Individual component testing
- **Integration Tests**: Service interaction testing
- **End-to-End Tests**: Complete workflow testing
- **Performance Tests**: Load and scalability testing

### Running Tests
```bash
# Run all Evolution API tests
pytest test_evolution_integration.py -v --asyncio-mode=auto

# Run specific test categories
pytest test_evolution_integration.py::TestEvolutionAPIClient -v
pytest test_evolution_integration.py::TestEvolutionManager -v
pytest test_evolution_integration.py::TestEvolutionWebhookHandler -v
```

## 🚨 Error Handling

### Common Error Scenarios
1. **Evolution API Unavailable**: Fallback to traditional AI handler
2. **WhatsApp Connection Lost**: Automatic reconnection attempts
3. **Message Delivery Failed**: Retry mechanism with exponential backoff
4. **DSPy Module Failure**: Graceful degradation to rule-based responses

### Error Monitoring
```python
# Errors are logged and tracked
logger.error(f"Evolution API error: {error}")

# Metrics are updated for monitoring
evolution_instance.error_count += 1
evolution_instance.last_error = str(error)
```

## 📊 Business Metrics

### Subscription Plan Integration
- **Basic Plan**: No Evolution API access
- **Pro Plan**: Evolution API + WhatsApp ($35/month)
- **Enterprise Plan**: Full features + Premium support ($60/month)

### Usage Limits
```python
# Pro Plan Limits
{
    "messages_per_month": 5000,
    "calls_per_month": 500,
    "contacts": 2000
}

# Enterprise Plan Limits
{
    "messages_per_month": -1,  # Unlimited
    "calls_per_month": -1,     # Unlimited
    "contacts": -1             # Unlimited
}
```

## 🔒 Security Considerations

### API Security
- **Authentication**: Bearer token authentication for all endpoints
- **Authorization**: Business ownership verification
- **Rate Limiting**: Per-instance and per-business rate limits
- **Input Validation**: Comprehensive request validation

### Data Protection
- **Message Encryption**: End-to-end encryption for WhatsApp messages
- **Data Isolation**: Business data completely isolated
- **GDPR Compliance**: Data retention and deletion policies
- **Audit Logging**: Complete audit trail for all operations

## 🔄 Deployment

### Production Deployment
1. **Evolution API Server**: Deploy using Docker Compose
2. **Database Migration**: Run schema updates
3. **Environment Configuration**: Set production environment variables
4. **SSL Certificates**: Configure HTTPS for webhooks
5. **Monitoring Setup**: Configure Prometheus metrics and alerts

### Scaling Considerations
- **Horizontal Scaling**: Multiple Evolution API instances
- **Load Balancing**: Distribute businesses across instances
- **Database Optimization**: Proper indexing and query optimization
- **Caching**: Redis caching for frequently accessed data

## 📚 Additional Resources

### Documentation Links
- [Evolution API Documentation](https://evolution-api.gitbook.io/)
- [WhatsApp Business API](https://developers.facebook.com/docs/whatsapp/)
- [DSPy Framework Documentation](https://dspy-docs.vercel.app/)

### Support Channels
- **GitHub Issues**: Technical issues and bug reports
- **Documentation**: Comprehensive guides and examples
- **Community**: Developer community and discussions

## 🎉 Conclusion

The Evolution API integration transforms X-SevenAI from a basic AI platform into a comprehensive business communication solution. Key benefits include:

### For X-SevenAI Platform
- **Revenue Growth**: New subscription tiers and premium features
- **Competitive Advantage**: Enterprise-grade communication capabilities
- **Scalability**: Support for unlimited business growth
- **Technical Excellence**: Modern, maintainable architecture

### For Businesses
- **Professional Communication**: Dedicated phone numbers and WhatsApp Business
- **AI-Powered Service**: 24/7 intelligent customer support
- **Local Presence**: Country-specific phone numbers
- **Business Growth**: Scalable customer service solution

### Technical Benefits
- **Robust Architecture**: Enterprise-grade reliability and performance
- **Easy Integration**: RESTful APIs with comprehensive documentation
- **Cost-Effective**: Open-source solution with no licensing fees
- **Future-Proof**: Extensible design for future enhancements

The integration successfully combines the power of Evolution API's multi-tenant WhatsApp capabilities with X-SevenAI's advanced AI infrastructure, creating a comprehensive solution for modern business communication needs.

---

*This documentation was created for the X-SevenAI Evolution API integration. Last updated: January 2024*
