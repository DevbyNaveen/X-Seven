# LangGraph Conversation Flow Engine Implementation

## Overview

This implementation adds a sophisticated conversation flow engine using LangGraph to the X-SevenAI backend. The system provides advanced conversation state management, complex conversation flows, and seamless integration with existing CrewAI agents.

## Features Implemented

### 1. Core Components

#### Conversation Flow Engine (`conversation_flow_engine.py`)
- **Advanced State Management**: Manages conversation states with LangGraph
- **Multi-Agent Routing**: Intelligent routing between CrewAI agents
- **Conversation Persistence**: Redis-based state persistence
- **Recovery Mechanisms**: Automatic conversation recovery on errors

#### Conversation State Management (`conversation_state.py`)
- **Graph-Based Structure**: Node and edge-based conversation modeling
- **State Tracking**: Comprehensive conversation state management
- **Transition Logic**: Conditional and dynamic state transitions
- **History Management**: Complete conversation history tracking

#### Redis Persistence (`redis_persistence.py`)
- **State Persistence**: Save/load conversation states to Redis
- **Checkpoint System**: Automatic checkpointing for recovery
- **Cleanup Management**: Automatic cleanup of old checkpoints
- **Health Monitoring**: Redis connection health checks

### 2. Advanced Conversation Structures

#### Complex Conversation Graphs (`complex_conversation_graphs.py`)
- **Branching Conversations**: Multiple conversation paths based on conditions
- **Dynamic Routing**: AI-powered conversation flow control
- **Hierarchical Flows**: Multi-level conversation structures
- **Template System**: Pre-built conversation templates

#### CrewAI Integration (`crewai_langgraph_integration.py`)
- **Agent Switching**: Seamless switching between specialized agents
- **Context Preservation**: Maintains context across agent switches
- **Enhanced Processing**: Advanced message processing with CrewAI agents
- **Fallback Handling**: Robust fallback mechanisms

### 3. Recovery and Resilience

#### Conversation Recovery (`conversation_recovery.py`)
- **Multiple Recovery Strategies**: Retry, checkpoint, fallback, restart
- **Error Handling**: Comprehensive error handling and logging
- **Manual Intervention**: Support for manual recovery when needed
- **Recovery Statistics**: Detailed recovery metrics and analytics

#### Resilience Management
- **System Health Monitoring**: Real-time system health checks
- **Load Management**: Conversation load balancing
- **Circuit Breaker**: Automatic system protection under load
- **Performance Metrics**: Comprehensive system performance tracking

### 4. API Integration

#### REST API Endpoints (`langgraph_conversation_api.py`)
- **Conversation Management**: Create, update, end conversations
- **Message Processing**: Send messages with intelligent routing
- **Agent Control**: Switch agents mid-conversation
- **System Monitoring**: Health checks and statistics
- **Recovery Control**: Manual recovery triggers

## API Endpoints

### Core Conversation Endpoints
- `POST /api/v1/conversations/create` - Create new conversation
- `POST /api/v1/conversations/{id}/message` - Send message
- `GET /api/v1/conversations/{id}/history` - Get conversation history
- `POST /api/v1/conversations/{id}/switch-agent` - Switch agents
- `POST /api/v1/conversations/{id}/end` - End conversation

### Recovery and Management
- `POST /api/v1/conversations/{id}/recover` - Trigger recovery
- `GET /api/v1/conversations/agents` - List available agents
- `GET /api/v1/conversations/health` - System health check
- `GET /api/v1/conversations/stats` - System statistics

## Available Agents

The system integrates with existing CrewAI agents:

1. **RestaurantFoodAgent** - Restaurant recommendations and food services
2. **BeautySalonAgent** - Beauty treatments and salon services
3. **AutomotiveAgent** - Vehicle maintenance and automotive services
4. **HealthMedicalAgent** - Healthcare information and medical services
5. **BusinessAnalyticsAgent** - Business metrics and performance analysis
6. **VoiceEnhancementAgent** - Voice interface optimization
7. **LocalServicesAgent** - Local business and community services
8. **GeneralPurposeAgent** - General inquiries and assistance

