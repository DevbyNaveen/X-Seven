# 🚀 DSPy Integration Guide for X-SevenAI

## Overview

This guide documents the complete DSPy integration into the X-SevenAI backend, transforming it from basic prompt engineering to a sophisticated, optimizable AI system.

## What is DSPy?

DSPy (Declarative Self-improving Python) is a framework for programming—rather than prompting—language models. It allows you to:

- **Program with modules** instead of crafting prompts
- **Automatically optimize** prompts and model weights
- **Systematically improve** AI system performance
- **Compose complex pipelines** with confidence scoring

## Integration Architecture

```
┌─────────────────────────────────────┐
│         FastAPI Application        │
│  /api/v1/conversations/dspy/*      │
└─────────────────────────────────────┘
                │
┌─────────────────────────────────────┐
│      DSPy Integration Layer         │
│  - Enhanced AI Handler             │
│  - DSPy Conversation Engine        │
│  - Optimization Pipeline           │
└─────────────────────────────────────┘
                │
┌─────────────────────────────────────┐
│         DSPy Core Modules          │
│  - Intent Detection               │
│  - Agent Routing                  │
│  - Response Generation            │
│  - Conversation Summary           │
└─────────────────────────────────────┘
                │
┌─────────────────────────────────────┐
│      Optimization System           │
│  - Training Data Manager          │
│  - MIPROv2 Optimizer              │
│  - Performance Metrics            │
└─────────────────────────────────────┘
```

## Key Components

### 1. DSPy Configuration (`app/core/dspy/config.py`)
- **DSPyManager**: Handles LLM configuration and initialization
- **Multi-provider support**: OpenAI, Groq, Anthropic
- **Fallback mechanisms**: Automatic provider switching
- **Caching**: Optimized for performance

### 2. Core DSPy Modules (`app/core/dspy/base_modules.py`)
- **IntentDetectionModule**: Classifies user intents with confidence
- **AgentRoutingModule**: Routes to appropriate agents
- **ResponseGenerationModule**: Generates contextual responses
- **ConversationSummaryModule**: Summarizes conversations
- **BusinessSpecificIntentModule**: Category-optimized intent detection

### 3. Enhanced Conversation Engine (`app/core/dspy/enhanced_conversation_engine.py`)
- **DSPy-powered LangGraph**: Integrates DSPy with existing conversation flows
- **State management**: Enhanced with DSPy predictions and confidence scores
- **Error recovery**: DSPy-enhanced fallback mechanisms
- **Optimization support**: Built-in module optimization

### 4. Optimization Pipeline (`app/core/dspy/optimizers.py`)
- **MIPROv2**: Multi-step instruction proposal and refinement
- **BootstrapFewShot**: Few-shot example generation
- **Training data management**: Synthetic and real data handling
- **Performance tracking**: Comprehensive metrics collection

### 5. Training Data System (`app/core/dspy/training_data.py`)
- **Synthetic data generation**: Creates training examples automatically
- **Real data collection**: Integrates with conversation history
- **Data validation**: Ensures quality training data
- **Statistics tracking**: Monitors data quality and quantity

## API Endpoints

### Core Conversation Endpoints

#### Enhanced Message Processing
```http
POST /api/v1/conversations/{conversation_id}/message/dspy
```
**Request:**
```json
{
  "message": "I'd like to book a table for 4 people tonight",
  "user_id": "user123",
  "use_dspy": true
}
```

**Response:**
```json
{
  "conversation_id": "conv_123",
  "response": "I'd be happy to help you make a reservation...",
  "agent_used": "DSPy-Enhanced",
  "turn_count": 1,
  "status": "processed",
  "dspy_metadata": {
    "intent": {
      "intent": "booking",
      "confidence": 0.92,
      "reasoning": "Clear booking request with specific details"
    },
    "response_confidence": 0.88,
    "optimization_used": true
  }
}
```

### DSPy Management Endpoints

#### System Status
```http
GET /api/v1/conversations/dspy/status
```

#### Trigger Optimization
```http
POST /api/v1/conversations/dspy/optimize
```

#### Test Modules
```http
POST /api/v1/conversations/dspy/test
```

### Dedicated DSPy API

#### Enhanced Chat Processing
```http
POST /api/v1/dspy/chat
```

#### Module Optimization
```http
POST /api/v1/dspy/optimize
```

