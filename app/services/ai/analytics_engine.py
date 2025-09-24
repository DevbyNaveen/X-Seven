"""Stub AnalyticsEngine for predictive analytics endpoints.

Provides minimal async methods with safe defaults to unblock server startup.
"""
from __future__ import annotations

from typing import Any, Dict, List
from enum import Enum
from sqlalchemy.orm import Session


class TimeRange(str, Enum):
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class AnalyticsEngine:
    def __init__(self, db: Session) -> None:
        self.db = db

    async def get_business_dashboard(self, *, business_id: int, time_range: TimeRange) -> Dict[str, Any]:
        """Return a minimal dashboard payload.
        Matches expected shape used by `app/api/v1/endpoints/analytics.py`.
        """
        return {
            "business_id": business_id,
            "time_range": time_range.value if isinstance(time_range, TimeRange) else str(time_range),
            "summary": {
                "total_orders": 0,
                "total_revenue": 0.0,
                "average_order_value": 0.0,
                "returning_customers": 0,
            },
            "top_items": [],
            "trends": [],
            "alerts": [],
        }

    async def analyze_customer_churn_risk(self, *, business_id: int) -> List[Dict[str, Any]]:
        """Return empty churn risk list by default.
        Expected keys when populated: phone, last_order_date, days_since_last_order,
        total_orders, total_spent, average_order_value, churn_risk_score, risk_level.
        """
        return []

    async def predict_next_order(self, *, customer_phone: str, business_id: int) -> Dict[str, Any]:
        """Return a safe default next-order prediction structure."""
        return {
            "predicted_items": [],
            "confidence": 0.0,
            "predicted_time": {"window": "unknown"},
            "order_frequency_days": 0.0,
        }

    async def generate_personalized_recommendations(self, *, customer_phone: str, business_id: int) -> Dict[str, Any]:
        """Return a safe default recommendations structure."""
        return {
            "recommendations": [],  # List of {item_id, name, description, price, score, reason}
            "reasoning": "insufficient data",
            "preferences": {},
        }
