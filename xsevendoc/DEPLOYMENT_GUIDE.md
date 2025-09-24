# 🚀 X-SevenAI Enhanced Framework Deployment Guide

## Quick Start

### 1. **Install Dependencies**
```bash
pip install -r requirements.txt
```

### 2. **Environment Setup**
Create/update your `.env` file:
```env
# Existing configuration
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
GROQ_API_KEY=your_groq_api_key

# Enhanced Framework Configuration
REDIS_URL=redis://localhost:6379
TEMPORAL_HOST=localhost:7233

# Optional Enhanced Settings
LOG_LEVEL=INFO
STRUCTURED_LOGGING=true
CREWAI_VERBOSE=false
CREWAI_MEMORY=true
```

### 3. **Infrastructure Setup**

#### **Redis Setup**
```bash
# Using Docker
docker run -d --name redis -p 6379:6379 redis:latest

# Or using local installation
brew install redis  # macOS
sudo apt-get install redis-server  # Ubuntu
```

#### **Temporal Setup**
```bash
# Using Docker
docker run -d --name temporal -p 7233:7233 temporalio/auto-setup:latest

# Or download Temporal CLI
curl -sSf https://temporal.download/cli.sh | sh
temporal server start-dev
```

### 4. **Start the Application**
```bash
# Development
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## 🧪 **Testing the Enhanced Framework**

### **Health Check**
```bash
curl http://localhost:8000/health
```

### **System Statistics**
```bash
curl http://localhost:8000/api/v1/conversations/stats
```

### **Test Dedicated Chat**
```bash
curl -X POST "http://localhost:8000/api/v1/conversations/chat/dedicated" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Book a table for 4 people",
    "business_id": "test-restaurant",
    "user_id": "user-123"
  }'
```

### **Test Dashboard Chat**
```bash
curl -X POST "http://localhost:8000/api/v1/conversations/chat/dashboard" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me today'\''s bookings",
    "business_id": "test-restaurant",
    "user_id": "admin-123",
    "user_role": "owner"
  }'
```

### **Test Global Chat**
```bash
curl -X POST "http://localhost:8000/api/v1/conversations/chat/global" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Find the best restaurants near me",
    "user_id": "user-123"
  }'
```

## 🔧 **Configuration Options**

### **Redis Configuration**
- `REDIS_URL`: Redis connection string
- Default TTL: Conversations (1h), Workflows (24h), Cache (15min)

### **Temporal Configuration**
- `TEMPORAL_HOST`: Temporal server address
- Task queue: `x-seven-ai-workflows`

### **LangGraph Configuration**
- Max turns: 50 per conversation
- Timeout: 300 seconds
- Persistence: Enabled by default

### **CrewAI Configuration**
- `CREWAI_VERBOSE`: Enable detailed logging
- `CREWAI_MEMORY`: Enable agent memory

## 📊 **Monitoring & Observability**

### **Key Endpoints**
- `/health` - Basic health check
- `/api/v1/conversations/health` - Detailed system health
- `/api/v1/conversations/stats` - System statistics
- `/api/v1/conversations/workflows/active` - Active workflows

### **Metrics to Monitor**
- Conversation success rate
- Average response time
- Active workflow count
- Redis memory usage
- Error recovery attempts

## 🚨 **Troubleshooting**

### **Common Issues**

#### **Redis Connection Failed**
```bash
# Check Redis status
redis-cli ping

# Restart Redis
docker restart redis
```

#### **Temporal Connection Failed**
```bash
# Check Temporal status
temporal workflow list

# Restart Temporal
docker restart temporal
```

#### **Import Errors**
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### **Debug Mode**
Set environment variables:
```env
LOG_LEVEL=DEBUG
CREWAI_VERBOSE=true
```

## 🔄 **Migration from Previous Version**

### **Automatic Migration**
- Existing conversations continue to work
- New features available immediately
- No data loss or downtime

### **Manual Steps**
1. Update environment variables
2. Install new dependencies
3. Start Redis and Temporal services
4. Restart application

## 🎯 **Production Deployment**

### **Docker Compose Example**
```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379
      - TEMPORAL_HOST=temporal:7233
    depends_on:
      - redis
      - temporal

  redis:
    image: redis:latest
    ports:
      - "6379:6379"

  temporal:
    image: temporalio/auto-setup:latest
    ports:
      - "7233:7233"
```

### **Kubernetes Deployment**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: x-seven-ai
spec:
  replicas: 3
  selector:
    matchLabels:
      app: x-seven-ai
  template:
    metadata:
      labels:
        app: x-seven-ai
    spec:
      containers:
      - name: app
        image: x-seven-ai:latest
        ports:
        - containerPort: 8000
        env:
        - name: REDIS_URL
          value: "redis://redis-service:6379"
        - name: TEMPORAL_HOST
          value: "temporal-service:7233"
```

## 📈 **Performance Optimization**

### **Recommended Settings**
```env
# Redis
REDIS_MAX_CONNECTIONS=20

# Temporal
TEMPORAL_MAX_WORKERS=10

# FastAPI
WORKERS=4
MAX_REQUESTS=1000
```

### **Scaling Guidelines**
- **Small deployment:** 1-2 workers, basic Redis/Temporal
- **Medium deployment:** 4-8 workers, Redis cluster, Temporal cluster
- **Large deployment:** 10+ workers, Redis Cluster, Temporal Cloud

## 🛡️ **Security Considerations**

### **Environment Variables**
- Never commit `.env` files
- Use secrets management in production
- Rotate API keys regularly

### **Network Security**
- Use TLS for all connections
- Implement rate limiting
- Configure firewall rules

### **Data Protection**
- Enable Redis AUTH
- Use encrypted connections
- Implement data retention policies

## 📞 **Support**

### **Logs Location**
- Application logs: `logs/app.log`
- Error logs: `logs/error.log`
- Access logs: `logs/access.log`

### **Debug Information**
```bash
# Get system status
curl http://localhost:8000/api/v1/conversations/health

# Get detailed stats
curl http://localhost:8000/api/v1/conversations/stats

# Check active workflows
curl http://localhost:8000/api/v1/conversations/workflows/active
```

---

**Your enhanced X-SevenAI framework is now ready for deployment! 🚀**
