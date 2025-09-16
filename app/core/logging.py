"""
Structured logging configuration for AI services
"""
import logging
import json
import sys
from typing import Dict, Any
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add extra fields
        if hasattr(record, 'service'):
            log_entry['service'] = record.service
        if hasattr(record, 'chat_context'):
            log_entry['chat_context'] = record.chat_context
        if hasattr(record, 'session_id'):
            log_entry['session_id'] = record.session_id
        if hasattr(record, 'business_id'):
            log_entry['business_id'] = record.business_id
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'duration'):
            log_entry['duration_ms'] = record.duration
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry)


def setup_logging(service_name: str, level: str = "INFO"):
    """Setup structured logging for a service"""
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Console handler with JSON formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(JSONFormatter())
    
    # Add service context to all logs
    console_handler.addFilter(lambda record: setattr(record, 'service', service_name) or True)
    
    logger.addHandler(console_handler)
    
    return logger


def get_service_logger(service_name: str):
    """Get a logger instance for a specific service"""
    return logging.getLogger(f"xseven.{service_name}")
