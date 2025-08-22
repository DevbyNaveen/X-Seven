"""Enhanced analytics endpoints for predictive customer analytics."""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timedelta

from app.core.dependencies import get_db, get_current_business
from app.models import Business
from app.services.ai.analytics_engine import AnalyticsEngine, TimeRange
from app.services.notifications.notification_service import NotificationService

router = APIRouter()


class CustomerChurnRisk(BaseModel):
    """Customer churn risk analysis."""
    phone: str
    last_order_date: str
    days_since_last_order: int
    total_orders: int
    total_spent: float
    average_order_value: float
    churn_risk_score: float
    risk_level: str


class NextOrderPrediction(BaseModel):
    """Next order prediction for a customer."""
    predicted_items: List[Dict[str, Any]]
    confidence: float
    predicted_time: Dict[str, Any]
    order_frequency_days: float


class PersonalizedRecommendation(BaseModel):
    """Personalized recommendation for a customer."""
    item_id: int
    name: str
    description: str
    price: float
    score: float
    reason: str


class CustomerRecommendations(BaseModel):
    """Customer recommendations response."""
    recommendations: List[PersonalizedRecommendation]
    reasoning: str
    preferences: Dict[str, Any]


@router.get("/dashboard")
async def get_business_dashboard(
    time_range: TimeRange = Query(TimeRange.DAY, description="Time range for analytics"),
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
):
    """Get comprehensive business dashboard with predictive analytics."""
    try:
        analytics_engine = AnalyticsEngine(db)
        dashboard_data = await analytics_engine.get_business_dashboard(
            business_id=business.id,
            time_range=time_range
        )
        
        return dashboard_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard: {str(e)}")


