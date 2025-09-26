# X-SevenAI Complete Startup Guide

## 🚀 Quick Start (5 minutes)

### Option 1: Cloud-Native Setup (Recommended)
```bash
# Use managed cloud services - no local setup needed
source .venv/bin/activate
python modern_setup.py cloud
# Follow prompts to set up cloud services
```

### Option 2: Local Development Setup
```bash
# Install and start all services locally
source .venv/bin/activate
python modern_setup.py local
# This will install Redis, Kafka, and Temporal
```

### Option 3: Docker Setup (If Docker is available)
```bash
# Start all services with Docker
docker compose up -d redis kafka temporal
```

## 📋 Complete Setup Steps

### 1. Environment Setup
```bash
# Activate virtual environment
source .venv/bin/activate

# Verify setup
python verify_setup.py
```

### 2. Service Configuration

#### Redis Setup (Choose one):

**Cloud Redis (Upstash - Free)**
1. Go to [upstash.com](https://upstash.com)
2. Create Redis database
3. Update `.env`:
```bash
REDIS_URL=redis://default:password@host:port
```

**Local Redis**
```bash
# macOS
brew install redis
brew services start redis

# Ubuntu
sudo apt install redis-server
sudo systemctl start redis
```

#### Kafka Setup (Choose one):

**Cloud Kafka (Confluent - Free Tier)**
1. Go to [confluent.cloud](https://confluent.cloud)
2. Create cluster
3. Update `.env`:
```bash
KAFKA_BOOTSTRAP_SERVERS=["your-cluster.kafka.confluent.cloud:9092"]
KAFKA_SECURITY_PROTOCOL=SASL_SSL
KAFKA_SASL_MECHANISM=PLAIN
KAFKA_SASL_USERNAME=your-key
KAFKA_SASL_PASSWORD=your-secret
```

**Local Kafka**
```bash
# macOS
brew install kafka
brew services start zookeeper
brew services start kafka

# Create topics
kafka-topics --create --topic xseven-events --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
```

#### Temporal Setup (Choose one):

**Cloud Temporal (Free Tier)**
1. Go to [temporal.io/cloud](https://temporal.io/cloud)
2. Create namespace
3. Update `.env`:
```bash
TEMPORAL_HOST=your-namespace.tmprl.cloud:7233
TEMPORAL_NAMESPACE=your-namespace
```

**Local Temporal**
```bash
# macOS
brew install temporal
temporal server start-dev --port 7233 --ui-port 8233

# Access UI at http://localhost:8233
```

### 3. Verify All Services
```bash
python verify_setup.py
```

Expected output:
```
✅ Redis: Redis is ready
✅ Kafka: Kafka is ready
✅ Temporal: Temporal is ready
✅ Pipecat: PipeCat AI ready
✅ All dependencies installed
✅ All environment variables set
```

### 4. Start Application
```bash
# Start the main application
source .venv/bin/activate
python -m app.main
```

## 🔧 Troubleshooting

### Common Issues and Solutions

#### 1. Port Already in Use
```bash
# Check what's using ports
lsof -i :6379  # Redis
lsof -i :9092  # Kafka
lsof -i :7233  # Temporal

# Kill processes if needed
kill -9 <PID>
```

#### 2. Service Connection Issues
```bash
# Test Redis
redis-cli ping

# Test Kafka
kcat -b localhost:9092 -L

# Test Temporal
curl http://localhost:8233/api/v1/namespaces
```

#### 3. Missing Dependencies
```bash
# Reinstall all dependencies
source .venv/bin/activate
pip install -r requirements.txt --force-reinstall
```

#### 4. Environment Variables
```bash
# Check .env file
cat .env

# Ensure all required variables are set
python -c "from app.config.settings import settings; print(settings.model_dump())"
```

## 🌐 Service URLs

When running locally:
- **Application**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Redis**: redis://localhost:6379
- **Kafka**: localhost:9092
- **Temporal UI**: http://localhost:8233
- **Temporal API**: localhost:7233

## 📊 Monitoring

### Service Health Checks
```bash
# Check all services
python verify_setup.py

# Monitor logs
tail -f logs/app.log

# Check Redis
redis-cli info

# Check Kafka topics
kafka-topics --list --bootstrap-server localhost:9092
```

## 🔄 Restarting Services

### Stop All Services
```bash
# Local services
./stop_services.sh

# Docker services
docker compose down
```

### Start All Services
```bash
# Local services
./setup_services.sh

# Docker services
docker compose up -d
```

## 🚀 Production Deployment

### Cloud Services (Recommended)
1. **Redis**: AWS ElastiCache / Redis Cloud
2. **Kafka**: Confluent Cloud / AWS MSK
3. **Temporal**: Temporal Cloud / Kubernetes
4. **Database**: Supabase (already configured)

### Environment Variables for Production
```bash
# Copy cloud config
cp .env.cloud .env

# Edit with your actual cloud service URLs
nano .env
```

## 📞 Support

If you encounter issues:
1. Run `python verify_setup.py` to diagnose
2. Check logs in `logs/` directory
3. Ensure all services are running
4. Verify environment variables
5. Check network connectivity

## ✅ Success Checklist

- [ ] Virtual environment activated
- [ ] All Python dependencies installed
- [ ] Redis accessible
- [ ] Kafka accessible
- [ ] Temporal accessible
- [ ] Environment variables configured
- [ ] Application starts without errors
- [ ] API documentation loads at /docs
- [ ] All services show "✅" in verify script