#### Training Data Management
```http
POST /api/v1/dspy/training-data
GET /api/v1/dspy/training-data/{data_type}
```

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# DSPy Configuration
DSPY_PRIMARY_MODEL=openai/gpt-4o-mini
DSPY_FALLBACK_MODEL=groq/llama-3.3-70b-versatile
DSPY_OPTIMIZATION_MODEL=openai/gpt-4o-mini
DSPY_MAX_TOKENS=2000
DSPY_TEMPERATURE=0.7
DSPY_ENABLE_CACHING=true
DSPY_CACHE_DIR=.dspy_cache
DSPY_OPTIMIZATION_BUDGET=10.0
DSPY_MAX_OPTIMIZATION_EXAMPLES=100

# Required API Keys (at least one)
OPENAI_API_KEY=your_openai_key
GROQ_API_KEY=your_groq_key
ANTHROPIC_API_KEY=your_anthropic_key
```

### Dependencies

The integration adds these key dependencies to `requirements.txt`:

```txt
# DSPy Framework for Prompt Engineering & Optimization
dspy-ai>=2.4.0
datasets>=2.14.0  # For training data management
evaluate>=0.4.0   # For metrics and evaluation
```

## Usage Examples

### 1. Basic DSPy-Enhanced Chat

```python
from app.core.ai.dspy_enhanced_handler import DSPyEnhancedAIHandler
from app.core.ai.types import ChatContext

handler = DSPyEnhancedAIHandler()

result = await handler.process_message_with_dspy(
    message="I need to book a haircut appointment",
    session_id="session_123",
    business_id=1,
    chat_context=ChatContext.DEDICATED
)

print(f"Response: {result['message']}")
print(f"Intent: {result['dspy_metadata']['intent']['intent']}")
print(f"Confidence: {result['dspy_metadata']['intent']['confidence']}")
```

### 2. Direct Module Usage

```python
from app.core.dspy.base_modules import IntentDetectionModule

intent_module = IntentDetectionModule()
result = intent_module.forward(
    message="I want to make a reservation",
    conversation_history="",
    business_context="Italian restaurant"
)

print(f"Intent: {result.intent}")
print(f"Confidence: {result.confidence}")
print(f"Reasoning: {result.reasoning}")
```

### 3. Conversation Engine

```python
from app.core.dspy.enhanced_conversation_engine import DSPyEnhancedConversationEngine

engine = DSPyEnhancedConversationEngine()

# Create conversation
conversation_id = await engine.create_conversation(
    conversation_type="dedicated",
    initial_context={"business_category": "food_hospitality"}
)

# Process message
result = await engine.process_message(
    conversation_id=conversation_id,
    message="Book a table for tonight"
)

print(f"DSPy predictions: {result.dspy_predictions}")
print(f"Confidence scores: {result.confidence_scores}")
```

### 4. Optimization

```python
from app.core.dspy.enhanced_conversation_engine import DSPyEnhancedConversationEngine

engine = DSPyEnhancedConversationEngine()

# Trigger optimization
result = await engine.optimize_modules(force_optimization=True)

if result["success"]:
    print("Optimization completed successfully!")
    print(f"Stats: {result['stats']}")
else:
    print(f"Optimization failed: {result['error']}")
```

## Performance Benefits

### Before DSPy Integration
- **Static prompts**: Hardcoded, difficult to maintain
- **No optimization**: Manual prompt tuning
- **Inconsistent quality**: Variable response quality
- **Limited metrics**: Basic success/failure tracking

### After DSPy Integration
- **Dynamic modules**: Programmatic, maintainable
- **Automatic optimization**: Systematic improvement
- **Consistent quality**: Confidence-scored responses
- **Rich metrics**: Detailed performance tracking

### Expected Improvements
- **20-50% better accuracy** in intent detection
- **30-40% improvement** in response relevance
- **Faster iteration** on AI behaviors
- **Better maintainability** with modular design

## Testing

### Run Comprehensive Tests

```bash
# Run the complete test suite
python test_dspy_integration.py
```

### Test Individual Components

```python
# Test DSPy modules
from app.core.dspy.base_modules import IntentDetectionModule
module = IntentDetectionModule()
result = module.forward("I want to book a table", "", "Restaurant")

