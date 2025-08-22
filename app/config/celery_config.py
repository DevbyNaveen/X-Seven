"""Celery configuration for background tasks."""
import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('CELERY_CONFIG_MODULE', 'app.config.celery_config')

# Broker settings
broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

# Task settings
task_serializer = 'json'
accept_content = ['json']
result_serializer = 'json'
timezone = 'UTC'
enable_utc = True

# Task routing
task_routes = {
    'app.tasks.order_tasks.*': {'queue': 'orders'},
    'app.tasks.notification_tasks.*': {'queue': 'notifications'},
    'app.tasks.analytics_tasks.*': {'queue': 'analytics'},
}

# Task execution settings
task_acks_late = True
worker_prefetch_multiplier = 1
task_always_eager = False  # Set to True for testing

# Result settings
result_expires = 3600  # 1 hour

# Worker settings
worker_max_tasks_per_child = 1000
worker_disable_rate_limits = False

# Beat settings (for periodic tasks)
beat_schedule = {
    'cleanup-expired-orders': {
        'task': 'app.tasks.order_tasks.cleanup_expired_orders',
        'schedule': 1800.0,  # 30 minutes
    },
    'process-waitlist-notifications': {
        'task': 'app.tasks.order_tasks.process_waitlist_notifications',
        'schedule': 900.0,  # 15 minutes
    },
    'update-analytics': {
        'task': 'app.tasks.analytics_tasks.update_analytics',
        'schedule': 3600.0,  # 1 hour
    },
}

# Logging
worker_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
worker_task_log_format = '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s'

# Error handling
task_reject_on_worker_lost = True
task_remote_tracebacks = True

# Monitoring
worker_send_task_events = True
task_send_sent_event = True
