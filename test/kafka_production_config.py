"""
Production Kafka Configuration Guide
This file contains production-ready Kafka configuration settings
"""

# Production Kafka Configuration
KAFKA_PRODUCTION_CONFIG = {
    # Kafka Cluster Settings
    "bootstrap_servers": [
        "kafka-1.production.local:9092",
        "kafka-2.production.local:9092",
        "kafka-3.production.local:9092"
    ],
    
    # Security Settings
    "security_protocol": "SASL_SSL",
    "sasl_mechanism": "SCRAM-SHA-512",
    "sasl_username": "your_production_username",
    "sasl_password": "your_production_password",
    
    # SSL Configuration
    "ssl_cafile": "/etc/ssl/certs/ca-certificates.crt",
    "ssl_certfile": "/etc/ssl/certs/client.pem",
    "ssl_keyfile": "/etc/ssl/private/client.key",
    
    # Producer Settings
    "producer": {
        "acks": "all",  # Wait for all replicas
        "max_batch_size": 32768,  # Larger batch size for production
        "linger_ms": 100,  # Allow more batching
        "compression_type": "snappy",  # Fast compression
        "max_request_size": 1048576,  # 1MB max message size
        "enable_idempotence": True,  # Exactly-once semantics
        "request_timeout_ms": 30000,
        "delivery_timeout_ms": 120000,
        "retries": 5,
        "retry_backoff_ms": 100,
    },
    
    # Consumer Settings
    "consumer": {
        "group_id": "xseven-ai-production",
        "auto_offset_reset": "earliest",
        "enable_auto_commit": False,  # Manual commit for reliability
        "max_poll_records": 500,
        "session_timeout_ms": 30000,
        "heartbeat_interval_ms": 3000,
        "max_partition_fetch_bytes": 1048576,
        "isolation_level": "read_committed",
    },
    
    # Topic Configuration
    "topics": {
        "conversation.events": {
            "partitions": 6,  # More partitions for scalability
            "replication_factor": 3,  # High availability
            "config": {
                "cleanup.policy": "compact",
                "retention.ms": 604800000,  # 7 days
                "segment.ms": 3600000,  # 1 hour segments
                "compression.type": "snappy",
            }
        },
        "ai.responses": {
            "partitions": 12,
            "replication_factor": 3,
            "config": {
                "cleanup.policy": "delete",
                "retention.ms": 259200000,  # 3 days
                "segment.ms": 3600000,
                "compression.type": "snappy",
            }
        },
        "business.analytics": {
            "partitions": 3,
            "replication_factor": 3,
            "config": {
                "cleanup.policy": "compact",
                "retention.ms": 2592000000,  # 30 days
                "segment.ms": 86400000,  # 1 day segments
                "compression.type": "snappy",
            }
        },
        "system.monitoring": {
            "partitions": 1,
            "replication_factor": 3,
            "config": {
                "cleanup.policy": "delete",
                "retention.ms": 86400000,  # 1 day
                "segment.ms": 3600000,
                "compression.type": "snappy",
            }
        },
        "dead.letter.queue": {
            "partitions": 3,
            "replication_factor": 3,
            "config": {
                "cleanup.policy": "delete",
                "retention.ms": 604800000,  # 7 days
                "segment.ms": 3600000,
                "compression.type": "snappy",
            }
        }
    },
    
    # Monitoring Configuration
    "monitoring": {
        "metrics_interval": 30,  # seconds
        "health_check_interval": 60,  # seconds
        "alert_on_consumer_lag": 1000,  # messages
        "alert_on_producer_errors": 5,  # errors per minute
    },
    
    # Performance Tuning
    "performance": {
        "buffer_memory": 67108864,  # 64MB buffer
        "batch_size": 32768,  # 32KB batches
        "linger_ms": 100,  # 100ms linger
        "fetch_min_bytes": 1,
        "fetch_max_wait_ms": 500,
    }
}

# Local Development Configuration
KAFKA_LOCAL_CONFIG = {
    "bootstrap_servers": ["localhost:9092"],
    "security_protocol": "PLAINTEXT",
    "producer": {
        "acks": "all",
        "max_batch_size": 16384,
        "linger_ms": 10,
        "compression_type": "gzip",
        "max_request_size": 1048576,
        "enable_idempotence": True,
    },
    "consumer": {
        "group_id": "xseven-ai-development",
        "auto_offset_reset": "earliest",
        "enable_auto_commit": False,
        "max_poll_records": 500,
        "session_timeout_ms": 30000,
        "heartbeat_interval_ms": 3000,
    },
    "topics": {
        "conversation.events": {
            "partitions": 3,
            "replication_factor": 1,
            "config": {
                "cleanup.policy": "compact",
                "retention.ms": 604800000,
            }
        },
        "ai.responses": {
            "partitions": 6,
            "replication_factor": 1,
            "config": {
                "cleanup.policy": "delete",
                "retention.ms": 259200000,
            }
        },
        "business.analytics": {
            "partitions": 2,
            "replication_factor": 1,
            "config": {
                "cleanup.policy": "compact",
                "retention.ms": 2592000000,
            }
        },
        "system.monitoring": {
            "partitions": 1,
            "replication_factor": 1,
            "config": {
                "cleanup.policy": "delete",
                "retention.ms": 86400000,
            }
        },
        "dead.letter.queue": {
            "partitions": 1,
            "replication_factor": 1,
            "config": {
                "cleanup.policy": "delete",
                "retention.ms": 604800000,
            }
        }
    }
}

# Cloud Configuration Examples
KAFKA_CLOUD_CONFIGS = {
    "confluent": {
        "bootstrap_servers": ["your-cluster.kafka.confluent.cloud:9092"],
        "security_protocol": "SASL_SSL",
        "sasl_mechanism": "PLAIN",
        "sasl_username": "your-api-key",
        "sasl_password": "your-api-secret",
    },
    "aws_msk": {
        "bootstrap_servers": [
            "b-1.xseven-cluster.abc123.c2.kafka.us-east-1.amazonaws.com:9092",
            "b-2.xseven-cluster.abc123.c2.kafka.us-east-1.amazonaws.com:9092",
            "b-3.xseven-cluster.abc123.c2.kafka.us-east-1.amazonaws.com:9092"
        ],
        "security_protocol": "SASL_SSL",
        "sasl_mechanism": "SCRAM-SHA-512",
        "sasl_username": "your-username",
        "sasl_password": "your-password",
    },
    "azure_event_hubs": {
        "bootstrap_servers": ["your-namespace.servicebus.windows.net:9093"],
        "security_protocol": "SASL_SSL",
        "sasl_mechanism": "PLAIN",
        "sasl_username": "$ConnectionString",
        "sasl_password": "Endpoint=sb://your-namespace.servicebus.windows.net/;SharedAccessKeyName=your-key-name;SharedAccessKey=your-key",
    }
}

def get_kafka_config(environment="local"):
    """Get appropriate Kafka configuration based on environment"""
    configs = {
        "local": KAFKA_LOCAL_CONFIG,
        "development": KAFKA_LOCAL_CONFIG,
        "staging": KAFKA_PRODUCTION_CONFIG,
        "production": KAFKA_PRODUCTION_CONFIG,
    }
    return configs.get(environment, KAFKA_LOCAL_CONFIG)

if __name__ == "__main__":
    import os
    
    # Print current configuration
    env = os.getenv("ENVIRONMENT", "local")
    config = get_kafka_config(env)
    
    print(f"🚀 Kafka Configuration for {env.upper()} environment:")
    print(json.dumps(config, indent=2, default=str))
