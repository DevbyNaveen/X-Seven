# X-SevenAI Cloud-Native Setup Guide

## Modern Solution Overview

Instead of running all services locally, we'll use managed cloud services for production-grade reliability and scalability.

## 1. Redis Cloud (Managed Redis)

### Option A: Redis Cloud (Free Tier)
1. Go to [Redis Cloud](https://redis.com/try-free/)
2. Create a free account
3. Create a new subscription (30MB free)
4. Get your Redis URL: `redis://default:password@host:port`

### Option B: Upstash (Serverless Redis)
1. Go to [Upstash](https://upstash.com)
2. Create a free Redis database
3. Copy the Redis URL

Update your `.env`:
```bash
REDIS_URL=redis://your-redis-url
```

## 2. Kafka Cloud (Managed Kafka)

### Option A: Confluent Cloud (Free Tier)
1. Go to [Confluent Cloud](https://confluent.cloud)
2. Create a free account ($400 credits)
3. Create a basic cluster
4. Create API keys and get bootstrap servers

Update your `.env`:
```bash
KAFKA_BOOTSTRAP_SERVERS=["your-cluster.kafka.confluent.cloud:9092"]
KAFKA_SECURITY_PROTOCOL=SASL_SSL
KAFKA_SASL_MECHANISM=PLAIN
KAFKA_SASL_USERNAME=your-api-key
KAFKA_SASL_PASSWORD=your-secret
```

### Option B: Upstash Kafka (Serverless)
1. Go to [Upstash Kafka](https://upstash.com/kafka)
2. Create a free Kafka cluster
3. Get connection details

## 3. Temporal Cloud (Managed Workflows)

### Option A: Temporal Cloud (Free Tier)
1. Go to [Temporal Cloud](https://temporal.io/cloud)
2. Create a free namespace
3. Get your Temporal endpoint and namespace

Update your `.env`:
```bash
TEMPORAL_HOST=your-namespace.tmprl.cloud:7233
TEMPORAL_NAMESPACE=your-namespace
TEMPORAL_TLS_CERT_PATH=/path/to/cert.pem
TEMPORAL_TLS_KEY_PATH=/path/to/key.pem
```

### Option B: Local Development (for testing)
We'll use Temporal's development server.

## 4. Quick Setup Script

Run this to set up cloud services:

```bash
# Install cloud CLI tools
npm install -g @confluentinc/cli
brew install temporal

# Login to services
confluent login
temporal login
```

## 5. Environment Configuration

Create `.env.cloud`:
```bash
# Redis Cloud
REDIS_URL=redis://your-redis-cloud-url

# Kafka Cloud
KAFKA_BOOTSTRAP_SERVERS=["your-kafka-broker:9092"]
KAFKA_SECURITY_PROTOCOL=SASL_SSL
KAFKA_SASL_MECHANISM=PLAIN
KAFKA_SASL_USERNAME=your-username
KAFKA_SASL_PASSWORD=your-password

# Temporal Cloud
TEMPORAL_HOST=your-namespace.tmprl.cloud:7233
TEMPORAL_NAMESPACE=your-namespace
TEMPORAL_TLS_CERT_PATH=./certs/client.pem
TEMPORAL_TLS_KEY_PATH=./certs/client.key

# PipeCat AI (already configured)
PIPECAT_API_KEY=your-pipecat-key
```

## 6. Docker Desktop Alternative

If you prefer local Docker:

```bash
# Install Docker Desktop
# https://www.docker.com/products/docker-desktop/

# Start services
docker compose up -d redis kafka temporal
```

## 7. Verification Commands

```bash
# Test Redis
redis-cli -u $REDIS_URL ping

# Test Kafka
kcat -b $KAFKA_BOOTSTRAP_SERVERS -L

# Test Temporal
temporal workflow list
```

## 8. Production Deployment

For production, use:
- **Redis**: Redis Cloud or AWS ElastiCache
- **Kafka**: Confluent Cloud or AWS MSK
- **Temporal**: Temporal Cloud or self-hosted on Kubernetes

## 9. Quick Start Commands

```bash
# Use cloud services
source .env.cloud

# Start application
source .venv/bin/activate
python -m app.main
```

## 10. Monitoring & Observability

- **Redis**: Use Redis Cloud dashboard
- **Kafka**: Use Confluent Cloud monitoring
- **Temporal**: Use Temporal Web UI

## Troubleshooting

### Service Connection Issues
1. Check firewall settings
2. Verify network connectivity
3. Check service credentials

### Performance Issues
1. Scale cloud resources
2. Use connection pooling
3. Implement caching strategies

## Support

For issues with cloud services:
- Redis Cloud: Check Redis Cloud documentation
- Confluent Cloud: Check Confluent documentation
- Temporal Cloud: Check Temporal documentation
