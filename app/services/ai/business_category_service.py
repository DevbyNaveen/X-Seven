"""Stub BusinessCategoryService for business category endpoints.

Minimal implementation to satisfy imports and provide safe defaults.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session


class BusinessCategoryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    async def get_available_categories(self) -> List[Dict[str, Any]]:
        """Return empty list of categories by default."""
        return []

    async def get_category_template(self, *, category: Any) -> Dict[str, Any]:
        """Return minimal template structure for a category."""
        return {
            "default_services": [],
            "pricing_tier": "basic",
            "features": [],
        }

    async def apply_category_to_business(self, *, business_id: int, category: Any, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Pretend to apply a category to a business and return applied config."""
        template = await self.get_category_template(category=category)
        applied = dict(template)
        if config:
            applied.update(config)
        return applied
