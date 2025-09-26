#!/bin/bash

# X-SevenAI Services Setup Script
# This script sets up all required services for proper initialization

set -e

echo "🚀 Setting up X-SevenAI services..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if port is available
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${YELLOW}Port $1 is already in use${NC}"
        return 1
    else
        echo -e "${GREEN}Port $1 is available${NC}"
        return 0
    fi
}

# Function to wait for service
wait_for_service() {
    local host=$1
    local port=$2
    local service_name=$3
    local max_attempts=30
    local attempt=1

    echo -e "${YELLOW}Waiting for $service_name to start...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        if nc -z $host $port 2>/dev/null; then
            echo -e "${GREEN}✅ $service_name is ready!${NC}"
            return 0
        fi
        echo -e "${YELLOW}Attempt $attempt/$max_attempts - waiting for $service_name...${NC}"
        sleep 2
        ((attempt++))
    done
    
    echo -e "${RED}❌ $service_name failed to start${NC}"
    return 1
}

# Create necessary directories
echo -e "${GREEN}📁 Creating necessary directories...${NC}"
mkdir -p logs services_data/redis services_data/temporal services_data/kafka services_data/zookeeper

# Check if Homebrew is available for macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    if ! command_exists brew; then
        echo -e "${YELLOW}Installing Homebrew...${NC}"
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
fi

# Install Redis
echo -e "${GREEN}🔧 Setting up Redis...${NC}"
if ! command_exists redis-server; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install redis
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt-get update && sudo apt-get install -y redis-server
    fi
fi

# Install Kafka dependencies
echo -e "${GREEN}🔧 Setting up Kafka...${NC}"
if [[ "$OSTYPE" == "darwin"* ]]; then
    if ! command_exists kafka-topics; then
        brew install kafka
    fi
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if ! command_exists kafka-topics; then
        wget https://downloads.apache.org/kafka/2.8.0/kafka_2.13-2.8.0.tgz
        tar -xzf kafka_2.13-2.8.0.tgz
        sudo mv kafka_2.13-2.8.0 /opt/kafka
        echo 'export PATH=$PATH:/opt/kafka/bin' >> ~/.bashrc
        source ~/.bashrc
    fi
fi

# Install Temporal CLI
echo -e "${GREEN}🔧 Setting up Temporal...${NC}"
if ! command_exists temporal; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install temporal
    else
        curl -sSf https://temporal.download/cli.sh | sh
    fi
fi

# Start Redis
echo -e "${GREEN}🚀 Starting Redis...${NC}"
if check_port 6379; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew services start redis
    else
        sudo systemctl start redis
    fi
    wait_for_service localhost 6379 "Redis"
fi

# Start Zookeeper
echo -e "${GREEN}🚀 Starting Zookeeper...${NC}"
if check_port 2181; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew services start zookeeper
    else
        zookeeper-server-start.sh -daemon /opt/kafka/config/zookeeper.properties
    fi
    wait_for_service localhost 2181 "Zookeeper"
fi

# Start Kafka
echo -e "${GREEN}🚀 Starting Kafka...${NC}"
if check_port 9092; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew services start kafka
    else
        kafka-server-start.sh -daemon /opt/kafka/config/server.properties
    fi
    wait_for_service localhost 9092 "Kafka"
fi

# Start Temporal
echo -e "${GREEN}🚀 Starting Temporal...${NC}"
if check_port 7233; then
    temporal server start-dev --port 7233 --ui-port 8233 --db-filename services_data/temporal/temporal.db &
    wait_for_service localhost 7233 "Temporal"
fi

# Create Kafka topics
echo -e "${GREEN}📋 Creating Kafka topics...${NC}"
sleep 10  # Wait for Kafka to be fully ready

# Create required topics
kafka_topics=("xseven-events" "xseven-commands" "xseven-responses")
for topic in "${kafka_topics[@]}"; do
    if command_exists kafka-topics; then
        kafka-topics --create --topic "$topic" --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1 2>/dev/null || true
    fi
done

# Install Python dependencies
echo -e "${GREEN}📦 Installing Python dependencies...${NC}"
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Verify services are running
echo -e "${GREEN}🔍 Verifying services...${NC}"
echo "Redis: $(redis-cli ping 2>/dev/null || echo 'FAILED')"
echo "Kafka: $(kafka-topics --list --bootstrap-server localhost:9092 2>/dev/null | head -5 || echo 'FAILED')"
echo "Temporal: $(curl -s http://localhost:8233/api/v1/namespaces 2>/dev/null | head -1 || echo 'FAILED')"

echo -e "${GREEN}✅ All services are set up and running!${NC}"
echo -e "${GREEN}🎉 You can now start your X-SevenAI application${NC}"
echo ""
echo "Service URLs:"
echo "- Redis: redis://localhost:6379"
echo "- Kafka: localhost:9092"
echo "- Temporal: localhost:7233"
echo "- Temporal UI: http://localhost:8233"
echo ""
echo "To stop services:"
echo "- ./stop_services.sh"
