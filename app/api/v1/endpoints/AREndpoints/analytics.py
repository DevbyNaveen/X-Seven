"""Main Analytics Endpoints for business intelligence and reporting."""
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.core.dependencies import get_current_business
from app.models import (
    Business, Order, User, MenuItem, Table, 
    Appointment, ServiceProvider, WaitlistEntry, Message
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ====================
# SALES ANALYTICS
# ====================

@router.get("/analytics/sales")
async def get_sales_analytics(
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    business_id: int = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """
    Revenue analysis with date ranges.
    Provides comprehensive sales data including total revenue, order counts, and trends.
    """
    try:
        # Parse dates
        if start_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            start_dt = datetime.now() - timedelta(days=30)  # Default to last 30 days
            
        if end_date:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        else:
            end_dt = datetime.now() + timedelta(days=1)
        
        # Query sales data
        orders_query = db.query(Order).filter(
            Order.business_id == business_id,
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
            Order.status.in_(["completed", "confirmed"])
        )
        
        total_revenue = orders_query.with_entities(func.sum(Order.total_amount)).scalar() or 0
        total_orders = orders_query.count()
        avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
        
        # Daily revenue trend
        daily_revenue = orders_query.with_entities(
            func.date(Order.created_at).label('date'),
            func.sum(Order.total_amount).label('revenue'),
            func.count(Order.id).label('order_count')
        ).group_by(func.date(Order.created_at)).order_by('date').all()
        
        # Payment method distribution
        payment_methods = orders_query.with_entities(
            Order.payment_method,
            func.count(Order.id).label('count')
        ).group_by(Order.payment_method).all()
        
        return {
            "type": "sales_analytics",
            "period": {
                "start_date": start_dt.strftime("%Y-%m-%d"),
                "end_date": (end_dt - timedelta(days=1)).strftime("%Y-%m-%d")
            },
            "summary": {
                "total_revenue": round(total_revenue, 2),
                "total_orders": total_orders,
                "average_order_value": round(avg_order_value, 2),
                "revenue_trend": [
                    {
                        "date": str(row.date),
                        "revenue": round(row.revenue, 2),
                        "order_count": row.order_count
                    } for row in daily_revenue
                ]
            },
            "payment_methods": [
                {
                    "method": row.payment_method.value if row.payment_method else "unknown",
                    "count": row.count
                } for row in payment_methods
            ]
        }
    except Exception as e:
        logger.error(f"Error in get_sales_analytics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve sales analytics")

@router.get("/analytics/revenue-trends")
async def get_revenue_trends(
    period: str = Query("monthly", description="Period type: daily, weekly, monthly"),
    months: int = Query(6, description="Number of months to analyze"),
    business_id: int = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """
    Daily/weekly/monthly revenue patterns.
    Analyzes revenue trends over different time periods.
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30*months)
        
        # Base query
        orders_query = db.query(Order).filter(
            Order.business_id == business_id,
            Order.created_at >= start_date,
            Order.created_at <= end_date,
            Order.status.in_(["completed", "confirmed"])
        )
        
        if period == "daily":
            # Group by day
            revenue_data = orders_query.with_entities(
                func.date(Order.created_at).label('period'),
                func.sum(Order.total_amount).label('revenue'),
                func.count(Order.id).label('order_count')
            ).group_by(func.date(Order.created_at)).order_by('period').all()
        elif period == "weekly":
            # Group by week
            revenue_data = orders_query.with_entities(
                func.year(Order.created_at).label('year'),
                func.week(Order.created_at).label('week'),
                func.sum(Order.total_amount).label('revenue'),
                func.count(Order.id).label('order_count')
            ).group_by(func.year(Order.created_at), func.week(Order.created_at)).order_by('year', 'week').all()
        else:  # monthly
            # Group by month
            revenue_data = orders_query.with_entities(
                func.year(Order.created_at).label('year'),
                func.month(Order.created_at).label('month'),
                func.sum(Order.total_amount).label('revenue'),
                func.count(Order.id).label('order_count')
            ).group_by(func.year(Order.created_at), func.month(Order.created_at)).order_by('year', 'month').all()
        
        # Calculate growth rates
        trends = []
        for i, row in enumerate(revenue_data):
            revenue = round(row.revenue, 2) if row.revenue else 0
            order_count = row.order_count if row.order_count else 0
            
            # Calculate growth rate
            growth_rate = 0
            if i > 0 and revenue_data[i-1].revenue and revenue_data[i-1].revenue > 0:
                growth_rate = ((revenue - revenue_data[i-1].revenue) / revenue_data[i-1].revenue) * 100
            
            if period == "daily":
                period_label = str(row.period)
            elif period == "weekly":
                period_label = f"{row.year}-W{row.week}"
            else:  # monthly
                period_label = f"{row.year}-{row.month:02d}"
            
            trends.append({
                "period": period_label,
                "revenue": revenue,
                "order_count": order_count,
                "growth_rate": round(growth_rate, 2)
            })
        
        return {
            "type": "revenue_trends",
            "period_type": period,
            "data": trends
        }
    except Exception as e:
        logger.error(f"Error in get_revenue_trends: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve revenue trends")

@router.get("/analytics/transaction-volume")
async def get_transaction_volume(
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    business_id: int = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """
    Order/appointment/service count analysis.
    Analyzes transaction volume across different service types.
    """
    try:
        # Parse dates
        if start_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            start_dt = datetime.now() - timedelta(days=30)
            
        if end_date:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        else:
            end_dt = datetime.now() + timedelta(days=1)
        
        # Order volume
        orders_query = db.query(Order).filter(
            Order.business_id == business_id,
            Order.created_at >= start_dt,
            Order.created_at <= end_dt
        )
        
        total_orders = orders_query.count()
        
        # Order types
        order_types = orders_query.with_entities(
            Order.order_type,
            func.count(Order.id).label('count')
        ).group_by(Order.order_type).all()
        
        # Appointment volume
        appointments_query = db.query(Appointment).filter(
            Appointment.business_id == business_id,
            Appointment.created_at >= start_dt,
            Appointment.created_at <= end_dt
        )
        
        total_appointments = appointments_query.count()
        
        # Appointment statuses
        appointment_statuses = appointments_query.with_entities(
            Appointment.status,
            func.count(Appointment.id).label('count')
        ).group_by(Appointment.status).all()
        
        # Waitlist entries
        waitlist_query = db.query(WaitlistEntry).filter(
            WaitlistEntry.business_id == business_id,
            WaitlistEntry.created_at >= start_dt,
            WaitlistEntry.created_at <= end_dt
        )
        
        total_waitlist_entries = waitlist_query.count()
        
        return {
            "type": "transaction_volume",
            "period": {
                "start_date": start_dt.strftime("%Y-%m-%d"),
                "end_date": (end_dt - timedelta(days=1)).strftime("%Y-%m-%d")
            },
            "orders": {
                "total": total_orders,
                "by_type": [
                    {
                        "type": row.order_type,
                        "count": row.count
                    } for row in order_types
                ]
            },
            "appointments": {
                "total": total_appointments,
                "by_status": [
                    {
                        "status": row.status.value if row.status else "unknown",
                        "count": row.count
                    } for row in appointment_statuses
                ]
            },
            "waitlist": {
                "total": total_waitlist_entries
            }
        }
    except Exception as e:
        logger.error(f"Error in get_transaction_volume: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve transaction volume analytics")

@router.get("/analytics/average-value")
async def get_average_transaction_value(
    period: str = Query("monthly", description="Period type: daily, weekly, monthly"),
    months: int = Query(6, description="Number of months to analyze"),
    business_id: int = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """
    Average transaction value trends.
    Tracks changes in average transaction value over time.
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30*months)
        
        # Base query
        orders_query = db.query(Order).filter(
            Order.business_id == business_id,
            Order.created_at >= start_date,
            Order.created_at <= end_date,
            Order.status.in_(["completed", "confirmed"])
        )
        
        if period == "daily":
            # Group by day
            avg_value_data = orders_query.with_entities(
                func.date(Order.created_at).label('period'),
                func.avg(Order.total_amount).label('avg_value'),
                func.count(Order.id).label('order_count')
            ).group_by(func.date(Order.created_at)).order_by('period').all()
        elif period == "weekly":
            # Group by week
            avg_value_data = orders_query.with_entities(
                func.year(Order.created_at).label('year'),
                func.week(Order.created_at).label('week'),
                func.avg(Order.total_amount).label('avg_value'),
                func.count(Order.id).label('order_count')
            ).group_by(func.year(Order.created_at), func.week(Order.created_at)).order_by('year', 'week').all()
        else:  # monthly
            # Group by month
            avg_value_data = orders_query.with_entities(
                func.year(Order.created_at).label('year'),
                func.month(Order.created_at).label('month'),
                func.avg(Order.total_amount).label('avg_value'),
                func.count(Order.id).label('order_count')
            ).group_by(func.year(Order.created_at), func.month(Order.created_at)).order_by('year', 'month').all()
        
        # Calculate trends
        trends = []
        overall_avg = 0
        total_orders = 0
        
        for row in avg_value_data:
            avg_value = round(row.avg_value, 2) if row.avg_value else 0
            order_count = row.order_count if row.order_count else 0
            
            if period == "daily":
                period_label = str(row.period)
            elif period == "weekly":
                period_label = f"{row.year}-W{row.week}"
            else:  # monthly
                period_label = f"{row.year}-{row.month:02d}"
            
            trends.append({
                "period": period_label,
                "average_value": avg_value,
                "order_count": order_count
            })
            
            overall_avg += avg_value * order_count
            total_orders += order_count
        
        overall_avg = round(overall_avg / total_orders, 2) if total_orders > 0 else 0
        
        return {
            "type": "average_transaction_value",
            "period_type": period,
            "overall_average": overall_avg,
            "data": trends
        }
    except Exception as e:
        logger.error(f"Error in get_average_transaction_value: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve average transaction value analytics")

@router.get("/analytics/payment-methods")
async def get_payment_methods_distribution(
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    business_id: int = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """
    Payment type distribution.
    Shows distribution of payment methods used across transactions.
    """
    try:
        # Parse dates
        if start_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            start_dt = datetime.now() - timedelta(days=90)
            
        if end_date:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        else:
            end_dt = datetime.now() + timedelta(days=1)
        
        # Query orders with payment methods
        orders_query = db.query(Order).filter(
            Order.business_id == business_id,
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
            Order.status.in_(["completed", "confirmed"]),
            Order.payment_method.isnot(None)
        )
        
        total_orders = orders_query.count()
        
        # Payment method distribution
        payment_methods = orders_query.with_entities(
            Order.payment_method,
            func.count(Order.id).label('count')
        ).group_by(Order.payment_method).all()
        
        # Calculate percentages
        distribution = []
        for row in payment_methods:
            count = row.count
            percentage = (count / total_orders * 100) if total_orders > 0 else 0
            
            distribution.append({
                "method": row.payment_method.value if row.payment_method else "unknown",
                "count": count,
                "percentage": round(percentage, 2)
            })
        
        # Sort by count descending
        distribution.sort(key=lambda x: x['count'], reverse=True)
        
        return {
            "type": "payment_methods_distribution",
            "period": {
                "start_date": start_dt.strftime("%Y-%m-%d"),
                "end_date": (end_dt - timedelta(days=1)).strftime("%Y-%m-%d")
            },
            "total_transactions": total_orders,
            "distribution": distribution
        }
    except Exception as e:
        logger.error(f"Error in get_payment_methods_distribution: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve payment methods distribution")

# ====================
# CUSTOMER ANALYTICS
# ====================

@router.get("/analytics/customer-behavior")
async def get_customer_behavior(
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    business_id: int = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """
    Customer visit patterns and preferences.
    Analyzes customer behavior including visit frequency and preferences.
    """
    try:
        # Parse dates
        if start_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            start_dt = datetime.now() - timedelta(days=90)
            
        if end_date:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        else:
            end_dt = datetime.now() + timedelta(days=1)
        
        # Get customers who made orders in this period
        customers_query = db.query(Order.customer_id).filter(
            Order.business_id == business_id,
            Order.customer_id.isnot(None),
            Order.created_at >= start_dt,
            Order.created_at <= end_dt
        ).distinct()
        
        customer_ids = [row.customer_id for row in customers_query.all()]
        
        # Visit frequency analysis
        visit_frequency = {}
        customer_segments = {
            "new": 0,
            "regular": 0,
            "frequent": 0,
            "vip": 0
        }
        
        for customer_id in customer_ids:
            # Count visits in period
            visit_count = db.query(Order).filter(
                Order.business_id == business_id,
                Order.customer_id == customer_id,
                Order.created_at >= start_dt,
                Order.created_at <= end_dt
            ).count()
            
            visit_frequency[customer_id] = visit_count
            
            # Segment customers
            if visit_count == 1:
                customer_segments["new"] += 1
            elif visit_count <= 3:
                customer_segments["regular"] += 1
            elif visit_count <= 10:
                customer_segments["frequent"] += 1
            else:
                customer_segments["vip"] += 1
        
        # Preferred order types
        order_types = db.query(Order.order_type, func.count(Order.id).label('count')).filter(
            Order.business_id == business_id,
            Order.customer_id.isnot(None),
            Order.created_at >= start_dt,
            Order.created_at <= end_dt
        ).group_by(Order.order_type).order_by(func.count(Order.id).desc()).all()
        
        # Preferred time slots (hourly)
        time_slots = db.query(
            func.hour(Order.created_at).label('hour'),
            func.count(Order.id).label('count')
        ).filter(
            Order.business_id == business_id,
            Order.customer_id.isnot(None),
            Order.created_at >= start_dt,
            Order.created_at <= end_dt
        ).group_by(func.hour(Order.created_at)).order_by('hour').all()
        
        return {
            "type": "customer_behavior",
            "period": {
                "start_date": start_dt.strftime("%Y-%m-%d"),
                "end_date": (end_dt - timedelta(days=1)).strftime("%Y-%m-%d")
            },
            "customer_segments": customer_segments,
            "order_type_preferences": [
                {
                    "type": row.order_type,
                    "count": row.count
                } for row in order_types
            ],
            "time_slot_preferences": [
                {
                    "hour": row.hour,
                    "count": row.count
                } for row in time_slots
            ]
        }
    except Exception as e:
        logger.error(f"Error in get_customer_behavior: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve customer behavior analytics")

@router.get("/analytics/customer-retention")
async def get_customer_retention(
    months: int = Query(6, description="Number of months to analyze for retention"),
    business_id: int = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """
    Repeat customer rates and loyalty.
    Measures customer retention and identifies loyal customers.
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30*months)
        
        # Get all customers who made orders in the period
        all_customers = db.query(Order.customer_id).filter(
            Order.business_id == business_id,
            Order.customer_id.isnot(None),
            Order.created_at >= start_date,
            Order.created_at <= end_date
        ).distinct().count()
        
        # Get customers who made orders in both first and last quarters
        first_quarter_end = start_date + timedelta(days=30*months//2)
        last_quarter_start = first_quarter_end
        
        first_quarter_customers = set([
            row.customer_id for row in db.query(Order.customer_id).filter(
                Order.business_id == business_id,
                Order.customer_id.isnot(None),
                Order.created_at >= start_date,
                Order.created_at <= first_quarter_end
            ).distinct().all()
        ])
        
        last_quarter_customers = set([
            row.customer_id for row in db.query(Order.customer_id).filter(
                Order.business_id == business_id,
                Order.customer_id.isnot(None),
                Order.created_at >= last_quarter_start,
                Order.created_at <= end_date
            ).distinct().all()
        ])
        
        # Calculate retention rate
        retained_customers = len(first_quarter_customers.intersection(last_quarter_customers))
        retention_rate = (retained_customers / len(first_quarter_customers) * 100) if len(first_quarter_customers) > 0 else 0
        
        # Identify loyal customers (5+ visits)
        loyal_customers_query = db.query(
            Order.customer_id,
            func.count(Order.id).label('visit_count')
        ).filter(
            Order.business_id == business_id,
            Order.customer_id.isnot(None),
            Order.created_at >= start_date,
            Order.created_at <= end_date
        ).group_by(Order.customer_id).having(func.count(Order.id) >= 5).all()
        
        loyal_customers_count = len(loyal_customers_query)
        
        return {
            "type": "customer_retention",
            "period": {
                "months": months,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d")
            },
            "metrics": {
                "total_customers": all_customers,
                "retained_customers": retained_customers,
                "retention_rate": round(retention_rate, 2),
                "loyal_customers": loyal_customers_count,
                "loyalty_rate": round((loyal_customers_count / all_customers * 100) if all_customers > 0 else 0, 2)
            },
            "loyal_customers_list": [
                {
                    "customer_id": row.customer_id,
                    "visit_count": row.visit_count
                } for row in loyal_customers_query[:10]  # Top 10
            ]
        }
    except Exception as e:
        logger.error(f"Error in get_customer_retention: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve customer retention analytics")

@router.get("/analytics/customer-lifetime-value")
async def get_customer_lifetime_value(
    months: int = Query(12, description="Number of months to calculate CLV"),
    business_id: int = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """
    CLV calculation and segmentation.
    Calculates Customer Lifetime Value and segments customers accordingly.
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30*months)
        
        # Calculate CLV for each customer
        customer_clv_query = db.query(
            Order.customer_id,
            func.count(Order.id).label('order_count'),
            func.sum(Order.total_amount).label('total_spent'),
            func.avg(Order.total_amount).label('avg_order_value'),
            func.min(Order.created_at).label('first_order'),
            func.max(Order.created_at).label('last_order')
        ).filter(
            Order.business_id == business_id,
            Order.customer_id.isnot(None),
            Order.created_at >= start_date,
            Order.created_at <= end_date,
            Order.status.in_(["completed", "confirmed"])
        ).group_by(Order.customer_id).all()
        
        # Process CLV data
        clv_data = []
        total_clv = 0
        
        for row in customer_clv_query:
            # Calculate customer lifespan in months
            lifespan = (row.last_order - row.first_order).days / 30
            lifespan = max(lifespan, 1)  # Minimum 1 month
            
            # Calculate purchase frequency
            purchase_frequency = row.order_count / lifespan
            
            # Simple CLV formula: Average Order Value × Purchase Frequency × Customer Lifespan
            # For this example, we'll use a fixed lifespan of 24 months
            clv = (row.total_spent / row.order_count if row.order_count > 0 else 0) * purchase_frequency * 24
            
            clv_data.append({
                "customer_id": row.customer_id,
                "order_count": row.order_count,
                "total_spent": round(row.total_spent, 2) if row.total_spent else 0,
                "avg_order_value": round(row.avg_order_value, 2) if row.avg_order_value else 0,
                "customer_lifespan_months": round(lifespan, 2),
                "purchase_frequency": round(purchase_frequency, 2),
                "clv": round(clv, 2)
            })
            
            total_clv += clv
        
        # Segment customers by CLV
        clv_data.sort(key=lambda x: x['clv'], reverse=True)
        
        high_value = [c for c in clv_data if c['clv'] >= 500]
        medium_value = [c for c in clv_data if 100 <= c['clv'] < 500]
        low_value = [c for c in clv_data if c['clv'] < 100]
        
        avg_clv = total_clv / len(clv_data) if clv_data else 0
        
        return {
            "type": "customer_lifetime_value",
            "period": {
                "months": months,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d")
            },
            "summary": {
                "total_customers": len(clv_data),
                "average_clv": round(avg_clv, 2),
                "total_clv": round(total_clv, 2)
            },
            "segments": {
                "high_value": {
                    "count": len(high_value),
                    "percentage": round(len(high_value) / len(clv_data) * 100, 2) if clv_data else 0,
                    "customers": high_value[:10]  # Top 10
                },
                "medium_value": {
                    "count": len(medium_value),
                    "percentage": round(len(medium_value) / len(clv_data) * 100, 2) if clv_data else 0,
                    "customers": medium_value[:10]  # Top 10
                },
                "low_value": {
                    "count": len(low_value),
                    "percentage": round(len(low_value) / len(clv_data) * 100, 2) if clv_data else 0,
                    "customers": low_value[:10]  # Top 10
                }
            }
        }
    except Exception as e:
        logger.error(f"Error in get_customer_lifetime_value: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve customer lifetime value analytics")

@router.get("/analytics/customer-acquisition")
async def get_customer_acquisition(
    months: int = Query(6, description="Number of months to analyze"),
    business_id: int = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """
    New vs returning customer analysis.
    Analyzes customer acquisition and retention patterns.
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30*months)
        
        # Monthly breakdown
        monthly_data = []
        
        for i in range(months):
            month_start = start_date + timedelta(days=30*i)
            month_end = month_start + timedelta(days=30)
            
            # Get all customers in this month
            month_customers = db.query(Order.customer_id).filter(
                Order.business_id == business_id,
                Order.customer_id.isnot(None),
                Order.created_at >= month_start,
                Order.created_at <= month_end
            ).distinct().all()
            
            month_customer_ids = [row.customer_id for row in month_customers]
            
            # Get customers who had orders before this month (returning)
            returning_customers = db.query(Order.customer_id).filter(
                Order.business_id == business_id,
                Order.customer_id.in_(month_customer_ids),
                Order.created_at < month_start
            ).distinct().count()
            
            # New customers are those who didn't have orders before
            new_customers = len(month_customer_ids) - returning_customers
            
            monthly_data.append({
                "month": month_start.strftime("%Y-%m"),
                "new_customers": new_customers,
                "returning_customers": returning_customers,
                "total_customers": len(month_customer_ids),
                "acquisition_rate": round((new_customers / len(month_customer_ids) * 100) if len(month_customer_ids) > 0 else 0, 2)
            })
        
        # Overall metrics
        total_new = sum(m['new_customers'] for m in monthly_data)
        total_returning = sum(m['returning_customers'] for m in monthly_data)
        total_customers = total_new + total_returning
        
        return {
            "type": "customer_acquisition",
            "period": {
                "months": months,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d")
            },
            "summary": {
                "total_new_customers": total_new,
                "total_returning_customers": total_returning,
                "total_customers": total_customers,
                "new_customer_rate": round((total_new / total_customers * 100) if total_customers > 0 else 0, 2)
            },
            "monthly_trends": monthly_data
        }
    except Exception as e:
        logger.error(f"Error in get_customer_acquisition: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve customer acquisition analytics")

@router.get("/analytics/customer-satisfaction")
async def get_customer_satisfaction(
    months: int = Query(6, description="Number of months to analyze"),
    business_id: int = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """
    Feedback scores and sentiment.
    Measures customer satisfaction through various feedback metrics.
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30*months)
        
        # For this example, we'll simulate feedback data
        # In a real implementation, this would come from actual feedback/survey data
        
        # Simulate feedback scores (1-5 scale)
        feedback_scores = [
            {"score": 5, "count": 120},
            {"score": 4, "count": 85},
            {"score": 3, "count": 45},
            {"score": 2, "count": 20},
            {"score": 1, "count": 10}
        ]
        
        total_feedback = sum(score['count'] for score in feedback_scores)
        
        # Calculate average score
        weighted_sum = sum(score['score'] * score['count'] for score in feedback_scores)
        avg_score = weighted_sum / total_feedback if total_feedback > 0 else 0
        
        # Calculate satisfaction rate (4-5 stars)
        positive_feedback = sum(score['count'] for score in feedback_scores if score['score'] >= 4)
        satisfaction_rate = (positive_feedback / total_feedback * 100) if total_feedback > 0 else 0
        
        # Net Promoter Score (NPS) simulation
        # NPS = % of promoters (score 9-10) - % of detractors (score 0-6)
        promoters = sum(score['count'] for score in feedback_scores if score['score'] >= 9)
        detractors = sum(score['count'] for score in feedback_scores if score['score'] <= 6)
        nps = ((promoters - detractors) / total_feedback * 100) if total_feedback > 0 else 0
        
        return {
            "type": "customer_satisfaction",
            "period": {
                "months": months,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d")
            },
            "metrics": {
                "total_feedback": total_feedback,
                "average_score": round(avg_score, 2),
                "satisfaction_rate": round(satisfaction_rate, 2),
                "nps": round(nps, 2)
            },
            "score_distribution": feedback_scores
        }
    except Exception as e:
        logger.error(f"Error in get_customer_satisfaction: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve customer satisfaction analytics")

# =======================
# PERFORMANCE ANALYTICS
# =======================

@router.get("/analytics/peak-hours")
async def get_peak_hours(
    days: int = Query(30, description="Number of days to analyze"),
    business_id: int = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """
    Busiest times and staffing needs.
    Identifies peak hours for better resource allocation.
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Hourly order counts
        hourly_orders = db.query(
            func.hour(Order.created_at).label('hour'),
            func.count(Order.id).label('order_count')
        ).filter(
            Order.business_id == business_id,
            Order.created_at >= start_date,
            Order.created_at <= end_date
        ).group_by(func.hour(Order.created_at)).order_by('hour').all()
        
        # Peak hours (top 5 busiest hours)
        peak_hours = sorted(hourly_orders, key=lambda x: x.order_count, reverse=True)[:5]
        
        return {
            "type": "peak_hours",
            "period": {
                "days": days,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d")
            },
            "hourly_distribution": [
                {
                    "hour": row.hour,
                    "order_count": row.order_count
                } for row in hourly_orders
            ],
            "peak_hours": [
                {
                    "hour": row.hour,
                    "order_count": row.order_count
                } for row in peak_hours
            ]
        }
    except Exception as e:
        logger.error(f"Error in get_peak_hours: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve peak hours analytics")

@router.get("/analytics/service-performance")
async def get_service_performance(
    days: int = Query(30, description="Number of days to analyze"),
    business_id: int = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """
    Order processing times and efficiency.
    Measures service performance and identifies bottlenecks.
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Average preparation time (difference between created and completed)
        completed_orders = db.query(Order).filter(
            Order.business_id == business_id,
            Order.status == "completed",
            Order.created_at >= start_date,
            Order.created_at <= end_date
        ).all()
        
        prep_times = []
        for order in completed_orders:
            if order.created_at and order.updated_at:
                prep_time = (order.updated_at - order.created_at).total_seconds() / 60  # in minutes
                prep_times.append(prep_time)
        
        avg_prep_time = sum(prep_times) / len(prep_times) if prep_times else 0
        
        # Order status distribution
        status_distribution = db.query(
            Order.status,
            func.count(Order.id).label('count')
        ).filter(
            Order.business_id == business_id,
            Order.created_at >= start_date,
            Order.created_at <= end_date
        ).group_by(Order.status).all()
        
        # Orders per day trend
        daily_orders = db.query(
            func.date(Order.created_at).label('date'),
            func.count(Order.id).label('order_count')
        ).filter(
            Order.business_id == business_id,
            Order.created_at >= start_date,
            Order.created_at <= end_date
        ).group_by(func.date(Order.created_at)).order_by('date').all()
        
        return {
            "type": "service_performance",
            "period": {
                "days": days,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d")
            },
            "metrics": {
                "average_preparation_time_minutes": round(avg_prep_time, 2),
                "total_orders": len(completed_orders),
                "status_distribution": [
                    {
                        "status": row.status,
                        "count": row.count
                    } for row in status_distribution
                ]
            },
            "daily_trend": [
                {
                    "date": row.date.strftime("%Y-%m-%d"),
                    "order_count": row.order_count
                } for row in daily_orders
            ]
        }
    except Exception as e:
        logger.error(f"Error in get_service_performance: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve service performance analytics")

@router.get("/analytics/staff-productivity")
async def get_staff_productivity(
    days: int = Query(30, description="Number of days to analyze"),
    business_id: int = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """
    Staff performance and task completion.
    Analyzes staff productivity and task completion rates.
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # For this example, we'll simulate staff productivity data
        # In a real implementation, this would come from actual staff/task tracking data
        
        # Simulate staff members
        staff_members = [
            {"id": 1, "name": "John Smith", "tasks_completed": 120, "hours_worked": 40},
            {"id": 2, "name": "Jane Doe", "tasks_completed": 95, "hours_worked": 35},
            {"id": 3, "name": "Mike Johnson", "tasks_completed": 110, "hours_worked": 42},
            {"id": 4, "name": "Sarah Wilson", "tasks_completed": 85, "hours_worked": 30}
        ]
        
        # Calculate productivity metrics
        for staff in staff_members:
            staff["tasks_per_hour"] = round(staff["tasks_completed"] / staff["hours_worked"], 2) if staff["hours_worked"] > 0 else 0
            
        # Sort by productivity
        staff_members.sort(key=lambda x: x['tasks_per_hour'], reverse=True)
        
        # Overall metrics
        total_tasks = sum(staff['tasks_completed'] for staff in staff_members)
        total_hours = sum(staff['hours_worked'] for staff in staff_members)
        avg_productivity = total_tasks / total_hours if total_hours > 0 else 0
        
        return {
            "type": "staff_productivity",
            "period": {
                "days": days,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d")
            },
            "summary": {
                "total_staff": len(staff_members),
                "total_tasks_completed": total_tasks,
                "total_hours_worked": total_hours,
                "average_productivity_tasks_per_hour": round(avg_productivity, 2)
            },
            "staff_performance": staff_members
        }
    except Exception as e:
        logger.error(f"Error in get_staff_productivity: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve staff productivity analytics")

@router.get("/analytics/conversion-rates")
async def get_conversion_rates(
    days: int = Query(30, description="Number of days to analyze"),
    business_id: int = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """
    Visitor-to-customer conversion tracking.
    Tracks conversion rates from visitors to customers.
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # For this example, we'll simulate conversion data
        # In a real implementation, this would come from actual visitor/customer tracking data
        
        # Simulate daily visitor and customer data
        daily_data = []
        total_visitors = 0
        total_customers = 0
        
        # Generate data for each day
        for i in range(days):
            day = start_date + timedelta(days=i)
            visitors = random.randint(80, 200)  # Random visitors per day
            conversion_rate = random.uniform(0.15, 0.35)  # 15-35% conversion rate
            customers = int(visitors * conversion_rate)
            
            daily_data.append({
                "date": day.strftime("%Y-%m-%d"),
                "visitors": visitors,
                "customers": customers,
                "conversion_rate": round(conversion_rate * 100, 2)
            })
            
            total_visitors += visitors
            total_customers += customers
        
        # Overall conversion rate
        overall_conversion_rate = (total_customers / total_visitors * 100) if total_visitors > 0 else 0
        
        # Best and worst performing days
        best_day = max(daily_data, key=lambda x: x['conversion_rate'])
        worst_day = min(daily_data, key=lambda x: x['conversion_rate'])
        
        return {
            "type": "conversion_rates",
            "period": {
                "days": days,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d")
            },
            "summary": {
                "total_visitors": total_visitors,
                "total_customers": total_customers,
                "overall_conversion_rate": round(overall_conversion_rate, 2)
            },
            "daily_trends": daily_data[-7:],  # Last 7 days
            "best_day": best_day,
            "worst_day": worst_day
        }
    except Exception as e:
        logger.error(f"Error in get_conversion_rates: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve conversion rates analytics")

@router.get("/analytics/capacity-utilization")
async def get_capacity_utilization(
    days: int = Query(30, description="Number of days to analyze"),
    business_id: int = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """
    Resource usage and optimization opportunities.
    Measures capacity utilization and identifies optimization opportunities.
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # For this example, we'll simulate capacity utilization data
        # In a real implementation, this would come from actual resource tracking data
        
        # Simulate capacity data
        total_capacity = 200  # Total capacity (e.g., seats, tables, etc.)
        
        # Get daily order counts
        daily_orders = db.query(
            func.date(Order.created_at).label('date'),
            func.count(Order.id).label('order_count')
        ).filter(
            Order.business_id == business_id,
            Order.created_at >= start_date,
            Order.created_at <= end_date
        ).group_by(func.date(Order.created_at)).order_by('date').all()
        
        # Calculate utilization rates
        utilization_data = []
        total_utilization = 0
        
        for row in daily_orders:
            utilization_rate = (row.order_count / total_capacity * 100) if total_capacity > 0 else 0
            utilization_data.append({
                "date": row.date.strftime("%Y-%m-%d"),
                "orders": row.order_count,
                "utilization_rate": round(utilization_rate, 2)
            })
            total_utilization += utilization_rate
        
        # Average utilization
        avg_utilization = total_utilization / len(utilization_data) if utilization_data else 0
        
        # Peak utilization day
        peak_utilization = max(utilization_data, key=lambda x: x['utilization_rate']) if utilization_data else None
        
        # Underutilized periods (below 50% utilization)
        underutilized_days = [day for day in utilization_data if day['utilization_rate'] < 50]
        
        return {
            "type": "capacity_utilization",
            "period": {
                "days": days,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d")
            },
            "metrics": {
                "total_capacity": total_capacity,
                "average_utilization_rate": round(avg_utilization, 2),
                "peak_utilization_day": peak_utilization,
                "underutilized_days_count": len(underutilized_days)
            },
            "daily_utilization": utilization_data[-7:],  # Last 7 days
            "underutilized_periods": underutilized_days[:5]  # First 5 underutilized days
        }
    except Exception as e:
        logger.error(f"Error in get_capacity_utilization: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve capacity utilization analytics")
