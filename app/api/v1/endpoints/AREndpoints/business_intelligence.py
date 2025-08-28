"""
Business Intelligence Endpoints Module
Provides advanced business intelligence and predictive analytics capabilities.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from datetime import datetime, timedelta
import random
import json

from app.config.database import get_db
from app.core.dependencies import get_current_business
from app.models.order import Order
from app.models.business import Business
from app.models.user import User

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# =======================
# BUSINESS INTELLIGENCE
# =======================

@router.get("/analytics/profitability")
async def get_profitability_analysis(
    period: str = Query("monthly", description="Analysis period: daily, weekly, monthly"),
    business_id: int = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """
    Profit margin analysis.
    Comprehensive analysis of profit margins and profitability trends.
    """
    try:
        # Calculate date range based on period
        end_date = datetime.now().date()
        if period == "daily":
            start_date = end_date
        elif period == "weekly":
            start_date = end_date - timedelta(days=7)
        else:  # monthly
            start_date = end_date.replace(day=1)
        
        # Get orders for the period
        orders = db.query(Order).filter(
            Order.business_id == business_id,
            Order.created_at >= start_date,
            Order.created_at <= end_date + timedelta(days=1)
        ).all()
        
        # Calculate revenue
        total_revenue = sum(order.total_amount for order in orders)
        total_orders = len(orders)
        
        # Simulate cost calculations
        cost_of_goods = total_revenue * random.uniform(0.25, 0.35)  # 25-35% of revenue
        labor_costs = total_revenue * random.uniform(0.20, 0.30)     # 20-30% of revenue
        overhead_costs = total_revenue * random.uniform(0.10, 0.15)   # 10-15% of revenue
        marketing_costs = total_revenue * random.uniform(0.05, 0.10)  # 5-10% of revenue
        
        total_costs = cost_of_goods + labor_costs + overhead_costs + marketing_costs
        gross_profit = total_revenue - cost_of_goods
        net_profit = total_revenue - total_costs
        
        # Calculate margins
        gross_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0
        net_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0
        
        # Profitability by category (simulated)
        categories = ["Food", "Beverages", "Desserts", "Appetizers"]
        category_profitability = [
            {
                "category": category,
                "revenue": round(total_revenue * random.uniform(0.15, 0.35), 2),
                "costs": round(total_revenue * random.uniform(0.10, 0.25), 2),
                "profit": round(total_revenue * random.uniform(0.05, 0.15), 2),
                "margin": round(random.uniform(15, 35), 2)
            }
            for category in categories
        ]
        
        return {
            "type": "profitability_analysis",
            "period": period,
            "date_range": {
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d")
            },
            "revenue": {
                "total": round(total_revenue, 2),
                "average_per_order": round(total_revenue / total_orders, 2) if total_orders > 0 else 0
            },
            "costs": {
                "total": round(total_costs, 2),
                "cost_of_goods": round(cost_of_goods, 2),
                "labor": round(labor_costs, 2),
                "overhead": round(overhead_costs, 2),
                "marketing": round(marketing_costs, 2)
            },
            "profitability": {
                "gross_profit": round(gross_profit, 2),
                "net_profit": round(net_profit, 2),
                "gross_margin": round(gross_margin, 2),
                "net_margin": round(net_margin, 2)
            },
            "by_category": category_profitability
        }
    except Exception as e:
        logger.error(f"Error in get_profitability_analysis: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate profitability analysis")

@router.get("/analytics/cost-analysis")
async def get_cost_analysis(
    business_id: int = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """
    Operating cost breakdown.
    Detailed breakdown of operating costs and expense analysis.
    """
    try:
        # Current month dates
        current_date = datetime.now().date()
        start_date = current_date.replace(day=1)
        end_date = start_date.replace(day=1) + timedelta(days=32)
        end_date = end_date.replace(day=1) - timedelta(days=1)  # Last day of current month
        
        # Get orders for current month
        orders = db.query(Order).filter(
            Order.business_id == business_id,
            Order.created_at >= start_date,
            Order.created_at <= end_date + timedelta(days=1)
        ).all()
        
        # Calculate revenue
        total_revenue = sum(order.total_amount for order in orders)
        
        # Simulate detailed cost breakdown
        cost_breakdown = {
            "fixed_costs": {
                "rent": round(total_revenue * random.uniform(0.08, 0.12), 2),  # 8-12% of revenue
                "insurance": round(total_revenue * random.uniform(0.02, 0.04), 2),  # 2-4% of revenue
                "utilities": round(total_revenue * random.uniform(0.03, 0.06), 2),  # 3-6% of revenue
                "equipment": round(total_revenue * random.uniform(0.02, 0.05), 2),  # 2-5% of revenue
                "licenses": round(total_revenue * random.uniform(0.01, 0.02), 2)   # 1-2% of revenue
            },
            "variable_costs": {
                "food_ingredients": round(total_revenue * random.uniform(0.25, 0.35), 2),  # 25-35% of revenue
                "labor": round(total_revenue * random.uniform(0.20, 0.30), 2),  # 20-30% of revenue
                "marketing": round(total_revenue * random.uniform(0.05, 0.10), 2),  # 5-10% of revenue
                "packaging": round(total_revenue * random.uniform(0.02, 0.04), 2),  # 2-4% of revenue
                "delivery": round(total_revenue * random.uniform(0.03, 0.07), 2)   # 3-7% of revenue
            }
        }
        
        # Calculate totals
        fixed_total = sum(cost_breakdown["fixed_costs"].values())
        variable_total = sum(cost_breakdown["variable_costs"].values())
        total_costs = fixed_total + variable_total
        
        # Cost ratios
        fixed_cost_ratio = (fixed_total / total_revenue * 100) if total_revenue > 0 else 0
        variable_cost_ratio = (variable_total / total_revenue * 100) if total_revenue > 0 else 0
        
        # Identify high-cost areas
        all_costs = {**cost_breakdown["fixed_costs"], **cost_breakdown["variable_costs"]}
        sorted_costs = sorted(all_costs.items(), key=lambda x: x[1], reverse=True)
        high_cost_areas = [
            {"category": category, "amount": round(amount, 2), "percentage": round(amount / total_revenue * 100, 2)}
            for category, amount in sorted_costs[:5]  # Top 5 cost areas
        ]
        
        return {
            "type": "cost_analysis",
            "period": {
                "month": start_date.strftime("%Y-%m"),
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d")
            },
            "revenue": round(total_revenue, 2),
            "cost_breakdown": cost_breakdown,
            "totals": {
                "fixed_costs": round(fixed_total, 2),
                "variable_costs": round(variable_total, 2),
                "total_costs": round(total_costs, 2)
            },
            "ratios": {
                "fixed_cost_ratio": round(fixed_cost_ratio, 2),
                "variable_cost_ratio": round(variable_cost_ratio, 2)
            },
            "high_cost_areas": high_cost_areas
        }
    except Exception as e:
        logger.error(f"Error in get_cost_analysis: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate cost analysis")

@router.get("/analytics/seasonal-trends")
async def get_seasonal_trends(
    business_id: int = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """
    Seasonal pattern identification.
    Analysis of seasonal trends and cyclical business patterns.
    """
    try:
        # Get orders for the past 2 years
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=730)  # 2 years
        
        orders = db.query(Order).filter(
            Order.business_id == business_id,
            Order.created_at >= start_date,
            Order.created_at <= end_date + timedelta(days=1)
        ).all()
        
        # Group orders by month
        monthly_data = {}
        for order in orders:
            month_key = order.created_at.strftime("%Y-%m")
            if month_key not in monthly_data:
                monthly_data[month_key] = {
                    "orders": [],
                    "revenue": 0
                }
            monthly_data[month_key]["orders"].append(order)
            monthly_data[month_key]["revenue"] += order.total_amount
        
        # Calculate seasonal metrics
        seasonal_data = []
        for month_key, data in monthly_data.items():
            orders_count = len(data["orders"])
            revenue = data["revenue"]
            avg_order_value = revenue / orders_count if orders_count > 0 else 0
            
            seasonal_data.append({
                "month": month_key,
                "metrics": {
                    "revenue": round(revenue, 2),
                    "orders": orders_count,
                    "avg_order_value": round(avg_order_value, 2)
                }
            })
        
        # Identify seasonal patterns
        # Group by month of year for seasonal analysis
        monthly_patterns = {}
        for order in orders:
            month_of_year = order.created_at.strftime("%m")
            if month_of_year not in monthly_patterns:
                monthly_patterns[month_of_year] = {
                    "revenue": 0,
                    "orders": 0,
                    "count": 0
                }
            monthly_patterns[month_of_year]["revenue"] += order.total_amount
            monthly_patterns[month_of_year]["orders"] += 1
            monthly_patterns[month_of_year]["count"] += 1
        
        # Calculate averages
        seasonal_averages = [
            {
                "month": month,
                "avg_revenue": round(data["revenue"] / data["count"], 2),
                "avg_orders": round(data["orders"] / data["count"], 2)
            }
            for month, data in sorted(monthly_patterns.items())
        ]
        
        # Identify peak and low seasons
        sorted_by_revenue = sorted(seasonal_averages, key=lambda x: x["avg_revenue"], reverse=True)
        peak_seasons = sorted_by_revenue[:3]  # Top 3 months
        low_seasons = sorted_by_revenue[-3:]  # Bottom 3 months
        
        return {
            "type": "seasonal_trends",
            "period": {
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "duration": "2 years"
            },
            "monthly_data": seasonal_data,
            "seasonal_averages": seasonal_averages,
            "peak_seasons": peak_seasons,
            "low_seasons": low_seasons,
            "insights": {
                "revenue_volatility": round(
                    (max(d["avg_revenue"] for d in seasonal_averages) - 
                     min(d["avg_revenue"] for d in seasonal_averages)) / 
                    (sum(d["avg_revenue"] for d in seasonal_averages) / len(seasonal_averages)) * 100, 2
                ) if seasonal_averages else 0
            }
        }
    except Exception as e:
        logger.error(f"Error in get_seasonal_trends: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate seasonal trends analysis")

@router.get("/analytics/competitive-position")
async def get_competitive_position(
    business_id: int = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """
    Market performance benchmarking.
    Competitive positioning analysis against market benchmarks.
    """
    try:
        # Current month dates
        current_date = datetime.now().date()
        start_date = current_date.replace(day=1)
        end_date = start_date.replace(day=1) + timedelta(days=32)
        end_date = end_date.replace(day=1) - timedelta(days=1)  # Last day of current month
        
        # Get orders for current month
        orders = db.query(Order).filter(
            Order.business_id == business_id,
            Order.created_at >= start_date,
            Order.created_at <= end_date + timedelta(days=1)
        ).all()
        
        # Calculate business metrics
        total_revenue = sum(order.total_amount for order in orders)
        total_orders = len(orders)
        avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
        
        # Customer metrics
        unique_customers = len(set(order.customer_id for order in orders if order.customer_id))
        repeat_customers = len([order for order in orders if order.customer_id and 
                              len([o for o in orders if o.customer_id == order.customer_id]) > 1])
        repeat_rate = (repeat_customers / unique_customers * 100) if unique_customers > 0 else 0
        
        # Simulate market benchmarks (in a real implementation, this would come from market data)
        market_benchmarks = {
            "avg_revenue": total_revenue * random.uniform(0.8, 1.3),  # 80-130% of business revenue
            "avg_order_value": avg_order_value * random.uniform(0.9, 1.2),  # 90-120% of business AOV
            "avg_monthly_orders": total_orders * random.uniform(0.7, 1.5),  # 70-150% of business orders
            "avg_customer_retention": random.uniform(25, 45)  # 25-45% retention rate
        }
        
        # Calculate competitive position
        revenue_position = ((total_revenue - market_benchmarks["avg_revenue"]) / 
                           market_benchmarks["avg_revenue"] * 100)
        aov_position = ((avg_order_value - market_benchmarks["avg_order_value"]) / 
                       market_benchmarks["avg_order_value"] * 100)
        order_position = ((total_orders - market_benchmarks["avg_monthly_orders"]) / 
                         market_benchmarks["avg_monthly_orders"] * 100)
        retention_position = (repeat_rate - market_benchmarks["avg_customer_retention"])
        
        # Competitive quartiles
        def get_quartile(position):
            if position >= 20:
                return "Top Quartile"
            elif position >= 5:
                return "Upper Middle"
            elif position >= -5:
                return "Middle"
            elif position >= -20:
                return "Lower Middle"
            else:
                return "Bottom Quartile"
        
        return {
            "type": "competitive_position",
            "period": {
                "month": start_date.strftime("%Y-%m"),
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d")
            },
            "business_metrics": {
                "total_revenue": round(total_revenue, 2),
                "total_orders": total_orders,
                "average_order_value": round(avg_order_value, 2),
                "unique_customers": unique_customers,
                "customer_retention_rate": round(repeat_rate, 2)
            },
            "market_benchmarks": {
                "avg_revenue": round(market_benchmarks["avg_revenue"], 2),
                "avg_order_value": round(market_benchmarks["avg_order_value"], 2),
                "avg_monthly_orders": round(market_benchmarks["avg_monthly_orders"], 2),
                "avg_customer_retention": round(market_benchmarks["avg_customer_retention"], 2)
            },
            "competitive_position": {
                "revenue_position": round(revenue_position, 2),
                "aov_position": round(aov_position, 2),
                "order_position": round(order_position, 2),
                "retention_position": round(retention_position, 2)
            },
            "quartiles": {
                "revenue": get_quartile(revenue_position),
                "order_value": get_quartile(aov_position),
                "order_volume": get_quartile(order_position),
                "customer_retention": get_quartile(retention_position)
            },
            "recommendations": [
                "Focus on customer retention programs to improve retention rate" if retention_position < 0 else "Maintain strong customer retention strategy",
                "Optimize pricing strategy" if aov_position < 0 else "Continue current pricing approach",
                "Expand marketing efforts to increase order volume" if order_position < 0 else "Sustain current marketing effectiveness"
            ]
        }
    except Exception as e:
        logger.error(f"Error in get_competitive_position: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate competitive position analysis")

@router.get("/analytics/growth-metrics")
async def get_growth_metrics(
    months: int = Query(12, description="Number of months to analyze for growth"),
    business_id: int = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """
    Business growth indicators.
    Key performance indicators tracking business growth and expansion.
    """
    try:
        # Calculate date range
        end_date = datetime.now().date()
        start_date = end_date.replace(day=1)
        
        # Go back months-1 times to get the start date
        for _ in range(months - 1):
            if start_date.month == 1:
                start_date = start_date.replace(year=start_date.year - 1, month=12)
            else:
                start_date = start_date.replace(month=start_date.month - 1)
        
        # Get orders for the period
        orders = db.query(Order).filter(
            Order.business_id == business_id,
            Order.created_at >= start_date,
            Order.created_at <= end_date + timedelta(days=1)
        ).all()
        
        # Group orders by month
        monthly_data = {}
        for order in orders:
            month_key = order.created_at.strftime("%Y-%m")
            if month_key not in monthly_data:
                monthly_data[month_key] = {
                    "orders": [],
                    "revenue": 0
                }
            monthly_data[month_key]["orders"].append(order)
            monthly_data[month_key]["revenue"] += order.total_amount
        
        # Calculate growth metrics
        growth_data = []
        sorted_months = sorted(monthly_data.keys())
        
        for month_key in sorted_months:
            data = monthly_data[month_key]
            orders_count = len(data["orders"])
            revenue = data["revenue"]
            avg_order_value = revenue / orders_count if orders_count > 0 else 0
            
            # Customer metrics
            unique_customers = len(set(order.customer_id for order in data["orders"] if order.customer_id))
            
            growth_data.append({
                "month": month_key,
                "metrics": {
                    "revenue": round(revenue, 2),
                    "orders": orders_count,
                    "customers": unique_customers,
                    "avg_order_value": round(avg_order_value, 2)
                }
            })
        
        # Calculate growth rates
        if len(growth_data) >= 2:
            # Revenue growth (month over month)
            revenue_growth_rates = []
            for i in range(1, len(growth_data)):
                prev_rev = growth_data[i-1]["metrics"]["revenue"]
                curr_rev = growth_data[i]["metrics"]["revenue"]
                growth = ((curr_rev - prev_rev) / prev_rev * 100) if prev_rev > 0 else 0
                revenue_growth_rates.append({
                    "month": growth_data[i]["month"],
                    "growth_rate": round(growth, 2)
                })
            
            # Calculate overall growth trend
            overall_revenue_growth = ((growth_data[-1]["metrics"]["revenue"] - 
                                     growth_data[0]["metrics"]["revenue"]) / 
                                    growth_data[0]["metrics"]["revenue"] * 100) if growth_data[0]["metrics"]["revenue"] > 0 else 0
            
            # Order growth
            overall_order_growth = ((growth_data[-1]["metrics"]["orders"] - 
                                   growth_data[0]["metrics"]["orders"]) / 
                                  growth_data[0]["metrics"]["orders"] * 100) if growth_data[0]["metrics"]["orders"] > 0 else 0
            
            # Customer growth
            overall_customer_growth = ((growth_data[-1]["metrics"]["customers"] - 
                                      growth_data[0]["metrics"]["customers"]) / 
                                     growth_data[0]["metrics"]["customers"] * 100) if growth_data[0]["metrics"]["customers"] > 0 else 0
        else:
            revenue_growth_rates = []
            overall_revenue_growth = 0
            overall_order_growth = 0
            overall_customer_growth = 0
        
        # Calculate CAGR (Compound Annual Growth Rate)
        if len(growth_data) > 1 and growth_data[0]["metrics"]["revenue"] > 0:
            years = months / 12
            cagr = ((growth_data[-1]["metrics"]["revenue"] / growth_data[0]["metrics"]["revenue"]) ** (1/years) - 1) * 100
        else:
            cagr = 0
        
        # Identify growth trends
        positive_months = len([m for m in revenue_growth_rates if m["growth_rate"] > 0])
        negative_months = len([m for m in revenue_growth_rates if m["growth_rate"] < 0])
        
        trend = "positive" if positive_months > negative_months else "negative" if negative_months > positive_months else "mixed"
        
        return {
            "type": "growth_metrics",
            "period": {
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "months_analyzed": months
            },
            "overall_growth": {
                "revenue_growth": round(overall_revenue_growth, 2),
                "order_growth": round(overall_order_growth, 2),
                "customer_growth": round(overall_customer_growth, 2),
                "cagr": round(cagr, 2)
            },
            "monthly_growth": revenue_growth_rates,
            "trend_analysis": {
                "direction": trend,
                "positive_months": positive_months,
                "negative_months": negative_months,
                "stability": "stable" if abs(positive_months - negative_months) <= 2 else "volatile"
            },
            "latest_performance": growth_data[-3:] if len(growth_data) >= 3 else growth_data
        }
    except Exception as e:
        logger.error(f"Error in get_growth_metrics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate growth metrics analysis")

# =======================
# PREDICTIVE ANALYTICS
# =======================

@router.get("/analytics/predictive-modeling")
async def get_predictive_modeling(
    business_id: int = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """
    AI-powered predictions.
    Advanced predictive modeling for business forecasting.
    """
    try:
        # Current date
        current_date = datetime.now().date()
        
        # Get orders for the past 90 days
        start_date = current_date - timedelta(days=90)
        orders = db.query(Order).filter(
            Order.business_id == business_id,
            Order.created_at >= start_date,
            Order.created_at <= current_date + timedelta(days=1)
        ).all()
        
        # Calculate historical metrics
        total_revenue = sum(order.total_amount for order in orders)
        total_orders = len(orders)
        avg_daily_orders = total_orders / 90 if total_orders > 0 else 0
        avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
        
        # Customer metrics
        unique_customers = len(set(order.customer_id for order in orders if order.customer_id))
        
        # Simulate AI-powered predictions
        # In a real implementation, this would use ML models
        
        # Revenue predictions
        next_7_days_revenue = total_revenue / 90 * 7 * random.uniform(0.9, 1.2)
        next_30_days_revenue = total_revenue / 90 * 30 * random.uniform(0.95, 1.1)
        next_90_days_revenue = total_revenue * random.uniform(0.98, 1.05)
        
        # Order predictions
        next_7_days_orders = total_orders / 90 * 7 * random.uniform(0.85, 1.25)
        next_30_days_orders = total_orders / 90 * 30 * random.uniform(0.9, 1.15)
        next_90_days_orders = total_orders * random.uniform(0.95, 1.08)
        
        # Customer predictions
        next_30_days_new_customers = unique_customers / 3 * random.uniform(0.8, 1.3)
        next_90_days_new_customers = unique_customers * random.uniform(0.9, 1.2)
        
        # Confidence scores (simulated)
        confidence_scores = {
            "7_day_revenue": round(random.uniform(75, 95), 2),
            "30_day_revenue": round(random.uniform(70, 90), 2),
            "90_day_revenue": round(random.uniform(65, 85), 2),
            "7_day_orders": round(random.uniform(70, 90), 2),
            "30_day_orders": round(random.uniform(65, 85), 2),
            "90_day_orders": round(random.uniform(60, 80), 2)
        }
        
        # Risk factors (simulated)
        risk_factors = [
            {"factor": "Seasonal fluctuations", "impact": "medium", "probability": round(random.uniform(30, 60), 2)},
            {"factor": "Market competition", "impact": "low" if confidence_scores["30_day_revenue"] > 80 else "medium", 
             "probability": round(random.uniform(20, 50), 2)},
            {"factor": "Economic conditions", "impact": "low", "probability": round(random.uniform(10, 30), 2)}
        ]
        
        return {
            "type": "predictive_modeling",
            "period": {
                "historical_data_from": start_date.strftime("%Y-%m-%d"),
                "historical_data_to": current_date.strftime("%Y-%m-%d"),
                "analysis_date": current_date.strftime("%Y-%m-%d")
            },
            "historical_metrics": {
                "total_revenue": round(total_revenue, 2),
                "total_orders": total_orders,
                "average_daily_orders": round(avg_daily_orders, 2),
                "average_order_value": round(avg_order_value, 2),
                "unique_customers": unique_customers
            },
            "predictions": {
                "revenue": {
                    "next_7_days": round(next_7_days_revenue, 2),
                    "next_30_days": round(next_30_days_revenue, 2),
                    "next_90_days": round(next_90_days_revenue, 2),
                    "confidence": {
                        "7_day": confidence_scores["7_day_revenue"],
                        "30_day": confidence_scores["30_day_revenue"],
                        "90_day": confidence_scores["90_day_revenue"]
                    }
                },
                "orders": {
                    "next_7_days": round(next_7_days_orders),
                    "next_30_days": round(next_30_days_orders),
                    "next_90_days": round(next_90_days_orders),
                    "confidence": {
                        "7_day": confidence_scores["7_day_orders"],
                        "30_day": confidence_scores["30_day_orders"],
                        "90_day": confidence_scores["90_day_orders"]
                    }
                },
                "customers": {
                    "next_30_days_new": round(next_30_days_new_customers),
                    "next_90_days_new": round(next_90_days_new_customers)
                }
            },
            "risk_factors": risk_factors,
            "recommendations": [
                "Maintain current marketing spend to support revenue growth",
                "Prepare for increased order volume in the next 30 days",
                "Consider seasonal inventory adjustments based on predicted demand"
            ]
        }
    except Exception as e:
        logger.error(f"Error in get_predictive_modeling: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate predictive modeling analysis")

@router.get("/analytics/anomaly-detection")
async def get_anomaly_detection(
    days: int = Query(30, description="Number of days to analyze for anomalies"),
    business_id: int = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """
    Unusual pattern identification.
    Detection of unusual patterns and outliers in business data.
    """
    try:
        # Calculate date range
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Get orders for the period
        orders = db.query(Order).filter(
            Order.business_id == business_id,
            Order.created_at >= start_date,
            Order.created_at <= end_date + timedelta(days=1)
        ).all()
        
        # Group orders by day
        daily_data = {}
        for order in orders:
            day_key = order.created_at.date()
            if day_key not in daily_data:
                daily_data[day_key] = {
                    "orders": [],
                    "revenue": 0
                }
            daily_data[day_key]["orders"].append(order)
            daily_data[day_key]["revenue"] += order.total_amount
        
        # Calculate daily metrics
        daily_metrics = []
        for day_key, data in daily_data.items():
            orders_count = len(data["orders"])
            revenue = data["revenue"]
            avg_order_value = revenue / orders_count if orders_count > 0 else 0
            
            daily_metrics.append({
                "date": day_key.strftime("%Y-%m-%d"),
                "orders": orders_count,
                "revenue": round(revenue, 2),
                "avg_order_value": round(avg_order_value, 2)
            })
        
        # Calculate averages and standard deviations
        if daily_metrics:
            avg_orders = sum(d["orders"] for d in daily_metrics) / len(daily_metrics)
            avg_revenue = sum(d["revenue"] for d in daily_metrics) / len(daily_metrics)
            
            # Calculate standard deviations
            orders_variance = sum((d["orders"] - avg_orders) ** 2 for d in daily_metrics) / len(daily_metrics)
            revenue_variance = sum((d["revenue"] - avg_revenue) ** 2 for d in daily_metrics) / len(daily_metrics)
            
            std_orders = orders_variance ** 0.5
            std_revenue = revenue_variance ** 0.5
            
            # Detect anomalies (values more than 2 standard deviations from mean)
            anomalies = []
            for day in daily_metrics:
                orders_z_score = abs(day["orders"] - avg_orders) / std_orders if std_orders > 0 else 0
                revenue_z_score = abs(day["revenue"] - avg_revenue) / std_revenue if std_revenue > 0 else 0
                
                if orders_z_score > 2 or revenue_z_score > 2:
                    anomaly_type = []
                    if orders_z_score > 2:
                        anomaly_type.append(f"orders (z-score: {round(orders_z_score, 2)})")
                    if revenue_z_score > 2:
                        anomaly_type.append(f"revenue (z-score: {round(revenue_z_score, 2)})")
                    
                    anomalies.append({
                        "date": day["date"],
                        "type": ", ".join(anomaly_type),
                        "orders": day["orders"],
                        "revenue": day["revenue"],
                        "avg_order_value": day["avg_order_value"]
                    })
            
            # Calculate anomaly severity
            severity = "low" if len(anomalies) <= 2 else "medium" if len(anomalies) <= 5 else "high"
        else:
            anomalies = []
            severity = "none"
            avg_orders = 0
            avg_revenue = 0
            std_orders = 0
            std_revenue = 0
        
        return {
            "type": "anomaly_detection",
            "period": {
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "days_analyzed": days
            },
            "statistics": {
                "average_daily_orders": round(avg_orders, 2),
                "average_daily_revenue": round(avg_revenue, 2),
                "std_orders": round(std_orders, 2),
                "std_revenue": round(std_revenue, 2)
            },
            "anomalies": anomalies,
            "summary": {
                "total_anomalies": len(anomalies),
                "severity": severity,
                "recommendation": f"Investigate {len(anomalies)} anomalous days" if anomalies else "No significant anomalies detected"
            }
        }
    except Exception as e:
        logger.error(f"Error in get_anomaly_detection: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate anomaly detection analysis")

@router.get("/analytics/demand-forecasting")
async def get_demand_forecasting(
    days: int = Query(30, description="Number of days to forecast"),
    business_id: int = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """
    Future demand prediction.
    Forecasting of future demand patterns and trends.
    """
    try:
        # Current date
        current_date = datetime.now().date()
        
        # Get orders for the past 90 days for trend analysis
        historical_start = current_date - timedelta(days=90)
        orders = db.query(Order).filter(
            Order.business_id == business_id,
            Order.created_at >= historical_start,
            Order.created_at <= current_date + timedelta(days=1)
        ).all()
        
        # Group by day for trend analysis
        daily_orders = {}
        for order in orders:
            day_key = order.created_at.date()
            if day_key not in daily_orders:
                daily_orders[day_key] = 0
            daily_orders[day_key] += 1
        
        # Calculate trend factors
        if daily_orders:
            # Calculate average orders for different time periods
            last_7_days = [daily_orders.get(current_date - timedelta(days=i), 0) for i in range(7)]
            last_30_days = [daily_orders.get(current_date - timedelta(days=i), 0) for i in range(30)]
            
            avg_7_days = sum(last_7_days) / len(last_7_days) if last_7_days else 0
            avg_30_days = sum(last_30_days) / len(last_30_days) if last_30_days else 0
            
            # Trend calculation (positive = increasing, negative = decreasing)
            trend = (avg_7_days - avg_30_days) / avg_30_days * 100 if avg_30_days > 0 else 0
            
            # Simulate day-of-week patterns
            day_patterns = {}
            for order in orders:
                day_of_week = order.created_at.strftime("%A")  # Monday, Tuesday, etc.
                if day_of_week not in day_patterns:
                    day_patterns[day_of_week] = []
                day_patterns[day_of_week].append(1)  # Count orders
            
            # Calculate average orders by day of week
            avg_by_day = {day: sum(counts) / len(counts) for day, counts in day_patterns.items()}
            
            # Find peak and low days
            peak_day = max(avg_by_day, key=avg_by_day.get) if avg_by_day else "Unknown"
            low_day = min(avg_by_day, key=avg_by_day.get) if avg_by_day else "Unknown"
            
            # Generate forecast
            forecast = []
            base_demand = avg_7_days if avg_7_days > 0 else avg_30_days if avg_30_days > 0 else 10
            
            for i in range(1, days + 1):
                forecast_date = current_date + timedelta(days=i)
                day_of_week = forecast_date.strftime("%A")
                
                # Apply trend
                trend_multiplier = 1 + (trend / 100) * (i / 30)  # Scale trend over forecast period
                
                # Apply day-of-week pattern
                day_pattern = avg_by_day.get(day_of_week, base_demand) / base_demand if base_demand > 0 else 1
                
                # Calculate forecasted demand
                forecasted_demand = base_demand * trend_multiplier * day_pattern * random.uniform(0.8, 1.2)
                
                # Confidence decreases with forecast horizon
                confidence = max(50, 95 - (i * 1.5))  # Start at 95%, decrease by 1.5% per day
                
                forecast.append({
                    "date": forecast_date.strftime("%Y-%m-%d"),
                    "day_of_week": day_of_week,
                    "forecasted_orders": round(forecasted_demand),
                    "confidence": round(confidence, 2)
                })
            
            # High and low demand periods
            sorted_forecast = sorted(forecast, key=lambda x: x["forecasted_orders"])
            high_demand_periods = sorted_forecast[-5:]  # Top 5 days
            low_demand_periods = sorted_forecast[:5]   # Bottom 5 days
        else:
            forecast = []
            trend = 0
            peak_day = "Unknown"
            low_day = "Unknown"
            high_demand_periods = []
            low_demand_periods = []
        
        return {
            "type": "demand_forecasting",
            "period": {
                "historical_from": historical_start.strftime("%Y-%m-%d"),
                "historical_to": current_date.strftime("%Y-%m-%d"),
                "forecast_from": (current_date + timedelta(days=1)).strftime("%Y-%m-%d"),
                "forecast_to": (current_date + timedelta(days=days)).strftime("%Y-%m-%d"),
                "forecast_days": days
            },
            "trend_analysis": {
                "current_trend": round(trend, 2),
                "trend_direction": "increasing" if trend > 2 else "decreasing" if trend < -2 else "stable",
                "peak_day": peak_day,
                "low_day": low_day
            },
            "forecast": forecast,
            "demand_periods": {
                "high_demand": high_demand_periods,
                "low_demand": low_demand_periods
            },
            "recommendations": [
                f"Prepare for {trend:.1f}% trend in demand" if abs(trend) > 2 else "Maintain current staffing levels",
                f"Peak demand day is {peak_day}, consider additional resources",
                f"Low demand day is {low_day}, consider promotional activities"
            ]
        }
    except Exception as e:
        logger.error(f"Error in get_demand_forecasting: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate demand forecasting")

@router.get("/analytics/optimization-recommendations")
async def get_optimization_recommendations(
    business_id: int = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """
    AI improvement suggestions.
    AI-driven recommendations for business optimization.
    """
    try:
        # Current date
        current_date = datetime.now().date()
        
        # Get orders for the past 30 days
        start_date = current_date - timedelta(days=30)
        orders = db.query(Order).filter(
            Order.business_id == business_id,
            Order.created_at >= start_date,
            Order.created_at <= current_date + timedelta(days=1)
        ).all()
        
        # Calculate key metrics
        total_revenue = sum(order.total_amount for order in orders)
        total_orders = len(orders)
        avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
        
        # Customer metrics
        unique_customers = len(set(order.customer_id for order in orders if order.customer_id))
        repeat_customers = len([order for order in orders if order.customer_id and 
                              len([o for o in orders if o.customer_id == order.customer_id]) > 1])
        repeat_rate = (repeat_customers / unique_customers * 100) if unique_customers > 0 else 0
        
        # Time-based analysis
        peak_hours = {}
        for order in orders:
            hour = order.created_at.hour
            if hour not in peak_hours:
                peak_hours[hour] = 0
            peak_hours[hour] += 1
        
        busiest_hour = max(peak_hours, key=peak_hours.get) if peak_hours else 0
        
        # Payment method analysis
        payment_methods = {}
        for order in orders:
            method = getattr(order, 'payment_method', 'unknown')
            if method not in payment_methods:
                payment_methods[method] = 0
            payment_methods[method] += 1
        
        preferred_payment = max(payment_methods, key=payment_methods.get) if payment_methods else "unknown"
        
        # Generate AI-driven recommendations
        recommendations = []
        
        # Revenue-based recommendations
        if avg_order_value < 25:
            recommendations.append({
                "category": "pricing",
                "priority": "high",
                "recommendation": "Consider menu price optimization to increase average order value",
                "potential_impact": "10-20% increase in revenue"
            })
        elif avg_order_value > 50:
            recommendations.append({
                "category": "upselling",
                "priority": "medium",
                "recommendation": "Implement upselling strategies to maximize high-value customer spending",
                "potential_impact": "5-15% increase in revenue"
            })
        
        # Customer retention recommendations
        if repeat_rate < 30:
            recommendations.append({
                "category": "customer_retention",
                "priority": "high",
                "recommendation": "Implement customer loyalty program to improve retention rate",
                "potential_impact": "15-25% improvement in repeat customers"
            })
        elif repeat_rate > 50:
            recommendations.append({
                "category": "customer_retention",
                "priority": "low",
                "recommendation": "Maintain current customer retention strategies which are performing well",
                "potential_impact": "Sustain current retention levels"
            })
        
        # Operational recommendations
        if busiest_hour:
            recommendations.append({
                "category": "operations",
                "priority": "medium",
                "recommendation": f"Ensure adequate staffing during peak hour ({busiest_hour}:00) to optimize service quality",
                "potential_impact": "Improved customer satisfaction and reduced wait times"
            })
        
        # Technology recommendations
        recommendations.append({
            "category": "technology",
            "priority": "medium",
            "recommendation": "Consider implementing AI-powered inventory management to reduce waste",
            "potential_impact": "5-10% reduction in food costs"
        })
        
        # Marketing recommendations
        if preferred_payment and preferred_payment != "unknown":
            recommendations.append({
                "category": "marketing",
                "priority": "low",
                "recommendation": f"Promote payment method '{preferred_payment}' in marketing campaigns to improve conversion",
                "potential_impact": "2-5% increase in order conversion rate"
            })
        
        # Cost optimization recommendations
        recommendations.append({
            "category": "cost_optimization",
            "priority": "medium",
            "recommendation": "Analyze supplier contracts quarterly to identify cost-saving opportunities",
            "potential_impact": "3-8% reduction in operational costs"
        })
        
        return {
            "type": "optimization_recommendations",
            "period": {
                "analysis_from": start_date.strftime("%Y-%m-%d"),
                "analysis_to": current_date.strftime("%Y-%m-%d"),
                "days_analyzed": 30
            },
            "business_metrics": {
                "total_revenue": round(total_revenue, 2),
                "total_orders": total_orders,
                "average_order_value": round(avg_order_value, 2),
                "unique_customers": unique_customers,
                "repeat_customer_rate": round(repeat_rate, 2),
                "busiest_hour": busiest_hour,
                "preferred_payment_method": preferred_payment
            },
            "recommendations": recommendations,
            "summary": {
                "total_recommendations": len(recommendations),
                "high_priority": len([r for r in recommendations if r["priority"] == "high"]),
                "medium_priority": len([r for r in recommendations if r["priority"] == "medium"]),
                "low_priority": len([r for r in recommendations if r["priority"] == "low"])
            }
        }
    except Exception as e:
        logger.error(f"Error in get_optimization_recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate optimization recommendations")

@router.get("/analytics/scenario-planning")
async def get_scenario_planning(
    scenario: str = Query("growth", description="Scenario type: growth, downturn, expansion, cost_reduction"),
    business_id: int = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """
    What-if analysis.
    Scenario planning for different business situations.
    """
    try:
        # Current date
        current_date = datetime.now().date()
        
        # Get orders for the past 90 days
        start_date = current_date - timedelta(days=90)
        orders = db.query(Order).filter(
            Order.business_id == business_id,
            Order.created_at >= start_date,
            Order.created_at <= current_date + timedelta(days=1)
        ).all()
        
        # Calculate baseline metrics
        total_revenue = sum(order.total_amount for order in orders)
        total_orders = len(orders)
        avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
        unique_customers = len(set(order.customer_id for order in orders if order.customer_id))
        
        # Define scenarios
        scenarios = {
            "growth": {
                "description": "Business growth scenario with increased demand",
                "revenue_multiplier": 1.25,
                "customer_multiplier": 1.20,
                "order_multiplier": 1.15,
                "assumptions": [
                    "Market demand increases by 20-30%",
                    "Successful marketing campaigns",
                    "Positive customer reviews and word-of-mouth"
                ]
            },
            "downturn": {
                "description": "Economic downturn with decreased demand",
                "revenue_multiplier": 0.75,
                "customer_multiplier": 0.80,
                "order_multiplier": 0.85,
                "assumptions": [
                    "Economic recession affecting consumer spending",
                    "Increased competition in the market",
                    "Reduced foot traffic and customer visits"
                ]
            },
            "expansion": {
                "description": "Business expansion to new locations or services",
                "revenue_multiplier": 1.50,
                "customer_multiplier": 1.40,
                "order_multiplier": 1.30,
                "assumptions": [
                    "Successful launch of new location or service",
                    "Increased market reach and customer base",
                    "Additional revenue streams from new offerings"
                ]
            },
            "cost_reduction": {
                "description": "Cost reduction initiatives without revenue impact",
                "revenue_multiplier": 1.00,
                "customer_multiplier": 1.00,
                "order_multiplier": 1.00,
                "cost_reduction": 0.15,  # 15% cost reduction
                "assumptions": [
                    "Successful negotiation with suppliers",
                    "Operational efficiency improvements",
                    "Technology automation reducing labor costs"
                ]
            }
        }
        
        # Get selected scenario
        selected_scenario = scenarios.get(scenario, scenarios["growth"])
        
        # Calculate scenario outcomes
        scenario_revenue = total_revenue * selected_scenario["revenue_multiplier"]
        scenario_customers = unique_customers * selected_scenario["customer_multiplier"]
        scenario_orders = total_orders * selected_scenario["order_multiplier"]
        scenario_avg_order = scenario_revenue / scenario_orders if scenario_orders > 0 else avg_order_value
        
        # Calculate financial impact
        baseline_profit = total_revenue * 0.15  # Assuming 15% profit margin
        scenario_profit = scenario_revenue * (0.15 + (0 if scenario != "cost_reduction" else selected_scenario.get("cost_reduction", 0)))
        profit_impact = scenario_profit - baseline_profit
        
        # Resource requirements (simulated)
        resource_requirements = {
            "growth": {
                "additional_staff": 3,
                "marketing_investment": round(total_revenue * 0.10, 2),
                "inventory_increase": round(total_revenue * 0.20, 2)
            },
            "downturn": {
                "staff_reduction": 2,
                "marketing_reduction": round(total_revenue * 0.30, 2),
                "inventory_reduction": round(total_revenue * 0.25, 2)
            },
            "expansion": {
                "additional_staff": 8,
                "capital_investment": round(total_revenue * 0.50, 2),
                "marketing_investment": round(total_revenue * 0.20, 2)
            },
            "cost_reduction": {
                "technology_investment": round(total_revenue * 0.05, 2),
                "training_investment": round(total_revenue * 0.02, 2)
            }
        }
        
        requirements = resource_requirements.get(scenario, resource_requirements["growth"])
        
        # Risk assessment
        risk_levels = {
            "growth": "medium",
            "downturn": "high",
            "expansion": "high",
            "cost_reduction": "low"
        }
        
        risk_level = risk_levels.get(scenario, "medium")
        
        return {
            "type": "scenario_planning",
            "scenario": scenario,
            "description": selected_scenario["description"],
            "period": {
                "baseline_from": start_date.strftime("%Y-%m-%d"),
                "baseline_to": current_date.strftime("%Y-%m-%d"),
                "projection_period": "12 months"
            },
            "baseline_metrics": {
                "revenue": round(total_revenue, 2),
                "orders": total_orders,
                "customers": unique_customers,
                "avg_order_value": round(avg_order_value, 2),
                "profit": round(baseline_profit, 2)
            },
            "scenario_projection": {
                "revenue": round(scenario_revenue, 2),
                "orders": round(scenario_orders),
                "customers": round(scenario_customers),
                "avg_order_value": round(scenario_avg_order, 2),
                "profit": round(scenario_profit, 2)
            },
            "financial_impact": {
                "revenue_change": round(scenario_revenue - total_revenue, 2),
                "profit_change": round(profit_impact, 2),
                "percentage_change": round((scenario_profit - baseline_profit) / baseline_profit * 100, 2) if baseline_profit > 0 else 0
            },
            "resource_requirements": requirements,
            "assumptions": selected_scenario["assumptions"],
            "risk_assessment": {
                "level": risk_level,
                "mitigation_strategies": [
                    "Regular monitoring of key performance indicators",
                    "Flexible resource allocation based on actual performance",
                    "Contingency planning for adverse conditions"
                ]
            },
            "recommendations": [
                f"Monitor {scenario} scenario assumptions closely",
                "Establish key performance indicators to track scenario progress",
                "Prepare contingency plans for adverse outcomes"
            ]
        }
    except Exception as e:
        logger.error(f"Error in get_scenario_planning: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate scenario planning analysis")
