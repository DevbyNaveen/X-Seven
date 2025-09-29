# 🚀 Service Mesh Migration Guide

## Overview
This guide helps migrate from the legacy service initialization to the modern service mesh architecture with dependency management, circuit breakers, and health monitoring.

## 🎯 What's New

### ✅ Modern Features
- **Service Registry**: Centralized service discovery
- **Circuit Breakers**: Fault tolerance for external dependencies
- **Health Monitoring**: Real-time service health checks
- **Dependency Injection**: Clean service lifecycle management
- **Configuration Hot-Reload**: No restart required for config changes
- **Graceful Degradation**: Services continue operating when dependencies fail

### 🔄 Backward Compatibility
- Legacy services still work alongside service mesh
- Automatic fallback to legacy initialization
- Gradual migration path

## 📋 Migration Steps

### 1. Install New Dependencies
```bash
pip install -r requirements/service_mesh.txt
```

### 2. Configuration Setup
```bash
# Copy and customize the configuration
cp config/service_mesh.yml.example config/service_mesh.yml

# Set environment variables
export DATABASE_HOST=localhost
export REDIS_HOST=localhost
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
export TEMPORAL_HOST=localhost
```

### 3. Environment Variables
The service mesh uses environment variables for configuration:

```bash
# Database
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=xseven
DATABASE_USERNAME=postgres
DATABASE_PASSWORD=your_password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_password

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Temporal
TEMPORAL_HOST=localhost
TEMPORAL_PORT=7233

# DSPy
DSPY_MODEL=gpt-4o-mini
DSPY_TRAINING_DATA_PATH=/path/to/training/data

# Voice Services
VOICE_PROVIDER=openai
VOICE_TTS_PROVIDER=elevenlabs
VOICE_VOICE_ID=your_voice_id
```

### 4. Service Health Endpoints

#### Check System Health
```bash
curl http://localhost:8000/health/system
```

#### Check Individual Service Health
```bash
curl http://localhost:8000/health/service/database
curl http://localhost:8000/health/service/redis
curl http://localhost:8000/health/service/kafka
curl http://localhost:8000/health/service/temporal
```

### 5. Service Monitoring

#### Real-time Health Monitoring
```python
from app.core.service_mesh.health import get_health_checker

health_checker = get_health_checker()
status = await health_checker.get_system_health()
```

#### Circuit Breaker Status
```python
from app.core.service_mesh.circuit_breaker import get_circuit_manager

manager = get_circuit_manager()
status = manager.get_system_health()
```

## 🔧 Service Registration

### Registering New Services
```python
from app.core.service_mesh.orchestrator import get_startup_orchestrator

orchestrator = get_startup_orchestrator()

# Register a service with dependencies
orchestrator.register_service(
    name="my_service",
    service_class=MyService,
    dependencies=["database", "redis"],
    health_check=my_health_check_function,
    lifecycle=ServiceLifecycle.SINGLETON,
    required=True
)
```

### Custom Health Checks
```python
async def my_service_health_check() -> bool:
    try:
        # Your health check logic here
        return True
    except Exception:
        return False

# Register the health check
from app.core.service_mesh.health import get_health_checker
health_checker = get_health_checker()
health_checker.register_check("my_service", my_service_health_check)
```

## 📊 Monitoring and Debugging

### Service Status Dashboard
```python
from app.core.service_mesh.integrations import get_service_mesh

service_mesh = await get_service_mesh()
status = await service_mesh.get_status()
print(json.dumps(status, indent=2))
```

### Circuit Breaker Metrics
```python
from app.core.service_mesh.circuit_breaker import get_circuit_manager

manager = get_circuit_manager()
for name, breaker in manager.get_all_breakers().items():
    print(f"{name}: {breaker.get_metrics()}")
```

## 🚨 Troubleshooting

### Common Issues

#### Service Not Starting
1. Check configuration validation:
```python
from app.core.service_mesh.config import get_config_manager
errors = get_config_manager().validate_config()
```

2. Check service dependencies:
```python
from app.core.service_mesh.orchestrator import get_startup_orchestrator
orchestrator = get_startup_orchestrator()
status = orchestrator.get_system_status()
```

#### Circuit Breaker Open
- Check service health endpoints
- Review circuit breaker metrics
- Verify network connectivity

#### Configuration Issues
- Validate environment variables
- Check file permissions for config files
- Review configuration syntax

### Debug Mode
Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
python -m app.main
```

## 🔄 Rollback Plan

If you need to rollback to legacy initialization:

1. Set environment variable:
```bash
export USE_LEGACY_STARTUP=true
```

2. The system will automatically fallback to legacy startup

3. Monitor logs for fallback messages

## 📈 Performance Benefits

### ✅ Improved Reliability
- Circuit breakers prevent cascade failures
- Health checks ensure only healthy services receive traffic
- Graceful degradation when services fail

### ⚡ Faster Startup
- Parallel service initialization
- Dependency-aware startup ordering
- Optimized resource allocation

### 🔍 Better Observability
- Real-time health monitoring
- Detailed service metrics
- Centralized logging

## 🧪 Testing

### Integration Tests
```bash
# Run service mesh tests
python -m pytest tests/test_service_mesh.py -v

# Run health check tests
python -m pytest tests/test_health_checks.py -v

# Run circuit breaker tests
python -m pytest tests/test_circuit_breakers.py -v
```

### Load Testing
```bash
# Test service resilience under load
locust -f tests/load_test_service_mesh.py --host=http://localhost:8000
```

## 📚 API Reference

### Service Mesh Endpoints
- `GET /health/system` - Overall system health
- `GET /health/service/{name}` - Specific service health
- `GET /health/circuit-breakers` - Circuit breaker status
- `POST /admin/restart-service/{name}` - Restart specific service

### Configuration Updates
```bash
# Update configuration at runtime
curl -X POST http://localhost:8000/admin/config \
  -H "Content-Type: application/json" \
  -d '{"redis": {"host": "new-redis-host"}}'
```

## 🎉 Migration Complete!

Your X-Seven AI framework now uses modern service mesh architecture with:
- ✅ Circuit breakers for fault tolerance
- ✅ Health monitoring for all services
- ✅ Dependency injection for clean architecture
- ✅ Configuration hot-reload
- ✅ Graceful degradation
- ✅ Comprehensive observability

The system is now production-ready with enterprise-grade reliability and monitoring capabilities.
