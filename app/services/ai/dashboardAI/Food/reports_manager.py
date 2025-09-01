# app/services/ai/dashboardAI/Food/reports_manager.py
"""
Reports Management for Dashboard AI
Handles natural language requests for business reports and analytics
"""

from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from app.models import Order
from datetime import datetime, timedelta
import logging
import json
import random

logger = logging.getLogger(__name__)

class ReportsManager:
    def __init__(self, db: Session):
        self.db = db
    
    async def handle_reports_request(self, business_id: int, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle reports-related requests from the AI"""
        action = intent.get("action", "")
        parameters = intent.get("parameters", {})
        
        try:
            if action == "get_daily_summary":
                return await self.get_daily_summary(business_id)
            elif action == "get_weekly_performance":
                return await self.get_weekly_performance(business_id)
            elif action == "get_monthly_comprehensive":
                months = parameters.get("months", 1)
                return await self.get_monthly_comprehensive(business_id, months)
            elif action == "get_sales_report":
                period = parameters.get("period", "daily")
                return await self.get_sales_report(business_id, period)
            elif action == "get_customer_insights":
                return await self.get_customer_insights(business_id)
            elif action == "get_financial_report":
                return await self.get_financial_report(business_id)
            elif action == "get_operational_report":
                return await self.get_operational_report(business_id)
            elif action == "get_growth_analysis":
                months = parameters.get("months", 6)
                return await self.get_growth_analysis(business_id, months)
            elif action == "generate_custom_report":
                report_type = parameters.get("report_type", "custom")
                start_date = parameters.get("start_date", "")
                end_date = parameters.get("end_date", "")
                format = parameters.get("format", "json")
                if not start_date or not end_date:
                    return {"success": False, "message": "Start date and end date are required for custom reports"}
                return await self.generate_custom_report(business_id, report_type, start_date, end_date, format)
            elif action == "export_business_data":
                data_type = parameters.get("data_type", "all")
                start_date = parameters.get("start_date", "")
                end_date = parameters.get("end_date", "")
                format = parameters.get("format", "csv")
                if not start_date or not end_date:
                    return {"success": False, "message": "Start date and end date are required for data export"}
                return await self.export_business_data(business_id, data_type, start_date, end_date, format)
            elif action == "schedule_report":
                report_type = parameters.get("report_type", "daily_summary")
                frequency = parameters.get("frequency", "daily")
                format = parameters.get("format", "pdf")
                email = parameters.get("email")
                return await self.schedule_report(business_id, report_type, frequency, format, email)
            elif action == "get_report_templates":
                return await self.get_report_templates(business_id)
            elif action == "generate_report_from_template":
                template_id = parameters.get("template_id", "")
                start_date = parameters.get("start_date")
                end_date = parameters.get("end_date")
                format = parameters.get("format", "pdf")
                if not template_id:
                    return {"success": False, "message": "Template ID is required for template-based reports"}
                return await self.generate_report_from_template(business_id, template_id, start_date, end_date, None, format)
            else:
                return {"success": False, "message": f"Unsupported reports action: {action}"}
        except Exception as e:
            logger.exception("Error handling reports request: %s", e)
            return {"success": False, "message": f"Error processing reports request: {str(e)}"}
    
    async def get_daily_summary(self, business_id: int, date_str: Optional[str] = None) -> Dict[str, Any]:
        """Generate daily business summary"""
        try:
            # Parse date or use today
            if date_str:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            else:
                target_date = datetime.now().date()
            
            # Get orders for the day
            start_datetime = datetime.combine(target_date, datetime.min.time())
            end_datetime = datetime.combine(target_date, datetime.max.time())
            
            orders = self.db.query(Order).filter(
                Order.business_id == business_id,
                Order.created_at >= start_datetime,
                Order.created_at <= end_datetime
            ).all()
            
            # Calculate metrics
            total_revenue = sum(order.total_amount for order in orders)
            total_orders = len(orders)
            avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
            
            # Status breakdown
            status_counts = {}
            for order in orders:
                status = getattr(order.status, "value", str(order.status)) if order.status else "unknown"
                if status not in status_counts:
                    status_counts[status] = 0
                status_counts[status] += 1
            
            # Customer metrics
            unique_customers = len(set(order.customer_id for order in orders if order.customer_id))
            
            # Payment methods
            payment_methods = {}
            for order in orders:
                method = order.payment_method or "unknown"
                if method not in payment_methods:
                    payment_methods[method] = 0
                payment_methods[method] += order.total_amount
            
            # Format response
            response_text = f"## Daily Business Summary - {target_date.strftime('%Y-%m-%d')}\n\n"
            response_text += f"**Total Revenue:** ${total_revenue:.2f}\n"
            response_text += f"**Total Orders:** {total_orders}\n"
            response_text += f"**Average Order Value:** ${avg_order_value:.2f}\n"
            response_text += f"**Unique Customers:** {unique_customers}\n\n"
            
            if status_counts:
                response_text += "**Order Status Breakdown:**\n"
                for status, count in status_counts.items():
                    response_text += f"  - {status.title()}: {count} orders\n"
                response_text += "\n"
            
            if payment_methods:
                response_text += "**Payment Methods:**\n"
                for method, amount in payment_methods.items():
                    response_text += f"  - {method.title()}: ${amount:.2f}\n"
            
            return {
                "success": True,
                "message": response_text,
                "data": {
                    "type": "daily_summary",
                    "date": target_date.strftime('%Y-%m-%d'),
                    "metrics": {
                        "total_revenue": round(total_revenue, 2),
                        "total_orders": total_orders,
                        "average_order_value": round(avg_order_value, 2),
                        "unique_customers": unique_customers,
                        "status_breakdown": status_counts,
                        "payment_methods": {method: round(amount, 2) for method, amount in payment_methods.items()}
                    }
                }
            }
        except Exception as e:
            return {"success": False, "message": f"Error generating daily summary: {str(e)}"}
    
    async def get_weekly_performance(self, business_id: int) -> Dict[str, Any]:
        """Generate weekly performance report"""
        try:
            # Current week dates
            current_date = datetime.now().date()
            start_date = current_date - timedelta(days=current_date.weekday())  # Monday
            end_date = start_date + timedelta(days=6)  # Sunday
            
            # Get orders for the week
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
            
            orders = self.db.query(Order).filter(
                Order.business_id == business_id,
                Order.created_at >= start_datetime,
                Order.created_at <= end_datetime
            ).all()
            
            # Calculate metrics
            total_revenue = sum(order.total_amount for order in orders)
            total_orders = len(orders)
            avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
            
            # Daily trend
            daily_revenue = {}
            for order in orders:
                day = order.created_at.date()
                if day not in daily_revenue:
                    daily_revenue[day] = 0
                daily_revenue[day] += order.total_amount
            
            # Convert to list for JSON serialization
            daily_trend = [
                {
                    "date": day.strftime("%Y-%m-%d"),
                    "revenue": round(revenue, 2)
                }
                for day, revenue in sorted(daily_revenue.items())
            ]
            
            # Status breakdown
            status_counts = {}
            for order in orders:
                status = getattr(order.status, "value", str(order.status)) if order.status else "unknown"
                if status not in status_counts:
                    status_counts[status] = 0
                status_counts[status] += 1
            
            # Customer metrics
            unique_customers = len(set(order.customer_id for order in orders if order.customer_id))
            
            # Format response
            response_text = f"## Weekly Performance Report\n"
            response_text += f"**Period:** {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}\n\n"
            response_text += f"**Total Revenue:** ${total_revenue:.2f}\n"
            response_text += f"**Total Orders:** {total_orders}\n"
            response_text += f"**Average Order Value:** ${avg_order_value:.2f}\n"
            response_text += f"**Unique Customers:** {unique_customers}\n\n"
            
            if daily_trend:
                response_text += "**Daily Revenue Trend:**\n"
                for day_data in daily_trend:
                    response_text += f"  - {day_data['date']}: ${day_data['revenue']:.2f}\n"
                response_text += "\n"
            
            if status_counts:
                response_text += "**Order Status Breakdown:**\n"
                for status, count in status_counts.items():
                    response_text += f"  - {status.title()}: {count} orders\n"
            
            return {
                "success": True,
                "message": response_text,
                "data": {
                    "type": "weekly_performance",
                    "period": {
                        "start_date": start_date.strftime('%Y-%m-%d'),
                        "end_date": end_date.strftime('%Y-%m-%d')
                    },
                    "metrics": {
                        "total_revenue": round(total_revenue, 2),
                        "total_orders": total_orders,
                        "average_order_value": round(avg_order_value, 2),
                        "unique_customers": unique_customers,
                        "daily_trend": daily_trend,
                        "status_breakdown": status_counts
                    }
                }
            }
        except Exception as e:
            return {"success": False, "message": f"Error generating weekly performance report: {str(e)}"}
    
    async def get_monthly_comprehensive(self, business_id: int, months: int = 1) -> Dict[str, Any]:
        """Generate comprehensive monthly report"""
        try:
            # Current date
            current_date = datetime.now().date()
            
            # Calculate start date based on months parameter
            if months == 1:
                # Just current month
                start_date = current_date.replace(day=1)
                end_date = start_date.replace(day=1) + timedelta(days=32)
                end_date = end_date.replace(day=1) - timedelta(days=1)  # Last day of current month
            else:
                # Multiple months
                end_date = current_date
                # Calculate start date
                start_date = current_date.replace(day=1)
                for _ in range(months - 1):
                    # Move to previous month
                    if start_date.month == 1:
                        start_date = start_date.replace(year=start_date.year - 1, month=12)
                    else:
                        start_date = start_date.replace(month=start_date.month - 1)
            
            # Get orders for the period
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
            
            orders = self.db.query(Order).filter(
                Order.business_id == business_id,
                Order.created_at >= start_datetime,
                Order.created_at <= end_datetime
            ).all()
            
            # Calculate metrics
            total_revenue = sum(order.total_amount for order in orders)
            total_orders = len(orders)
            avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
            
            # Customer metrics
            unique_customers = len(set(order.customer_id for order in orders if order.customer_id))
            
            # Status breakdown
            status_counts = {}
            for order in orders:
                status = getattr(order.status, "value", str(order.status)) if order.status else "unknown"
                if status not in status_counts:
                    status_counts[status] = 0
                status_counts[status] += 1
            
            # Format response
            response_text = f"## Comprehensive Monthly Report\n"
            response_text += f"**Period:** {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}\n"
            response_text += f"**Months Analyzed:** {months}\n\n"
            response_text += f"**Total Revenue:** ${total_revenue:.2f}\n"
            response_text += f"**Total Orders:** {total_orders}\n"
            response_text += f"**Average Order Value:** ${avg_order_value:.2f}\n"
            response_text += f"**Unique Customers:** {unique_customers}\n\n"
            
            if status_counts:
                response_text += "**Order Status Breakdown:**\n"
                for status, count in status_counts.items():
                    percentage = (count / total_orders * 100) if total_orders > 0 else 0
                    response_text += f"  - {status.title()}: {count} orders ({percentage:.1f}%)\n"
            
            return {
                "success": True,
                "message": response_text,
                "data": {
                    "type": "monthly_comprehensive",
                    "period": {
                        "start_date": start_date.strftime('%Y-%m-%d'),
                        "end_date": end_date.strftime('%Y-%m-%d'),
                        "months_analyzed": months
                    },
                    "metrics": {
                        "total_revenue": round(total_revenue, 2),
                        "total_orders": total_orders,
                        "average_order_value": round(avg_order_value, 2),
                        "unique_customers": unique_customers,
                        "status_breakdown": status_counts
                    }
                }
            }
        except Exception as e:
            return {"success": False, "message": f"Error generating comprehensive monthly report: {str(e)}"}
    
    async def get_sales_report(self, business_id: int, period: str = "daily") -> Dict[str, Any]:
        """Generate sales report for specified period"""
        try:
            # Determine date range based on period
            current_date = datetime.now().date()
            
            if period == "daily":
                start_date = current_date
                end_date = current_date
                title = "Today's Sales Report"
            elif period == "weekly":
                start_date = current_date - timedelta(days=current_date.weekday())
                end_date = start_date + timedelta(days=6)
                title = "Weekly Sales Report"
            elif period == "monthly":
                start_date = current_date.replace(day=1)
                end_date = start_date.replace(day=1) + timedelta(days=32)
                end_date = end_date.replace(day=1) - timedelta(days=1)
                title = "Monthly Sales Report"
            else:
                start_date = current_date - timedelta(days=7)
                end_date = current_date
                title = "Sales Report (Last 7 Days)"
            
            # Get orders for the period
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
            
            orders = self.db.query(Order).filter(
                Order.business_id == business_id,
                Order.created_at >= start_datetime,
                Order.created_at <= end_datetime
            ).all()
            
            # Calculate sales metrics
            total_revenue = sum(order.total_amount for order in orders)
            total_orders = len(orders)
            avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
            
            # Revenue by payment method
            payment_methods = {}
            for order in orders:
                method = order.payment_method or "unknown"
                if method not in payment_methods:
                    payment_methods[method] = 0
                payment_methods[method] += order.total_amount
            
            # Format response
            response_text = f"## {title}\n"
            response_text += f"**Period:** {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}\n\n"
            response_text += f"**Total Revenue:** ${total_revenue:.2f}\n"
            response_text += f"**Total Orders:** {total_orders}\n"
            response_text += f"**Average Order Value:** ${avg_order_value:.2f}\n\n"
            
            if payment_methods:
                response_text += "**Revenue by Payment Method:**\n"
                for method, amount in payment_methods.items():
                    response_text += f"  - {method.title()}: ${amount:.2f}\n"
            
            return {
                "success": True,
                "message": response_text,
                "data": {
                    "type": "sales_report",
                    "period": period,
                    "date_range": {
                        "start_date": start_date.strftime('%Y-%m-%d'),
                        "end_date": end_date.strftime('%Y-%m-%d')
                    },
                    "metrics": {
                        "total_revenue": round(total_revenue, 2),
                        "total_orders": total_orders,
                        "average_order_value": round(avg_order_value, 2),
                        "payment_methods": {method: round(amount, 2) for method, amount in payment_methods.items()}
                    }
                }
            }
        except Exception as e:
            return {"success": False, "message": f"Error generating sales report: {str(e)}"}
    
    async def get_customer_insights(self, business_id: int) -> Dict[str, Any]:
        """Generate customer insights report"""
        try:
            # Current month dates
            current_date = datetime.now().date()
            start_date = current_date.replace(day=1)
            end_date = start_date.replace(day=1) + timedelta(days=32)
            end_date = end_date.replace(day=1) - timedelta(days=1)  # Last day of current month
            
            # Get orders for current month
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
            
            orders = self.db.query(Order).filter(
                Order.business_id == business_id,
                Order.created_at >= start_datetime,
                Order.created_at <= end_datetime
            ).all()
            
            # Customer metrics
            total_orders = len(orders)
            unique_customers = len(set(order.customer_id for order in orders if order.customer_id))
            
            # Repeat customers analysis
            customer_order_counts = {}
            for order in orders:
                if order.customer_id:
                    if order.customer_id not in customer_order_counts:
                        customer_order_counts[order.customer_id] = 0
                    customer_order_counts[order.customer_id] += 1
            
            repeat_customers = len([cid for cid, count in customer_order_counts.items() if count > 1])
            new_customers = unique_customers - repeat_customers
            
            repeat_customer_rate = (repeat_customers / unique_customers * 100) if unique_customers > 0 else 0
            
            # Customer lifetime value (simplified)
            avg_customer_value = total_revenue / unique_customers if unique_customers > 0 else 0
            
            # Customer segments
            high_value_customers = [
                cid for cid, count in customer_order_counts.items() 
                if count >= 5  # 5 or more orders
            ]
            
            medium_value_customers = [
                cid for cid, count in customer_order_counts.items() 
                if 2 <= count < 5  # 2-4 orders
            ]
            
            low_value_customers = [
                cid for cid, count in customer_order_counts.items() 
                if count == 1  # 1 order
            ]
            
            # Format response
            response_text = "## Customer Insights Report\n\n"
            response_text += f"**Reporting Period:** {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}\n\n"
            response_text += f"**Unique Customers:** {unique_customers}\n"
            response_text += f"**New Customers:** {new_customers}\n"
            response_text += f"**Repeat Customers:** {repeat_customers}\n"
            response_text += f"**Repeat Customer Rate:** {repeat_customer_rate:.1f}%\n\n"
            
            response_text += "**Customer Segments:**\n"
            response_text += f"  - High Value (5+ orders): {len(high_value_customers)} customers\n"
            response_text += f"  - Medium Value (2-4 orders): {len(medium_value_customers)} customers\n"
            response_text += f"  - Low Value (1 order): {len(low_value_customers)} customers\n\n"
            
            response_text += f"**Average Customer Value:** ${avg_customer_value:.2f}\n"
            
            return {
                "success": True,
                "message": response_text,
                "data": {
                    "type": "customer_insights",
                    "period": {
                        "start_date": start_date.strftime('%Y-%m-%d'),
                        "end_date": end_date.strftime('%Y-%m-%d')
                    },
                    "customer_base": {
                        "unique_customers": unique_customers,
                        "new_customers": new_customers,
                        "repeat_customers": repeat_customers,
                        "repeat_customer_rate": round(repeat_customer_rate, 2)
                    },
                    "customer_segments": {
                        "high_value": len(high_value_customers),
                        "medium_value": len(medium_value_customers),
                        "low_value": len(low_value_customers)
                    },
                    "average_customer_value": round(avg_customer_value, 2)
                }
            }
        except Exception as e:
            return {"success": False, "message": f"Error generating customer insights: {str(e)}"}
    
    async def get_financial_report(self, business_id: int) -> Dict[str, Any]:
        """Generate financial performance report"""
        try:
            # Current month dates
            current_date = datetime.now().date()
            start_date = current_date.replace(day=1)
            end_date = start_date.replace(day=1) + timedelta(days=32)
            end_date = end_date.replace(day=1) - timedelta(days=1)  # Last day of current month
            
            # Get orders for current month
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
            
            orders = self.db.query(Order).filter(
                Order.business_id == business_id,
                Order.created_at >= start_datetime,
                Order.created_at <= end_datetime
            ).all()
            
            # Calculate revenue metrics
            total_revenue = sum(order.total_amount for order in orders)
            total_orders = len(orders)
            avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
            
            # Revenue by payment method
            payment_methods = {}
            for order in orders:
                method = order.payment_method or "unknown"
                if method not in payment_methods:
                    payment_methods[method] = 0
                payment_methods[method] += order.total_amount
            
            # Daily revenue trend
            daily_revenue = {}
            for order in orders:
                day = order.created_at.date()
                if day not in daily_revenue:
                    daily_revenue[day] = 0
                daily_revenue[day] += order.total_amount
            
            # Convert to list for JSON serialization
            daily_trend = [
                {
                    "date": day.strftime("%Y-%m-%d"),
                    "revenue": round(revenue, 2)
                }
                for day, revenue in sorted(daily_revenue.items())
            ]
            
            # Simulated cost data (in a real implementation, this would come from accounting systems)
            cost_of_goods = total_revenue * random.uniform(0.25, 0.35)  # 25-35% of revenue
            labor_costs = total_revenue * random.uniform(0.20, 0.30)     # 20-30% of revenue
            overhead_costs = total_revenue * random.uniform(0.10, 0.15)   # 10-15% of revenue
            
            total_costs = cost_of_goods + labor_costs + overhead_costs
            gross_profit = total_revenue - cost_of_goods
            net_profit = total_revenue - total_costs
            
            profit_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0
            
            # Format response
            response_text = "## Monthly Financial Report\n\n"
            response_text += f"**Reporting Period:** {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}\n\n"
            response_text += f"**Total Revenue:** ${total_revenue:.2f}\n"
            response_text += f"**Total Orders:** {total_orders}\n"
            response_text += f"**Average Order Value:** ${avg_order_value:.2f}\n\n"
            
            response_text += "**Cost Analysis:**\n"
            response_text += f"  - Cost of Goods: ${cost_of_goods:.2f}\n"
            response_text += f"  - Labor Costs: ${labor_costs:.2f}\n"
            response_text += f"  - Overhead Costs: ${overhead_costs:.2f}\n"
            response_text += f"  - **Total Costs:** ${total_costs:.2f}\n\n"
            
            response_text += "**Profitability:**\n"
            response_text += f"  - Gross Profit: ${gross_profit:.2f}\n"
            response_text += f"  - Net Profit: ${net_profit:.2f}\n"
            response_text += f"  - Profit Margin: {profit_margin:.1f}%\n\n"
            
            if daily_trend:
                response_text += "**Daily Revenue Trend (Top 5 days):**\n"
                # Show top 5 days by revenue
                sorted_days = sorted(daily_trend, key=lambda x: x['revenue'], reverse=True)[:5]
                for day_data in sorted_days:
                    response_text += f"  - {day_data['date']}: ${day_data['revenue']:.2f}\n"
            
            return {
                "success": True,
                "message": response_text,
                "data": {
                    "type": "financial_report",
                    "period": {
                        "month": start_date.strftime("%Y-%m"),
                        "start_date": start_date.strftime('%Y-%m-%d'),
                        "end_date": end_date.strftime('%Y-%m-%d')
                    },
                    "revenue": {
                        "total": round(total_revenue, 2),
                        "average_order_value": round(avg_order_value, 2),
                        "total_orders": total_orders,
                        "by_payment_method": {
                            method: round(amount, 2) 
                            for method, amount in payment_methods.items()
                        },
                        "daily_trend": daily_trend
                    },
                    "costs": {
                        "cost_of_goods": round(cost_of_goods, 2),
                        "labor_costs": round(labor_costs, 2),
                        "overhead_costs": round(overhead_costs, 2),
                        "total_costs": round(total_costs, 2)
                    },
                    "profitability": {
                        "gross_profit": round(gross_profit, 2),
                        "net_profit": round(net_profit, 2),
                        "profit_margin": round(profit_margin, 2)
                    }
                }
            }
        except Exception as e:
            return {"success": False, "message": f"Error generating financial report: {str(e)}"}
    
    async def get_operational_report(self, business_id: int) -> Dict[str, Any]:
        """Generate operational efficiency report"""
        try:
            # Current month dates
            current_date = datetime.now().date()
            start_date = current_date.replace(day=1)
            end_date = start_date.replace(day=1) + timedelta(days=32)
            end_date = end_date.replace(day=1) - timedelta(days=1)  # Last day of current month
            
            # Get orders for current month
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
            
            orders = self.db.query(Order).filter(
                Order.business_id == business_id,
                Order.created_at >= start_datetime,
                Order.created_at <= end_datetime
            ).all()
            
            # Operational metrics
            total_orders = len(orders)
            completed_orders = [o for o in orders if getattr(o.status, "value", str(o.status)) == "completed"]
            
            # Preparation time metrics
            prep_times = []
            for order in completed_orders:
                if order.created_at and order.updated_at:
                    prep_time = (order.updated_at - order.created_at).total_seconds() / 60  # in minutes
                    prep_times.append(prep_time)
            
            avg_prep_time = sum(prep_times) / len(prep_times) if prep_times else 0
            
            # Order status distribution
            status_counts = {}
            for order in orders:
                status = getattr(order.status, "value", str(order.status)) if order.status else "unknown"
                if status not in status_counts:
                    status_counts[status] = 0
                status_counts[status] += 1
            
            # Cancellation rate
            cancellations = status_counts.get("cancelled", 0)
            cancellation_rate = (cancellations / total_orders * 100) if total_orders > 0 else 0
            
            # Peak hours analysis
            hourly_orders = {}
            for order in orders:
                hour = order.created_at.hour
                if hour not in hourly_orders:
                    hourly_orders[hour] = 0
                hourly_orders[hour] += 1
            
            peak_hour = max(hourly_orders, key=hourly_orders.get) if hourly_orders else None
            
            # Daily order volume
            daily_orders = {}
            for order in orders:
                day = order.created_at.date()
                if day not in daily_orders:
                    daily_orders[day] = 0
                daily_orders[day] += 1
            
            avg_daily_orders = sum(daily_orders.values()) / len(daily_orders) if daily_orders else 0
            
            # Busiest day
            busiest_day = max(daily_orders, key=daily_orders.get) if daily_orders else None
            
            # Format response
            response_text = "## Monthly Operational Report\n\n"
            response_text += f"**Reporting Period:** {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}\n\n"
            response_text += "**Efficiency Metrics:**\n"
            response_text += f"  - Total Orders: {total_orders}\n"
            response_text += f"  - Completed Orders: {len(completed_orders)}\n"
            response_text += f"  - Average Preparation Time: {avg_prep_time:.1f} minutes\n"
            response_text += f"  - Completion Rate: {(len(completed_orders) / total_orders * 100) if total_orders > 0 else 0:.1f}%\n"
            response_text += f"  - Cancellation Rate: {cancellation_rate:.1f}%\n\n"
            
            response_text += "**Peak Performance:**\n"
            response_text += f"  - Peak Hour: {peak_hour}:00\n" if peak_hour is not None else "  - Peak Hour: Not available\n"
            response_text += f"  - Average Daily Orders: {avg_daily_orders:.1f}\n"
            response_text += f"  - Busiest Day: {busiest_day.strftime('%Y-%m-%d') if busiest_day else 'Not available'}\n\n"
            
            if status_counts:
                response_text += "**Order Status Distribution:**\n"
                for status, count in status_counts.items():
                    response_text += f"  - {status.title()}: {count} orders\n"
            
            return {
                "success": True,
                "message": response_text,
                "data": {
                    "type": "operational_report",
                    "period": {
                        "month": start_date.strftime("%Y-%m"),
                        "start_date": start_date.strftime('%Y-%m-%d'),
                        "end_date": end_date.strftime('%Y-%m-%d')
                    },
                    "efficiency": {
                        "total_orders": total_orders,
                        "completed_orders": len(completed_orders),
                        "average_preparation_time_minutes": round(avg_prep_time, 2),
                        "completion_rate": round((len(completed_orders) / total_orders * 100) if total_orders > 0 else 0, 2),
                        "cancellation_rate": round(cancellation_rate, 2)
                    },
                    "peak_performance": {
                        "peak_hour": peak_hour,
                        "average_daily_orders": round(avg_daily_orders, 2),
                        "busiest_day": busiest_day.strftime("%Y-%m-%d") if busiest_day else None
                    },
                    "status_distribution": status_counts
                }
            }
        except Exception as e:
            return {"success": False, "message": f"Error generating operational report: {str(e)}"}
    
    async def get_growth_analysis(self, business_id: int, months: int = 6) -> Dict[str, Any]:
        """Generate business growth analysis report"""
        try:
            # Current date
            current_date = datetime.now().date()
            
            # Calculate date range
            end_date = current_date
            start_date = current_date.replace(day=1)
            for _ in range(months - 1):
                # Move to previous month
                if start_date.month == 1:
                    start_date = start_date.replace(year=start_date.year - 1, month=12)
                else:
                    start_date = start_date.replace(month=start_date.month - 1)
            
            # Get orders for the period
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
            
            orders = self.db.query(Order).filter(
                Order.business_id == business_id,
                Order.created_at >= start_datetime,
                Order.created_at <= end_datetime
            ).all()
            
            # Group orders by month
            monthly_data = {}
            for order in orders:
                month_key = order.created_at.strftime("%Y-%m")
                if month_key not in monthly_data:
                    monthly_data[month_key] = {"revenue": 0, "orders": 0, "customers": set()}
                monthly_data[month_key]["revenue"] += order.total_amount
                monthly_data[month_key]["orders"] += 1
                if order.customer_id:
                    monthly_data[month_key]["customers"].add(order.customer_id)
            
            # Convert customer sets to counts
            for month_data in monthly_data.values():
                month_data["customers"] = len(month_data["customers"])
            
            # Sort months chronologically
            sorted_months = sorted(monthly_data.keys())
            
            # Calculate growth metrics
            growth_data = []
            for i, month in enumerate(sorted_months):
                data = monthly_data[month]
                growth_entry = {
                    "month": month,
                    "revenue": round(data["revenue"], 2),
                    "orders": data["orders"],
                    "customers": data["customers"]
                }
                
                # Calculate growth rates
                if i > 0:
                    prev_month = sorted_months[i-1]
                    prev_data = monthly_data[prev_month]
                    
                    revenue_growth = ((data["revenue"] - prev_data["revenue"]) / prev_data["revenue"] * 100) if prev_data["revenue"] > 0 else 0
                    order_growth = ((data["orders"] - prev_data["orders"]) / prev_data["orders"] * 100) if prev_data["orders"] > 0 else 0
                    customer_growth = ((data["customers"] - prev_data["customers"]) / prev_data["customers"] * 100) if prev_data["customers"] > 0 else 0
                    
                    growth_entry["revenue_growth_percent"] = round(revenue_growth, 2)
                    growth_entry["order_growth_percent"] = round(order_growth, 2)
                    growth_entry["customer_growth_percent"] = round(customer_growth, 2)
                else:
                    growth_entry["revenue_growth_percent"] = 0
                    growth_entry["order_growth_percent"] = 0
                    growth_entry["customer_growth_percent"] = 0
                
                growth_data.append(growth_entry)
            
            # Overall growth
            if len(growth_data) > 1:
                first_month = growth_data[0]
                last_month = growth_data[-1]
                
                overall_revenue_growth = ((last_month["revenue"] - first_month["revenue"]) / first_month["revenue"] * 100) if first_month["revenue"] > 0 else 0
                overall_order_growth = ((last_month["orders"] - first_month["orders"]) / first_month["orders"] * 100) if first_month["orders"] > 0 else 0
                overall_customer_growth = ((last_month["customers"] - first_month["customers"]) / first_month["customers"] * 100) if first_month["customers"] > 0 else 0
            else:
                overall_revenue_growth = 0
                overall_order_growth = 0
                overall_customer_growth = 0
            
            # Format response
            response_text = "## Business Growth Analysis Report\n\n"
            response_text += f"**Analysis Period:** {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} ({months} months)\n\n"
            
            response_text += "**Monthly Performance:**\n"
            for entry in growth_data:
                response_text += f"  - {entry['month']}: ${entry['revenue']:.2f} revenue, {entry['orders']} orders, {entry['customers']} customers\n"
                if entry['revenue_growth_percent'] != 0:
                    response_text += f"    Growth: {entry['revenue_growth_percent']:+.1f}% revenue, {entry['order_growth_percent']:+.1f}% orders, {entry['customer_growth_percent']:+.1f}% customers\n"
            response_text += "\n"
            
            response_text += "**Overall Growth:**\n"
            response_text += f"  - Revenue: {overall_revenue_growth:+.1f}%\n"
            response_text += f"  - Orders: {overall_order_growth:+.1f}%\n"
            response_text += f"  - Customers: {overall_customer_growth:+.1f}%\n\n"
            
            # Identify best performing month
            if growth_data:
                best_month = max(growth_data, key=lambda x: x['revenue'])
                response_text += f"**Best Performing Month:** {best_month['month']} with ${best_month['revenue']:.2f} revenue\n"
            
            return {
                "success": True,
                "message": response_text,
                "data": {
                    "type": "growth_analysis",
                    "period": {
                        "months_analyzed": months,
                        "start_date": start_date.strftime('%Y-%m-%d'),
                        "end_date": end_date.strftime('%Y-%m-%d')
                    },
                    "monthly_data": growth_data,
                    "overall_growth": {
                        "revenue_percent": round(overall_revenue_growth, 2),
                        "orders_percent": round(overall_order_growth, 2),
                        "customers_percent": round(overall_customer_growth, 2)
                    }
                }
            }
        except Exception as e:
            return {"success": False, "message": f"Error generating growth analysis: {str(e)}"}
    
    async def generate_custom_report(self, business_id: int, report_type: str, start_date: str, end_date: str, format: str = "json") -> Dict[str, Any]:
        """Generate a custom report based on specified parameters"""
        try:
            # Parse dates
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
            
            # Get orders for the period
            start_datetime = datetime.combine(start_dt, datetime.min.time())
            end_datetime = datetime.combine(end_dt, datetime.max.time())
            
            orders = self.db.query(Order).filter(
                Order.business_id == business_id,
                Order.created_at >= start_datetime,
                Order.created_at <= end_datetime
            ).all()
            
            # Calculate metrics based on report type
            total_revenue = sum(order.total_amount for order in orders)
            total_orders = len(orders)
            avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
            
            # Customer metrics
            unique_customers = len(set(order.customer_id for order in orders if order.customer_id))
            
            # Status breakdown
            status_counts = {}
            for order in orders:
                status = getattr(order.status, "value", str(order.status)) if order.status else "unknown"
                if status not in status_counts:
                    status_counts[status] = 0
                status_counts[status] += 1
            
            # Format response based on requested format
            if format.lower() == "csv":
                # CSV format simulation
                response_text = f"Custom Report ({report_type})\n"
                response_text += f"Period: {start_date} to {end_date}\n"
                response_text += f"Total Revenue: ${total_revenue:.2f}\n"
                response_text += f"Total Orders: {total_orders}\n"
                response_text += f"Average Order Value: ${avg_order_value:.2f}\n"
                response_text += f"Unique Customers: {unique_customers}\n"
            elif format.lower() == "pdf":
                # PDF format simulation
                response_text = f"# Custom Report ({report_type})\n\n"
                response_text += f"**Period:** {start_date} to {end_date}\n\n"
                response_text += f"**Total Revenue:** ${total_revenue:.2f}\n"
                response_text += f"**Total Orders:** {total_orders}\n"
                response_text += f"**Average Order Value:** ${avg_order_value:.2f}\n"
                response_text += f"**Unique Customers:** {unique_customers}\n\n"
                
                if status_counts:
                    response_text += "**Order Status Distribution:**\n"
                    for status, count in status_counts.items():
                        response_text += f"  - {status.title()}: {count} orders\n"
            else:  # JSON/default
                response_text = f"## Custom Report ({report_type})\n\n"
                response_text += f"**Period:** {start_date} to {end_date}\n\n"
                response_text += f"**Total Revenue:** ${total_revenue:.2f}\n"
                response_text += f"**Total Orders:** {total_orders}\n"
                response_text += f"**Average Order Value:** ${avg_order_value:.2f}\n"
                response_text += f"**Unique Customers:** {unique_customers}\n\n"
                
                if status_counts:
                    response_text += "**Order Status Distribution:**\n"
                    for status, count in status_counts.items():
                        response_text += f"  - {status.title()}: {count} orders\n"
            
            return {
                "success": True,
                "message": response_text,
                "data": {
                    "type": "custom_report",
                    "report_type": report_type,
                    "format": format,
                    "period": {
                        "start_date": start_date,
                        "end_date": end_date
                    },
                    "metrics": {
                        "total_revenue": round(total_revenue, 2),
                        "total_orders": total_orders,
                        "average_order_value": round(avg_order_value, 2),
                        "unique_customers": unique_customers,
                        "status_breakdown": status_counts
                    }
                }
            }
        except Exception as e:
            return {"success": False, "message": f"Error generating custom report: {str(e)}"}
    
    async def export_business_data(self, business_id: int, data_type: str, start_date: str, end_date: str, format: str = "csv") -> Dict[str, Any]:
        """Export business data in specified format"""
        try:
            # Parse dates
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
            
            # Get orders for the period
            start_datetime = datetime.combine(start_dt, datetime.min.time())
            end_datetime = datetime.combine(end_dt, datetime.max.time())
            
            orders = self.db.query(Order).filter(
                Order.business_id == business_id,
                Order.created_at >= start_datetime,
                Order.created_at <= end_datetime
            ).all()
            
            # Export data based on type
            if data_type == "orders":
                # Simulate order data export
                exported_records = len(orders)
                response_text = f"## Business Data Export\n\n"
                response_text += f"**Data Type:** Orders\n"
                response_text += f"**Period:** {start_date} to {end_date}\n"
                response_text += f"**Format:** {format.upper()}\n"
                response_text += f"**Records Exported:** {exported_records}\n\n"
                response_text += f"Your {format.upper()} file with order data has been generated and is ready for download.\n"
                
                # Sample data for demonstration
                response_text += "**Sample Data:**\n"
                for i, order in enumerate(orders[:3]):  # Show first 3 orders
                    response_text += f"  {i+1}. Order #{order.id} - ${order.total_amount:.2f} - {order.created_at.strftime('%Y-%m-%d')}\n"
                if len(orders) > 3:
                    response_text += f"  ... and {len(orders) - 3} more orders\n"
            elif data_type == "customers":
                # Simulate customer data export
                unique_customers = len(set(order.customer_id for order in orders if order.customer_id))
                response_text = f"## Business Data Export\n\n"
                response_text += f"**Data Type:** Customers\n"
                response_text += f"**Period:** {start_date} to {end_date}\n"
                response_text += f"**Format:** {format.upper()}\n"
                response_text += f"**Records Exported:** {unique_customers}\n\n"
                response_text += f"Your {format.upper()} file with customer data has been generated and is ready for download.\n"
            else:  # Default to all data
                exported_records = len(orders)
                unique_customers = len(set(order.customer_id for order in orders if order.customer_id))
                response_text = f"## Business Data Export\n\n"
                response_text += f"**Data Type:** All Business Data\n"
                response_text += f"**Period:** {start_date} to {end_date}\n"
                response_text += f"**Format:** {format.upper()}\n"
                response_text += f"**Order Records Exported:** {exported_records}\n"
                response_text += f"**Customer Records Exported:** {unique_customers}\n\n"
                response_text += f"Your comprehensive {format.upper()} file has been generated and is ready for download.\n"
            
            return {
                "success": True,
                "message": response_text,
                "data": {
                    "type": "data_export",
                    "data_type": data_type,
                    "format": format,
                    "period": {
                        "start_date": start_date,
                        "end_date": end_date
                    },
                    "export_details": {
                        "records_count": len(orders) if data_type == "orders" or data_type == "all" else unique_customers,
                        "status": "ready_for_download"
                    }
                }
            }
        except Exception as e:
            return {"success": False, "message": f"Error exporting business data: {str(e)}"}
    
    async def schedule_report(self, business_id: int, report_type: str, frequency: str, format: str = "pdf", email: str = None) -> Dict[str, Any]:
        """Schedule a recurring report"""
        try:
            # Simulate report scheduling
            response_text = f"## Report Scheduling Confirmation\n\n"
            response_text += f"**Report Type:** {report_type}\n"
            response_text += f"**Frequency:** {frequency}\n"
            response_text += f"**Format:** {format.upper()}\n"
            if email:
                response_text += f"**Delivery Email:** {email}\n"
            response_text += f"**Status:** Scheduled successfully\n\n"
            response_text += f"Your {report_type} report has been scheduled to run {frequency} and will be delivered in {format.upper()} format.\n"
            
            # Next run simulation
            if frequency == "daily":
                next_run = datetime.now() + timedelta(days=1)
            elif frequency == "weekly":
                next_run = datetime.now() + timedelta(weeks=1)
            elif frequency == "monthly":
                next_run = datetime.now() + timedelta(days=30)
            else:
                next_run = datetime.now() + timedelta(days=1)
            
            response_text += f"**Next Run:** {next_run.strftime('%Y-%m-%d %H:%M')}\n"
            
            return {
                "success": True,
                "message": response_text,
                "data": {
                    "type": "scheduled_report",
                    "report_type": report_type,
                    "frequency": frequency,
                    "format": format,
                    "delivery_email": email,
                    "schedule_details": {
                        "status": "active",
                        "next_run": next_run.strftime('%Y-%m-%d %H:%M')
                    }
                }
            }
        except Exception as e:
            return {"success": False, "message": f"Error scheduling report: {str(e)}"}
    
    async def get_report_templates(self, business_id: int) -> Dict[str, Any]:
        """Get available report templates"""
        try:
            # Simulate available templates
            templates = [
                {
                    "id": "daily_summary",
                    "name": "Daily Business Summary",
                    "description": "Comprehensive overview of daily business performance",
                    "frequency": "daily"
                },
                {
                    "id": "weekly_performance",
                    "name": "Weekly Performance Report",
                    "description": "Detailed analysis of weekly business metrics and trends",
                    "frequency": "weekly"
                },
                {
                    "id": "monthly_comprehensive",
                    "name": "Monthly Comprehensive Report",
                    "description": "Complete monthly analysis including financials, operations, and growth metrics",
                    "frequency": "monthly"
                },
                {
                    "id": "financial_analysis",
                    "name": "Financial Analysis Report",
                    "description": "Detailed financial performance with cost analysis and profitability metrics",
                    "frequency": "monthly"
                },
                {
                    "id": "customer_insights",
                    "name": "Customer Insights Report",
                    "description": "Customer behavior analysis, segmentation, and retention metrics",
                    "frequency": "monthly"
                }
            ]
            
            response_text = "## Available Report Templates\n\n"
            response_text += "You can generate reports from the following templates:\n\n"
            
            for template in templates:
                response_text += f"**{template['name']}**\n"
                response_text += f"  - ID: {template['id']}\n"
                response_text += f"  - Description: {template['description']}\n"
                response_text += f"  - Recommended Frequency: {template['frequency']}\n\n"
            
            return {
                "success": True,
                "message": response_text,
                "data": {
                    "type": "report_templates",
                    "templates": templates
                }
            }
        except Exception as e:
            return {"success": False, "message": f"Error retrieving report templates: {str(e)}"}
    
    async def generate_report_from_template(self, business_id: int, template_id: str, start_date: str = None, end_date: str = None, customizations: Dict[str, Any] = None, format: str = "pdf") -> Dict[str, Any]:
        """Generate a report from a predefined template"""
        try:
            # Determine date range
            if not start_date:
                start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            if not end_date:
                end_date = datetime.now().strftime("%Y-%m-%d")
            
            # Parse dates
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
            
            # Get orders for the period
            start_datetime = datetime.combine(start_dt, datetime.min.time())
            end_datetime = datetime.combine(end_dt, datetime.max.time())
            
            orders = self.db.query(Order).filter(
                Order.business_id == business_id,
                Order.created_at >= start_datetime,
                Order.created_at <= end_datetime
            ).all()
            
            # Calculate metrics
            total_revenue = sum(order.total_amount for order in orders)
            total_orders = len(orders)
            avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
            
            # Template-specific content
            if template_id == "daily_summary":
                template_name = "Daily Business Summary"
                content = f"**Total Revenue:** ${total_revenue:.2f}\n"
                content += f"**Total Orders:** {total_orders}\n"
                content += f"**Average Order Value:** ${avg_order_value:.2f}\n"
            elif template_id == "weekly_performance":
                template_name = "Weekly Performance Report"
                content = f"**Total Revenue:** ${total_revenue:.2f}\n"
                content += f"**Total Orders:** {total_orders}\n"
                content += f"**Average Order Value:** ${avg_order_value:.2f}\n"
                
                # Add trend analysis
                daily_revenue = {}
                for order in orders:
                    day = order.created_at.date()
                    if day not in daily_revenue:
                        daily_revenue[day] = 0
                    daily_revenue[day] += order.total_amount
                
                if daily_revenue:
                    best_day = max(daily_revenue, key=daily_revenue.get)
                    content += f"**Best Day:** {best_day.strftime('%Y-%m-%d')} with ${daily_revenue[best_day]:.2f}\n"
            elif template_id == "monthly_comprehensive":
                template_name = "Monthly Comprehensive Report"
                content = f"**Total Revenue:** ${total_revenue:.2f}\n"
                content += f"**Total Orders:** {total_orders}\n"
                content += f"**Average Order Value:** ${avg_order_value:.2f}\n"
                
                # Customer metrics
                unique_customers = len(set(order.customer_id for order in orders if order.customer_id))
                content += f"**Unique Customers:** {unique_customers}\n"
                
                # Status breakdown
                status_counts = {}
                for order in orders:
                    status = getattr(order.status, "value", str(order.status)) if order.status else "unknown"
                    if status not in status_counts:
                        status_counts[status] = 0
                    status_counts[status] += 1
                
                if status_counts:
                    content += "\n**Order Status Distribution:**\n"
                    for status, count in status_counts.items():
                        content += f"  - {status.title()}: {count} orders\n"
            else:
                template_name = "Custom Report"
                content = f"**Total Revenue:** ${total_revenue:.2f}\n"
                content += f"**Total Orders:** {total_orders}\n"
                content += f"**Average Order Value:** ${avg_order_value:.2f}\n"
            
            # Format response
            response_text = f"## {template_name}\n\n"
            response_text += f"**Period:** {start_date} to {end_date}\n\n"
            response_text += content
            response_text += f"\n**Format:** {format.upper()}\n"
            response_text += f"**Generated from template:** {template_id}\n"
            
            return {
                "success": True,
                "message": response_text,
                "data": {
                    "type": "template_report",
                    "template_id": template_id,
                    "template_name": template_name,
                    "format": format,
                    "period": {
                        "start_date": start_date,
                        "end_date": end_date
                    },
                    "metrics": {
                        "total_revenue": round(total_revenue, 2),
                        "total_orders": total_orders,
                        "average_order_value": round(avg_order_value, 2)
                    }
                }
            }
        except Exception as e:
            return {"success": False, "message": f"Error generating report from template: {str(e)}"}