## Configuration

### Conversation Config
```python
conversation_config = ConversationConfig(
    max_turns=50,                    # Maximum conversation turns
    timeout_seconds=300,             # Conversation timeout
    enable_persistence=True,         # Enable Redis persistence
    enable_recovery=True,            # Enable recovery mechanisms
    fallback_agent="GeneralPurposeAgent"  # Default fallback agent
)
```

### Redis Configuration
```python
redis_manager = RedisPersistenceManager(
    host="localhost",
    port=6379,
    db=0,
    password=None
)
```

## Usage Examples

### Creating a Conversation
```python
# Create a restaurant booking conversation
conversation = await integrator.create_specialized_conversation(
    "restaurant",
    conversation_id="user123_restaurant_chat"
)
```

### Processing Messages
```python
# Send a message and get intelligent response
result = await integrator.process_message_with_agent(
    conversation_id="user123_restaurant_chat",
    message="I want to book a table for 4 at an Italian restaurant tonight",
    user_id="user123"
)
```

### Switching Agents
```python
# Switch to beauty specialist mid-conversation
await integrator.switch_agent(conversation_id, "BeautySalonAgent")
```

## Recovery Mechanisms

The system includes multiple recovery strategies:

1. **Retry Last Message**: Retry with fallback agent
2. **Checkpoint Recovery**: Restore from previous checkpoint
3. **Fallback to General**: Switch to general purpose agent
4. **Restart Conversation**: Create new conversation with same context
5. **Manual Intervention**: Flag for human support

## Monitoring and Analytics

### Health Monitoring
- Real-time system health checks
- Redis connection monitoring
- Conversation load tracking
- Circuit breaker status

### Performance Metrics
- Recovery success rates
- Agent usage statistics
- Conversation completion rates
- System response times

## Error Handling

The system provides comprehensive error handling:

- **Automatic Recovery**: Attempts multiple recovery strategies
- **Graceful Degradation**: Falls back to simpler agents when needed
- **Manual Override**: Allows human intervention when required
- **Detailed Logging**: Comprehensive error logging and tracking

## Installation and Setup

1. **Install Dependencies**:
   ```bash
   pip install langgraph langgraph-prebuilt asyncio-redis redis[hiredis]
   ```

2. **Configure Redis**:
   - Ensure Redis is running and accessible
   - Configure connection parameters in environment variables

3. **Initialize Components**:
   ```python
   from app.services.ai.conversation_flow_engine import ConversationFlowEngine
   from app.services.ai.crewai_langgraph_integration import CrewAILangGraphIntegrator

   engine = ConversationFlowEngine()
   integrator = CrewAILangGraphIntegrator()
   ```

4. **Start Using**:
   ```python
   conversation_id = await integrator.create_enhanced_conversation()
   result = await integrator.process_message_with_agent(conversation_id, "Hello!")
   ```

## Architecture Benefits

### Scalability
- Horizontal scaling with Redis clustering
- Load balancing across multiple conversation engines
- Efficient state management with checkpointing

### Reliability
- Multiple recovery strategies ensure conversation continuity
- Circuit breaker prevents system overload
- Comprehensive error handling and logging

### Flexibility
- Dynamic agent routing based on conversation context
- Configurable conversation flows and templates
- Extensible architecture for new agent types

### Performance
- Efficient state persistence with Redis
- Minimal memory footprint with checkpoint cleanup
- Fast agent switching and context preservation

## Future Enhancements

1. **Machine Learning Integration**: Intent classification and sentiment analysis
2. **Advanced Analytics**: Conversation pattern analysis and optimization
3. **Multi-language Support**: Internationalization of conversation flows
4. **Voice Integration**: Enhanced voice conversation capabilities
5. **Advanced Routing**: ML-powered dynamic conversation routing

This implementation provides a robust, scalable, and intelligent conversation management system that significantly enhances the X-SevenAI platform's capabilities.