# Test optimization pipeline
from app.core.dspy.optimizers import DSPyOptimizer, OptimizationConfig
config = OptimizationConfig(max_training_examples=50)
optimizer = DSPyOptimizer(config)
```

### API Testing

```bash
# Test DSPy chat endpoint
curl -X POST "http://localhost:8000/api/v1/dspy/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I need to book a table",
    "session_id": "test_session",
    "chat_context": "dedicated"
  }'

# Test system status
curl "http://localhost:8000/api/v1/dspy/status"

# Test module optimization
curl -X POST "http://localhost:8000/api/v1/dspy/optimize" \
  -H "Content-Type: application/json" \
  -d '{
    "modules": ["intent_detection", "response_generation"],
    "max_examples": 50,
    "optimization_budget": 5.0
  }'
```

## Monitoring and Metrics

### Performance Metrics

The system tracks comprehensive metrics:

```python
# Get performance metrics
from app.core.ai.dspy_enhanced_handler import DSPyEnhancedAIHandler
handler = DSPyEnhancedAIHandler()
metrics = handler.get_performance_metrics()

print(f"Success rate: {metrics['success_rate']:.2%}")
print(f"Average confidence: {metrics['average_confidence']:.2f}")
print(f"Total requests: {metrics['total_requests']}")
```

### Optimization Tracking

```python
# Get optimization status
from app.core.dspy.enhanced_conversation_engine import DSPyEnhancedConversationEngine
engine = DSPyEnhancedConversationEngine()
status = engine.get_optimization_status()

print(f"Modules optimized: {status['modules_optimized']}")
print(f"Optimization history: {len(status['optimization_history'])}")
```

## Troubleshooting

### Common Issues

1. **DSPy initialization fails**
   - Check API keys in `.env`
   - Verify network connectivity
   - Check model availability

2. **Low confidence scores**
   - Run optimization: `POST /api/v1/dspy/optimize`
   - Add more training data
   - Check business context quality

3. **Optimization fails**
   - Reduce `max_examples` in config
   - Lower `optimization_budget`
   - Check training data quality

### Debug Mode

Enable detailed logging:

```python
import logging
logging.getLogger('app.core.dspy').setLevel(logging.DEBUG)
```

### Health Checks

```python
from app.core.dspy.startup import health_check_dspy_system
health = await health_check_dspy_system()
print(f"Overall status: {health['overall_status']}")
```

## Migration Guide

### From Basic Prompts to DSPy

1. **Replace hardcoded prompts** with DSPy modules
2. **Add confidence scoring** to responses
3. **Implement optimization** workflows
4. **Monitor performance** metrics

### Gradual Migration

- Use `/message/dspy` endpoint for new conversations
- Keep existing `/message` endpoint for compatibility
- Gradually migrate high-traffic flows
- Monitor performance improvements

## Best Practices

### 1. Module Design
- Keep signatures focused and specific
- Use descriptive field names
- Include confidence scoring
- Handle edge cases gracefully

### 2. Optimization
- Start with small training sets (50-100 examples)
- Monitor optimization costs
- Use validation sets for evaluation
- Regular re-optimization with new data

### 3. Performance
- Cache optimized modules
- Monitor confidence thresholds
- Use fallback mechanisms
- Track success rates

### 4. Maintenance
- Regular health checks
- Monitor training data quality
- Update business contexts
- Review optimization results

## Future Enhancements

### Planned Features
- **Multi-model optimization**: Optimize across different LLMs
- **Real-time learning**: Continuous improvement from conversations
- **A/B testing**: Compare optimized vs. non-optimized responses
- **Custom metrics**: Business-specific evaluation criteria

### Integration Opportunities
- **Vector databases**: Enhanced context retrieval
- **Knowledge graphs**: Structured business knowledge
- **Multi-modal**: Image and voice processing
- **Federated learning**: Cross-business optimization

## Conclusion

The DSPy integration transforms X-SevenAI from a basic prompt-based system to a sophisticated, self-improving AI platform. With automatic optimization, confidence scoring, and systematic performance tracking, the system can now:

- **Adapt automatically** to improve performance
- **Scale systematically** across different business types
- **Maintain consistency** while allowing customization
- **Provide transparency** through confidence scores and reasoning

This foundation enables continuous improvement and positions X-SevenAI as a cutting-edge AI orchestration platform.

---

**Need Help?** Check the test script (`test_dspy_integration.py`) for comprehensive examples, or review the API documentation at `/docs` when running the application.
