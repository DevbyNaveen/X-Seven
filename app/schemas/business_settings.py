"""Business settings and configuration schemas."""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class FinancialReportingConfig(BaseModel):
    """Financial reporting configuration."""
    cost_of_goods_percentage: float = Field(default=0.30, ge=0.0, le=1.0, description="Cost of goods as percentage of revenue")
    labor_cost_percentage: float = Field(default=0.25, ge=0.0, le=1.0, description="Labor costs as percentage of revenue")
    overhead_cost_percentage: float = Field(default=0.12, ge=0.0, le=1.0, description="Overhead costs as percentage of revenue")
    target_profit_margin: float = Field(default=0.15, ge=0.0, le=1.0, description="Target profit margin")


class CustomerSegmentationConfig(BaseModel):
    """Customer segmentation configuration."""
    high_value_threshold: int = Field(default=5, ge=1, description="Number of orders to qualify as high-value customer")
    medium_value_threshold: int = Field(default=2, ge=1, description="Number of orders to qualify as medium-value customer")
    new_customer_days: int = Field(default=30, ge=1, description="Days since first order to qualify as new customer")


class OperationalMetricsConfig(BaseModel):
    """Operational metrics configuration."""
    target_prep_time_minutes: int = Field(default=15, ge=1, description="Target preparation time in minutes")
    target_cancellation_rate: float = Field(default=0.05, ge=0.0, le=1.0, description="Target cancellation rate")
    target_delivery_time_minutes: int = Field(default=30, ge=1, description="Target delivery time in minutes")
    peak_hour_threshold: int = Field(default=10, ge=1, description="Orders per hour to qualify as peak time")


class ReportSettings(BaseModel):
    """Report generation settings."""
    default_period_days: int = Field(default=30, ge=1, description="Default report period in days")
    include_cost_analysis: bool = Field(default=True, description="Include cost analysis in financial reports")
    include_customer_segments: bool = Field(default=True, description="Include customer segmentation in reports")
    include_operational_metrics: bool = Field(default=True, description="Include operational metrics in reports")
    currency_symbol: str = Field(default="$", description="Currency symbol for reports")
    date_format: str = Field(default="%Y-%m-%d", description="Date format for reports")


class BusinessSettings(BaseModel):
    """Complete business settings configuration."""
    financial_reporting: FinancialReportingConfig = Field(default_factory=FinancialReportingConfig)
    customer_segmentation: CustomerSegmentationConfig = Field(default_factory=CustomerSegmentationConfig)
    operational_metrics: OperationalMetricsConfig = Field(default_factory=OperationalMetricsConfig)
    report_settings: ReportSettings = Field(default_factory=ReportSettings)
    
    class Config:
        json_schema_extra = {
            "example": {
                "financial_reporting": {
                    "cost_of_goods_percentage": 0.28,
                    "labor_cost_percentage": 0.22,
                    "overhead_cost_percentage": 0.10,
                    "target_profit_margin": 0.20
                },
                "customer_segmentation": {
                    "high_value_threshold": 10,
                    "medium_value_threshold": 3,
                    "new_customer_days": 30
                },
                "operational_metrics": {
                    "target_prep_time_minutes": 12,
                    "target_cancellation_rate": 0.03,
                    "target_delivery_time_minutes": 25,
                    "peak_hour_threshold": 15
                },
                "report_settings": {
                    "default_period_days": 30,
                    "include_cost_analysis": True,
                    "include_customer_segments": True,
                    "include_operational_metrics": True,
                    "currency_symbol": "$",
                    "date_format": "%Y-%m-%d"
                }
            }
        }
