# Dynamic Role Mapping Guide

This guide explains how to use the dynamic role mapping system for chat messages in X-SevenAI.

## Overview

The dynamic role mapping system provides a flexible way to map various sender types to standardized chat roles (`user` or `assistant`). This enables the system to handle different types of message senders without hardcoding role mappings.

## Quick Start

### Basic Usage

```python
from app.core.ai.role_mapper import RoleMapper

# Map sender type to chat role
role = RoleMapper.get_chat_role("customer")  # Returns "user"
role = RoleMapper.get_chat_role("bot")       # Returns "assistant"

# Check role types
is_customer = RoleMapper.is_customer_role("customer")  # True
is_ai = RoleMapper.is_ai_role("assistant")             # True
```

### Convenience Functions

```python
from app.core.ai.role_mapper import map_sender_to_role, is_user_message, is_assistant_message

# Simple mapping
role = map_sender_to_role("staff")  # Returns "assistant"

# Quick checks
if is_user_message(sender_type):
    # Handle user message
    pass

if is_assistant_message(sender_type):
    # Handle AI response
    pass
```

## Supported Sender Types

### Customer/User Roles (map to "user")
- `customer`
- `user`
- `client`
- `guest`

### AI/Assistant Roles (map to "assistant")
- `assistant`
- `bot`
- `ai`
- `system`
- `business`
- `staff`
- `admin`
- `manager`
- `support`
- `agent`

## Custom Mappings

You can add custom role mappings at runtime:

```python
from app.core.ai.role_mapper import RoleMapper

# Add custom mapping
RoleMapper.add_custom_mapping("vendor", "assistant")
RoleMapper.add_custom_mapping("test_user", "user")

# Use custom mapping
role = RoleMapper.get_chat_role("vendor")  # Returns "assistant"
```

## Integration Examples

### In Conversation History

The role mapper is automatically used when loading conversation history:

```python
# In context_builders.py - automatically handled
history = []
for msg in reversed(messages):
    role = RoleMapper.get_chat_role(msg.get('sender_type', 'customer'))
    history.append({
        "role": role,
        "content": msg['content'],
        "timestamp": msg['created_at']
    })
```

### In Message Processing

When processing incoming messages:

```python
# Determine role based on message source
if message_from_customer:
    sender_type = "customer"
elif message_from_staff:
    sender_type = "staff"
elif message_from_system:
    sender_type = "system"

# Map to standard role
chat_role = RoleMapper.get_chat_role(sender_type)
```

## Error Handling

The system handles edge cases gracefully:

```python
# Unknown sender types default to "user"
role = RoleMapper.get_chat_role("unknown_type")  # Returns "user"

# Empty or None values use default
role = RoleMapper.get_chat_role("")  # Returns "user"
role = RoleMapper.get_chat_role(None)  # Returns "user"

# Custom default role
role = RoleMapper.get_chat_role("unknown", default_role="assistant")  # Returns "assistant"
```

## Testing

Run the comprehensive test suite:

```bash
pytest tests/test_role_mapper.py -v
```

## Database Schema Compatibility

The role mapping system works with the existing database schema. The `messages` table uses:

- `sender_type`: Stores the original sender type (e.g., "customer", "bot", "staff")
- Role mapping happens at runtime when loading conversation history

## Migration Notes

The dynamic role mapping is backward compatible:
- Existing "customer" and "assistant" values continue to work
- New sender types can be added without database changes
- No migration required for existing data

## Best Practices

1. **Use standard types when possible**: Stick to "customer" for users and "assistant" for AI
2. **Add custom mappings for business-specific needs**: Use `add_custom_mapping()` for domain-specific sender types
3. **Handle unknown types gracefully**: The system defaults to "user" for unknown types
4. **Log unknown types**: Monitor logs for unknown sender types to improve mappings

## Troubleshooting

### Common Issues

1. **Unknown sender type warnings**: Check logs for unknown sender types and add appropriate mappings
2. **Role mapping not working**: Ensure sender types are lowercase and match known patterns
3. **Custom mappings not persisting**: Custom mappings are runtime-only; add them at application startup if needed

### Debug Mode

Enable debug logging to see role mapping decisions:

```python
import logging
logging.getLogger('app.core.ai.role_mapper').setLevel(logging.DEBUG)
```

## API Reference

### RoleMapper Class

- `get_chat_role(sender_type, default_role="user")` - Main mapping function
- `add_custom_mapping(sender_type, chat_role)` - Add custom mappings
- `get_all_mappings()` - Get all current mappings
- `is_customer_role(sender_type)` - Check if sender is a customer
- `is_ai_role(sender_type)` - Check if sender is AI/assistant

### Convenience Functions

- `map_sender_to_role(sender_type)` - Simple role mapping
- `is_user_message(sender_type)` - Check if message is from user
- `is_assistant_message(sender_type)` - Check if message is from assistant
