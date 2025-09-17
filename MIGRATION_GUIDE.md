# Migration Guide: From Unified to Separate AI Services

## Overview
This guide provides a step-by-step process to migrate from the unified `UnifiedAIHandler` to three separate, independent AI services.

## ✅ Completed Steps

### 1. ✅ Core Architecture
- **Extracted shared AI logic** into reusable library (`app/core/ai/`)
- **Created three separate handlers**:
  - `GlobalAIHandler` - Business discovery service
  - `DedicatedAIHandler` - Business-specific chat service  
  - `DashboardAIHandler` - Business management service
- **Implemented standardized endpoints** with health checks
- **Added structured logging** and comprehensive test suite

### 2. ✅ Service Structure
```
app/
├── core/ai/                    # Shared AI library
│   ├── base_handler.py         # Base AI functionality
│   ├── context_builders.py     # Context-specific data loading
│   └── types.py               # Shared type definitions
├── services/ai/               # Individual service handlers
│   ├── global_ai_handler.py
│   ├── dedicated_ai_handler.py
│   └── dashboard_ai_handler.py
├── api/v1/endpoints/          # Service endpoints
│   ├── global_endpoints.py
│   ├── dedicated_endpoints.py
│   └── dashboard_endpoints.py
└── tests/                     # Comprehensive test suite
```

## 🔄 Migration Phases

### Phase 1: Gradual Transition (Current → Target)
**Duration**: 1-2 weeks
**Risk**: Low

1. **Deploy new endpoints alongside existing ones**:
   - New endpoints available at:
     - `/api/v1/global/` (replaces `/api/v1/central/global`)
     - `/api/v1/dedicated/{business_identifier}` (replaces `/api/v1/central/dedicated/{business_identifier}`)
     - `/api/v1/dashboard/` (replaces `/api/v1/central/dashboard`)

2. **Update frontend gradually**:
   - Update API calls in frontend to use new endpoints
   - Test each service independently
   - Monitor performance and errors

3. **Feature flags**:
   - Use feature flags to switch between old/new endpoints
   - Rollback capability if issues arise

### Phase 2: Full Cutover
**Duration**: 1 week
**Risk**: Medium

1. **Remove old unified handler**:
   - Delete `app/services/ai/unified_ai_handler.py`
   - Remove old central endpoints
   - Update main API router

2. **Update deployment**:
   - Each service can now be deployed independently
   - Consider containerizing each service

### Phase 3: Independent Deployment (Optional)
**Duration**: 2-3 weeks
**Risk**: Low (only if Phase 2 successful)

1. **Container separation**:
   ```yaml
   # docker-compose.yml
   version: '3.8'
   services:
     global-service:
       build: ./services/global
       ports: ["8001:8000"]
       environment: ["SERVICE_NAME=global"]
     
     dedicated-service:
       build: ./services/dedicated  
       ports: ["8002:8000"]
       environment: ["SERVICE_NAME=dedicated"]
     
     dashboard-service:
       build: ./services/dashboard
       ports: ["8003:8000"]
       environment: ["SERVICE_NAME=dashboard"]
   ```

2. **Load balancing**:
   - Use nginx or API gateway to route requests
   - Implement service discovery

## 🔧 Configuration Updates

### Environment Variables
```bash
# Service-specific logging
SERVICE_NAME=global  # or dedicated/dashboard
LOG_LEVEL=INFO

# Database connections (can be separate per service)
DATABASE_URL=postgresql://user:pass@localhost/xseven

# AI service configuration  
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

### Database Schema
No schema changes required - existing database structure supports all services.

## 🧪 Testing Strategy

### 1. Unit Tests
```bash
# Run tests for each service
pytest tests/test_global_ai_handler.py -v
pytest tests/test_dedicated_ai_handler.py -v  
pytest tests/test_dashboard_ai_handler.py -v
pytest tests/test_context_builders.py -v
```

### 2. Integration Tests
```bash
# Test each service endpoint
curl -X POST http://localhost:8000/api/v1/global/ \
  -H "Content-Type: application/json" \
  -d '{"message": "Show me restaurants", "session_id": "test"}'

curl -X POST http://localhost:8000/api/v1/dedicated/1 \
  -H "Content-Type: application/json" \
  -d '{"message": "What's on the menu?", "session_id": "test"}'

curl -X POST http://localhost:8000/api/v1/dashboard/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"message": "Show pending orders", "session_id": "test"}'
```

### 3. Health Checks
```bash
# Verify all services are healthy
curl http://localhost:8000/api/v1/global/health
curl http://localhost:8000/api/v1/dedicated/health  
curl http://localhost:8000/api/v1/dashboard/health
```

## 📊 Monitoring & Observability

### Structured Logging
Each service now includes:
- Service-specific loggers
- JSON-formatted logs
- Context tracking (session_id, business_id, etc.)
- Performance metrics

### Metrics to Monitor
- Response times per service
- Error rates per context type
- Database query performance
- AI API usage and costs

## 🚀 Deployment Checklist

### Pre-deployment
- [ ] All tests passing
- [ ] Health endpoints responding
- [ ] Feature flags configured
- [ ] Monitoring dashboards ready

### Deployment
- [ ] Deploy new endpoints alongside existing
- [ ] Update frontend API calls gradually
- [ ] Monitor error rates and performance
- [ ] Validate data consistency

### Post-deployment
- [ ] Remove old unified handler
- [ ] Update documentation
- [ ] Update CI/CD pipelines
- [ ] Conduct performance testing

## 🔙 Rollback Plan

If issues arise:
1. **Immediate**: Switch feature flags back to old endpoints
2. **Short-term**: Revert frontend changes
3. **Long-term**: Restore unified handler if needed

## 📈 Benefits After Migration

### ✅ Immediate Benefits
- **Isolation**: Service failures don't affect other contexts
- **Scalability**: Each service can scale independently
- **Security**: Better security boundaries
- **Maintainability**: Cleaner codebase with clear responsibilities

### ✅ Long-term Benefits
- **Independent deployments**: Deploy updates without affecting other services
- **Technology flexibility**: Use different tech stacks per service
- **Team autonomy**: Different teams can own different services
- **Cost optimization**: Scale only what you need

## 🎯 Next Steps

1. **Review and approve** this migration plan
2. **Set up monitoring** for new endpoints
3. **Begin Phase 1** gradual transition
4. **Schedule Phase 2** cutover date
5. **Plan Phase 3** containerization (if needed)

## 📞 Support

For questions or issues during migration:
- Check service health endpoints
- Review structured logs
- Run test suites
- Consult this guide
