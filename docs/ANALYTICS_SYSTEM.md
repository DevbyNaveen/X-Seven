# Dashboard Analytics System Documentation

## Overview

The X-SevenAI Dashboard Analytics System provides comprehensive business intelligence and reporting capabilities for restaurant operations. The system integrates with both `orders` and `messages` tables to provide real-time and historical analytics.

## Architecture

### Core Components

1. **AnalyticsService** (`app/services/analytics_service.py`)
   - Core analytics processing engine
   - Handles both orders and messages analytics
   - Provides combined analytics functionality

2. **Analytics Endpoints** (`app/api/v1/endpoints/analytics_endpoints.py`)
   - Dedicated analytics API endpoints
   - Comprehensive filtering and export capabilities

3. **Dashboard Endpoints** (`app/api/v1/endpoints/dashboard/business_dashboard.py`)
   - Enhanced dashboard with analytics integration
   - Real-time and performance analytics

## Database Tables

### businesses Table
- **email**: Direct email column for analytics (TEXT UNIQUE)
- **contact_info**: JSONB field with additional contact details
- **All other business fields**: name, slug, subscription, etc.

### orders Table
- **business_id**: Links orders to businesses
- **status**: Order status (pending, confirmed, preparing, ready, delivered, cancelled)
- **total_amount**: Order revenue
- **created_at**: Order timestamp
- **All other order fields**: table_id, items, etc.

### messages Table
- **business_id**: Links messages to businesses
- **session_id**: Conversation session identifier
- **content**: Message content
- **created_at**: Message timestamp

## API Endpoints

### Analytics Endpoints (`/api/v1/analytics/`)

#### Orders Analytics
```
GET /api/v1/analytics/orders/{business_id}
```
**Parameters:**
- `period`: "1d", "7d", "30d" (default: "7d")
- `status_filter`: Filter by order status
- `start_date`: Custom start date (ISO format)
- `end_date`: Custom end date (ISO format)

**Response:**
```json
{
  "period": "7d",
  "start_date": "2025-09-12T16:54:34",
  "end_date": "2025-09-19T16:54:34",
  "total_orders": 150,
  "total_revenue": 7500.50,
  "orders": [...],
  "status_distribution": {
    "pending": 5,
    "confirmed": 10,
    "preparing": 15,
    "ready": 20
  },
  "daily_trends": {
    "2025-09-19": {"count": 25, "revenue": 1250.50}
  },
  "average_order_value": 50.02
}
```

#### Messages Analytics
```
GET /api/v1/analytics/messages/{business_id}
```
**Parameters:**
- `period`: "1d", "7d", "30d" (default: "7d")
- `session_id`: Filter by specific session
- `start_date`: Custom start date
- `end_date`: Custom end date

#### Combined Analytics
```
GET /api/v1/analytics/combined/{business_id}
```
Provides integrated analytics from both orders and messages.

#### Create Records
```
POST /api/v1/analytics/orders/{business_id}
POST /api/v1/analytics/messages/{business_id}
```
Create new order/message records with analytics tracking.

#### Export Data
```
GET /api/v1/analytics/orders/{business_id}/export
GET /api/v1/analytics/messages/{business_id}/export
```
Export analytics data in JSON format.

### Dashboard Endpoints (`/api/v1/dashboard/`)

#### Enhanced Dashboard Analytics
```
GET /api/v1/dashboard/{business_id}/analytics/overview
GET /api/v1/dashboard/{business_id}/analytics/realtime
GET /api/v1/dashboard/{business_id}/analytics/performance
```

#### Real-time Analytics
```
GET /api/v1/dashboard/{business_id}/analytics/realtime
```
Provides last hour analytics with performance metrics.

#### Performance Analytics
```
GET /api/v1/dashboard/{business_id}/analytics/performance
```
Includes growth rates, KPIs, and trend analysis.

## Key Features

### Real-time Analytics
- Last hour order and message activity
- Live revenue tracking
- Active conversation monitoring
- Performance metrics per hour

### Historical Analytics
- Customizable time periods (1d, 7d, 30d)
- Daily trend analysis
- Growth rate calculations
- Status distribution tracking

### Advanced Filtering
- Date range filtering
- Status-based filtering
- Session-based filtering
- Business-specific isolation

### Data Export
- JSON format export
- Filtered data export
- Analytics summary export

## Usage Examples

### Get Today's Analytics
```javascript
const response = await fetch('/api/v1/analytics/combined/123?period=1d', {
  headers: {
    'Authorization': 'Bearer ' + token
  }
});
const analytics = await response.json();
```

### Create Order with Analytics
```javascript
const orderData = {
  table_id: 5,
  items: [{name: "Burger", quantity: 2}],
  total_amount: 25.99,
  status: "pending"
};

const response = await fetch('/api/v1/analytics/orders/123', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer ' + token,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(orderData)
});
```

### Get Performance Analytics
```javascript
const response = await fetch('/api/v1/dashboard/123/analytics/performance?period=30d', {
  headers: {
    'Authorization': 'Bearer ' + token
  }
});
const performance = await response.json();
```

## Security & Access Control

- **JWT Authentication**: All endpoints require valid JWT tokens
- **Business Isolation**: Users can only access their own business data
- **Row-level Security**: Supabase RLS policies ensure data protection
- **Input Validation**: All inputs are validated and sanitized

## Performance Optimization

- **Indexed Queries**: Email column indexed for fast lookups
- **Efficient Filtering**: Optimized date range queries
- **Cached Analytics**: Real-time metrics with smart caching
- **Paginated Results**: Large datasets are properly paginated

## Integration Guide

### Frontend Integration
```javascript
// Initialize analytics client
class AnalyticsClient {
  constructor(baseUrl, token) {
    this.baseUrl = baseUrl;
    this.token = token;
  }

  async getDashboardAnalytics(businessId, period = '7d') {
    const response = await fetch(
      `${this.baseUrl}/api/v1/analytics/combined/${businessId}?period=${period}`,
      {
        headers: {
          'Authorization': `Bearer ${this.token}`
        }
      }
    );
    return response.json();
  }

  async createOrder(businessId, orderData) {
    const response = await fetch(
      `${this.baseUrl}/api/v1/analytics/orders/${businessId}`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(orderData)
      }
    );
    return response.json();
  }
}
```

### Backend Integration
```python
from app.services.analytics_service import AnalyticsService

# Get analytics service
analytics_service = AnalyticsService()

# Get comprehensive analytics
analytics = await analytics_service.get_combined_analytics(
    business_id=123,
    period="7d"
)

# Create order record
order = await analytics_service.create_order_analytics_record(
    business_id=123,
    order_data={
        "table_id": 5,
        "total_amount": 25.99,
        "status": "pending"
    }
)
```

## Monitoring & Maintenance

### Health Checks
- Regular analytics data validation
- Performance monitoring of queries
- Error rate tracking
- Data consistency checks

### Data Maintenance
- Automated cleanup of old analytics data
- Index optimization
- Query performance monitoring
- Backup and recovery procedures

This comprehensive analytics system provides everything needed for complete business intelligence and reporting in the X-SevenAI dashboard.
