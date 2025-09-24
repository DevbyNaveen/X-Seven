"""Central Celery app factory and configuration binding."""
from __future__ import annotations

from celery import Celery
from typing import Dict, Any

from app.config.settings import settings
from app.config import celery_config as cfg


def create_celery_app() -> Celery:
    app = Celery("x_sevenai")

    # Core broker/backend
    app.conf.broker_url = getattr(settings, "CELERY_BROKER_URL", None) or cfg.broker_url
    app.conf.result_backend = getattr(settings, "CELERY_RESULT_BACKEND", None) or cfg.result_backend

    # Serialization and timezone
    app.conf.update(
        task_serializer=cfg.task_serializer,
        accept_content=cfg.accept_content,
        result_serializer=cfg.result_serializer,
        timezone=cfg.timezone,
        enable_utc=cfg.enable_utc,
        task_acks_late=cfg.task_acks_late,
        worker_prefetch_multiplier=cfg.worker_prefetch_multiplier,
        task_always_eager=cfg.task_always_eager,
        result_expires=cfg.result_expires,
        worker_max_tasks_per_child=cfg.worker_max_tasks_per_child,
        worker_disable_rate_limits=cfg.worker_disable_rate_limits,
        worker_log_format=cfg.worker_log_format,
        worker_task_log_format=cfg.worker_task_log_format,
        task_reject_on_worker_lost=cfg.task_reject_on_worker_lost,
        task_remote_tracebacks=cfg.task_remote_tracebacks,
        worker_send_task_events=cfg.worker_send_task_events,
        task_send_sent_event=cfg.task_send_sent_event,
    )

    # Routing and beat schedule
    app.conf.task_routes = cfg.task_routes  # type: ignore
    app.conf.beat_schedule = cfg.beat_schedule  # type: ignore

    # Autodiscover tasks
    app.autodiscover_tasks([
        "app.tasks",  # e.g., app.tasks.order_tasks, app.tasks.notification_tasks, etc.
    ])

    return app


celery_app = create_celery_app()