@router.get("/churn-risk", response_model=List[CustomerChurnRisk])
async def get_customer_churn_risk(
    limit: int = Query(50, description="Number of customers to analyze"),
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
):
    """Get customers at risk of churning."""
    try:
        analytics_engine = AnalyticsEngine(db)
        churn_risk_customers = await analytics_engine.analyze_customer_churn_risk(
            business_id=business.id
        )
        
        # Limit results
        churn_risk_customers = churn_risk_customers[:limit]
        
        return [
            CustomerChurnRisk(
                phone=customer["phone"],
                last_order_date=customer["last_order_date"],
                days_since_last_order=customer["days_since_last_order"],
                total_orders=customer["total_orders"],
                total_spent=customer["total_spent"],
                average_order_value=customer["average_order_value"],
                churn_risk_score=customer["churn_risk_score"],
                risk_level=customer["risk_level"]
            )
            for customer in churn_risk_customers
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze churn risk: {str(e)}")


@router.get("/predict-next-order/{customer_phone}", response_model=NextOrderPrediction)
async def predict_next_order(
    customer_phone: str,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
):
    """Predict customer's next likely order."""
    try:
        analytics_engine = AnalyticsEngine(db)
        prediction = await analytics_engine.predict_next_order(
            customer_phone=customer_phone,
            business_id=business.id
        )
        
        return NextOrderPrediction(
            predicted_items=prediction["predicted_items"],
            confidence=prediction["confidence"],
            predicted_time=prediction["predicted_time"],
            order_frequency_days=prediction["order_frequency_days"]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to predict next order: {str(e)}")


@router.get("/recommendations/{customer_phone}", response_model=CustomerRecommendations)
async def get_personalized_recommendations(
    customer_phone: str,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
):
    """Get personalized recommendations for a customer."""
    try:
        analytics_engine = AnalyticsEngine(db)
        recommendations_data = await analytics_engine.generate_personalized_recommendations(
            customer_phone=customer_phone,
            business_id=business.id
        )
        
        recommendations = [
            PersonalizedRecommendation(
                item_id=rec["item_id"],
                name=rec["name"],
                description=rec["description"],
                price=rec["price"],
                score=rec["score"],
                reason=rec["reason"]
            )
            for rec in recommendations_data["recommendations"]
        ]
        
        return CustomerRecommendations(
            recommendations=recommendations,
            reasoning=recommendations_data["reasoning"],
            preferences=recommendations_data["preferences"]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")


@router.post("/send-churn-prevention")
async def send_churn_prevention_message(
    customer_phone: str,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
):
    """Send churn prevention message to a customer."""
    try:
        # Get customer info
        from app.models import Order
        
        customer_orders = db.query(Order).filter(
            Order.business_id == business.id,
            Order.customer_phone == customer_phone
        ).order_by(Order.created_at.desc()).all()
        
        if not customer_orders:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        # Calculate days since last order
        last_order_date = customer_orders[0].created_at
        days_since_last_order = (datetime.now() - last_order_date).days
        
        # Get customer name
        customer_name = customer_orders[0].customer_name or "Valued Customer"
        
        # Get usual order
        analytics_engine = AnalyticsEngine(db)
        prediction = await analytics_engine.predict_next_order(
            customer_phone=customer_phone,
            business_id=business.id
        )
        
        usual_order = prediction if prediction["predicted_items"] else None
        
        # Send churn prevention message
        notification_service = NotificationService(db)
        success = await notification_service.send_churn_prevention_message(
            customer_phone=customer_phone,
            customer_name=customer_name,
            business_name=business.name,
            days_since_last_order=days_since_last_order,
            usual_order=usual_order
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to send churn prevention message")
        
        return {"message": "Churn prevention message sent successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send churn prevention message: {str(e)}")


@router.post("/send-personalized-recommendation")
async def send_personalized_recommendation(
    customer_phone: str,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
):
    """Send personalized recommendations to a customer."""
    try:
        # Get customer info
        from app.models import Order
        
        customer_orders = db.query(Order).filter(
            Order.business_id == business.id,
            Order.customer_phone == customer_phone
        ).order_by(Order.created_at.desc()).limit(1).first()
        
        if not customer_orders:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        customer_name = customer_orders.customer_name or "Valued Customer"
        
        # Get personalized recommendations
        analytics_engine = AnalyticsEngine(db)
        recommendations_data = await analytics_engine.generate_personalized_recommendations(
            customer_phone=customer_phone,
            business_id=business.id
        )
        
        if not recommendations_data["recommendations"]:
            raise HTTPException(status_code=400, detail="No recommendations available for this customer")
        
        # Send personalized recommendation
        notification_service = NotificationService(db)
        success = await notification_service.send_personalized_recommendation(
            customer_phone=customer_phone,
            customer_name=customer_name,
            business_name=business.name,
            recommendations=recommendations_data["recommendations"]
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to send personalized recommendation")
        
        return {"message": "Personalized recommendation sent successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send personalized recommendation: {str(e)}")


@router.get("/customer-insights/{customer_phone}")
async def get_customer_insights(
    customer_phone: str,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
):
    """Get comprehensive customer insights."""
    try:
        from app.models import Order
        
        # Get customer orders
        customer_orders = db.query(Order).filter(
            Order.business_id == business.id,
            Order.customer_phone == customer_phone
        ).order_by(Order.created_at.desc()).all()
        
        if not customer_orders:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        # Calculate insights
        total_orders = len(customer_orders)
        total_spent = sum(order.total_amount for order in customer_orders)
        average_order_value = total_spent / total_orders if total_orders > 0 else 0
        
        # Get first and last order dates
        first_order = customer_orders[-1]
        last_order = customer_orders[0]
        
        # Calculate customer lifetime
        customer_lifetime_days = (last_order.created_at - first_order.created_at).days
        
        # Get favorite items
        item_counts = {}
        for order in customer_orders:
            for item in order.items:
                item_name = item.get("name", "")
                if item_name:
                    item_counts[item_name] = item_counts.get(item_name, 0) + item.get("quantity", 1)
        
        favorite_items = sorted(item_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Get churn risk
        days_since_last_order = (datetime.now() - last_order.created_at).days
        churn_risk = "low"
        if days_since_last_order > 30:
            churn_risk = "high"
        elif days_since_last_order > 14:
            churn_risk = "medium"
        
        # Get order frequency
        if total_orders > 1:
            avg_days_between_orders = customer_lifetime_days / (total_orders - 1)
        else:
            avg_days_between_orders = 0
        
        return {
            "customer_info": {
                "phone": customer_phone,
                "name": last_order.customer_name or "Unknown",
                "first_order_date": first_order.created_at.isoformat(),
                "last_order_date": last_order.created_at.isoformat(),
                "customer_lifetime_days": customer_lifetime_days
            },
            "order_metrics": {
                "total_orders": total_orders,
                "total_spent": round(total_spent, 2),
                "average_order_value": round(average_order_value, 2),
                "days_since_last_order": days_since_last_order,
                "avg_days_between_orders": round(avg_days_between_orders, 1)
            },
            "preferences": {
                "favorite_items": [{"name": name, "count": count} for name, count in favorite_items],
                "churn_risk": churn_risk
            },
            "recent_orders": [
                {
                    "id": order.id,
                    "total": order.total_amount,
                    "date": order.created_at.isoformat(),
                    "status": order.status.value
                }
                for order in customer_orders[:5]
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get customer insights: {str(e)}")


@router.get("/revenue-forecast")
async def get_revenue_forecast(
    days: int = Query(30, description="Number of days to forecast"),
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
):
    """Get revenue forecast for the specified number of days."""
    try:
        analytics_engine = AnalyticsEngine(db)
        
        # Get recent revenue data for forecasting
        from app.models import Order
        from app.models.order import OrderStatus
        from sqlalchemy import func
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)  # Use last 30 days for forecasting
        
        daily_revenue = db.query(
            func.date(Order.created_at).label('date'),
            func.sum(Order.total_amount).label('revenue')
        ).filter(
            Order.business_id == business.id,
            Order.created_at >= start_date,
            Order.created_at <= end_date,
            Order.status.in_([OrderStatus.COMPLETED, OrderStatus.CONFIRMED])
        ).group_by(func.date(Order.created_at)).all()
        
        if not daily_revenue:
            return {"forecast": [], "message": "Insufficient data for forecasting"}
        
        # Calculate average daily revenue
        total_revenue = sum(day.revenue for day in daily_revenue)
        avg_daily_revenue = total_revenue / len(daily_revenue)
        
        # Generate forecast
        forecast = []
        for i in range(days):
            forecast_date = end_date + timedelta(days=i+1)
            forecast.append({
                "date": forecast_date.strftime("%Y-%m-%d"),
                "predicted_revenue": round(avg_daily_revenue, 2),
                "confidence": "medium"
            })
        
        return {
            "forecast": forecast,
            "average_daily_revenue": round(avg_daily_revenue, 2),
            "forecast_period_days": days,
            "total_predicted_revenue": round(avg_daily_revenue * days, 2)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get revenue forecast: {str(e)}")


@router.get("/customer-segments")
async def get_customer_segments(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
):
    """Get customer segmentation analysis."""
    try:
        from app.models import Order
        from app.models.order import OrderStatus
        from sqlalchemy import func
        
        # Get customer data
        customer_data = db.query(
            Order.customer_phone,
            func.count(Order.id).label('order_count'),
            func.sum(Order.total_amount).label('total_spent'),
            func.max(Order.created_at).label('last_order_date')
        ).filter(
            Order.business_id == business.id,
            Order.customer_phone.isnot(None),
            Order.status.in_([OrderStatus.COMPLETED, OrderStatus.CONFIRMED])
        ).group_by(Order.customer_phone).all()
        
        if not customer_data:
            return {"segments": [], "message": "No customer data available"}
        
        # Segment customers
        segments = {
            "vip": [],
            "regular": [],
            "occasional": [],
            "at_risk": []
        }
        
        for customer in customer_data:
            days_since_last_order = (datetime.now() - customer.last_order_date).days
            avg_order_value = customer.total_spent / customer.order_count if customer.order_count > 0 else 0
            
            # Determine segment
            if customer.total_spent > 200 and customer.order_count > 10:
                segment = "vip"
            elif customer.total_spent > 100 and customer.order_count > 5:
                segment = "regular"
            elif days_since_last_order > 30:
                segment = "at_risk"
            else:
                segment = "occasional"
            
            customer_info = {
                "phone": customer.customer_phone,
                "order_count": customer.order_count,
                "total_spent": float(customer.total_spent),
                "average_order_value": round(avg_order_value, 2),
                "days_since_last_order": days_since_last_order,
                "last_order_date": customer.last_order_date.isoformat()
            }
            
            segments[segment].append(customer_info)
        
        # Calculate segment statistics
        segment_stats = {}
        for segment, customers in segments.items():
            if customers:
                segment_stats[segment] = {
                    "count": len(customers),
                    "total_revenue": sum(c["total_spent"] for c in customers),
                    "average_order_value": sum(c["average_order_value"] for c in customers) / len(customers)
                }
            else:
                segment_stats[segment] = {
                    "count": 0,
                    "total_revenue": 0,
                    "average_order_value": 0
                }
        
        return {
            "segments": segments,
            "segment_stats": segment_stats,
            "total_customers": len(customer_data)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get customer segments: {str(e)}")
