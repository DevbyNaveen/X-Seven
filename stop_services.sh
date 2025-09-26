#!/bin/bash

# X-SevenAI Services Stop Script

set -e

echo "🛑 Stopping X-SevenAI services..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Stop Temporal
echo -e "${YELLOW}Stopping Temporal...${NC}"
pkill -f "temporal server start-dev" || true

# Stop Kafka
echo -e "${YELLOW}Stopping Kafka...${NC}"
if [[ "$OSTYPE" == "darwin"* ]]; then
    brew services stop kafka
else
    kafka-server-stop.sh || true
fi

# Stop Zookeeper
echo -e "${YELLOW}Stopping Zookeeper...${NC}"
if [[ "$OSTYPE" == "darwin"* ]]; then
    brew services stop zookeeper
else
    zookeeper-server-stop.sh || true
fi

# Stop Redis
echo -e "${YELLOW}Stopping Redis...${NC}"
if [[ "$OSTYPE" == "darwin"* ]]; then
    brew services stop redis
else
    sudo systemctl stop redis
fi

echo -e "${GREEN}✅ All services stopped${NC}"
