"""Utilities for ensuring idempotent Celery task execution using Redis.

Usage:
    from app.tasks.utils.idempotency import Idempotency
    async with Idempotency(redis_client).guard(key, ttl_seconds=300):
        # run task code

If the key is already present, the guard raises a RuntimeError to skip duplicate work.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

import redis.asyncio as redis


class Idempotency:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    @asynccontextmanager
    async def guard(self, key: str, ttl_seconds: int = 300) -> AsyncIterator[None]:
        token = "1"
        acquired = await self.redis.set(name=key, value=token, nx=True, ex=ttl_seconds)
        if not acquired:
            raise RuntimeError("Duplicate task invocation (idempotency key exists)")
        try:
            yield None
        finally:
            # Best-effort cleanup; allow key to expire if deletion fails
            try:
                await self.redis.delete(key)
            except Exception:
                pass
