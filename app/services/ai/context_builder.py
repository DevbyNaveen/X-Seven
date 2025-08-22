"""Rich Context Builder

Builds comprehensive context for AI that includes all relevant business data,
conversation history, and user information in a single call.
This replaces complex state management with natural context understanding.
"""
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models import Business, MenuItem, Message


class RichContextBuilder:
    """Builds comprehensive context for AI conversations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def build_context(
        self,
        *,
        session_id: str,
        user_message: str,
        selected_business_id: Optional[int] = None,
        location: Optional[Dict[str, Any]] = None,
        phone_number: Optional[str] = None,
        max_history_messages: int = 15,
        max_businesses: Optional[int] = None
    ) -> Dict[str, Any]:
        """Build rich context including all businesses, intelligence data, and conversation history."""
        context = {
            "current_datetime": datetime.now().isoformat(),
            "user_message": user_message,
            "session_id": session_id,
            "location": location,
            "phone_number": phone_number,
        }
        
        # Get all active businesses with their complete information
        context["businesses"] = self._get_all_businesses(limit=max_businesses)
        
        # Add system-wide business intelligence for AI decision making
        context["system_intelligence"] = {
            "current_time_analysis": self._analyze_current_time(),
            "market_conditions": self._get_market_conditions(),
            "ai_decision_guidelines": self._get_ai_decision_guidelines()
        }
        
        # Get conversation history for natural memory
        context["conversation_history"] = self._get_conversation_history(
            session_id=session_id,
            selected_business_id=selected_business_id,
            max_messages=max_history_messages
        )
        
        # If a business is selected, include detailed information
        if selected_business_id:
            context["selected_business"] = self._get_business_details(selected_business_id)
        
        return context
    
    def _analyze_current_time(self) -> Dict[str, Any]:
        """Analyze current time for business decision making."""
        now = datetime.now()
        
        return {
            "current_hour": now.hour,
            "current_day": now.strftime('%A').lower(),
            "is_weekend": now.weekday() >= 5,
            "is_peak_time": 12 <= now.hour <= 14 or 18 <= now.hour <= 20,
            "is_business_hours": 9 <= now.hour <= 21,
            "time_until_close": max(0, 21 - now.hour) if now.hour < 21 else 0
        }
    
    def _get_market_conditions(self) -> Dict[str, Any]:
        """Get current market conditions for intelligent recommendations."""
        return {
            "demand_level": "moderate",
            "competition_level": "high",
            "customer_price_sensitivity": "moderate",
            "service_quality_expectations": "high",
            "booking_urgency_trends": "increasing_same_day_bookings"
        }
    
    def _get_ai_decision_guidelines(self) -> Dict[str, Any]:
        """Provide AI with intelligent decision-making guidelines."""
        return {
            "availability_analysis": {
                "consider_factors": ["current_utilization", "staff_availability", "time_constraints", "service_complexity"],
                "peak_time_strategy": "suggest_alternative_times_or_express_service",
                "off_peak_strategy": "promote_availability_and_potential_discounts",
                "full_capacity_strategy": "offer_waitlist_or_next_available_slot"
            },
            "recommendation_logic": {
                "new_customers": "prioritize_popular_services_and_good_value",
                "returning_customers": "suggest_based_on_history_and_preferences",
                "group_bookings": "check_capacity_and_suggest_optimal_times",
                "urgent_requests": "find_immediate_availability_or_alternatives"
            },
            "pricing_intelligence": {
                "peak_time_adjustments": "inform_about_potential_premium_pricing",
                "off_peak_incentives": "highlight_better_availability_and_value",
                "package_deals": "suggest_bundled_services_for_better_value",
                "loyalty_benefits": "mention_repeat_customer_advantages"
            }
        }
    
    def _get_all_businesses(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all active businesses with their basic info and sample menu items."""
        try:
            query = self.db.query(Business).filter(
                Business.is_active == True
            ).order_by(Business.name)
            
            if limit and limit > 0:
                query = query.limit(limit)
                
            businesses = query.all()
            
            business_data = []
            for business in businesses:
                # Get top 5 popular menu items for each business
                menu_items = self.db.query(MenuItem).filter(
                    MenuItem.business_id == business.id,
                    MenuItem.is_available == True
                ).order_by(MenuItem.display_order).limit(5).all()
                
                # Generate business intelligence data
                business_intelligence = self._generate_business_intelligence(business)
                
                business_info = {
                    "id": business.id,
                    "name": business.name,
                    "description": business.description,
                    "category": business.category,
                    "contact_info": business.contact_info,
                    "location": (business.contact_info or {}).get("address") if isinstance(business.contact_info, dict) else None,
                    "operating_hours": (business.settings or {}).get("operating_hours"),
                    "business_intelligence": business_intelligence,
                    "sample_service_offerings": [
                        {
                            "id": item.id,
                            "name": item.name,
                            "description": item.description,
                            "price": float(item.base_price) if item.base_price else None,
                            "category": item.category
                        }
                        for item in menu_items
                    ]
                }
                business_data.append(business_info)
            
            return business_data
            
        except Exception as e:
            print(f"Error getting businesses: {e}")
            return []
    
    def _get_business_details(self, business_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed information for a specific business including full menu."""
        try:
            business = self.db.query(Business).filter(
                Business.id == business_id,
                Business.is_active == True
            ).first()
            
            if not business:
                return None
            
            # Get all service offerings for this business
            service_items = self.db.query(MenuItem).filter(
                MenuItem.business_id == business_id,
                MenuItem.is_available == True
            ).order_by(MenuItem.category, MenuItem.display_order).all()
            
            # Group service offerings by category
            services_by_category = {}
            for item in service_items:
                category = item.category or "Other"
                if category not in services_by_category:
                    services_by_category[category] = []
                
                services_by_category[category].append({
                    "id": item.id,
                    "name": item.name,
                    "description": item.description,
                    "price": float(item.base_price) if item.base_price else None,
                    "ingredients": item.ingredients,
                    "allergens": item.allergens,
                    "nutritional_info": item.nutritional_info,
                    "customization_options": item.customization_options
                })
            
            # Generate detailed business intelligence
            business_intelligence = self._generate_business_intelligence(business)
            business_rules = self._generate_business_rules(business)
            
            return {
                "id": business.id,
                "name": business.name,
                "description": business.description,
                "category": business.category,
                "contact_info": business.contact_info,
                "location": (business.contact_info or {}).get("address") if isinstance(business.contact_info, dict) else None,
                "operating_hours": (business.settings or {}).get("operating_hours"),
                "settings": business.settings,
                "business_intelligence": business_intelligence,
                "business_rules": business_rules,
                "services_by_category": services_by_category,
                "total_service_items": len(service_items)
            }
            
        except Exception as e:
            print(f"Error getting business details: {e}")
            return None
    
    def _get_conversation_history(
        self,
        session_id: str,
        selected_business_id: Optional[int] = None,
        max_messages: int = 15
    ) -> List[Dict[str, str]]:
        """Get recent conversation history for natural context."""
        try:
            # Get messages from the last 3 hours to avoid stale context
            cutoff_time = datetime.utcnow() - timedelta(hours=3)
            
            query = self.db.query(Message).filter(
                Message.session_id == session_id,
                Message.created_at >= cutoff_time
            )
            
            # If business is selected, prioritize messages from that business
            if selected_business_id:
                query = query.filter(Message.business_id == selected_business_id)
            
            messages = query.order_by(Message.created_at.desc()).limit(max_messages).all()
            messages = list(reversed(messages))  # Chronological order
            
            history = []
            for msg in messages:
                role = "assistant" if msg.sender_type == "bot" else "user"
                history.append({
                    "role": role,
                    "content": msg.content or "",
                    "timestamp": msg.created_at.isoformat(),
                    "business_id": msg.business_id
                })
            
            return history
            
        except Exception as e:
            print(f"Error getting conversation history: {e}")
            return []
    
    def _generate_business_intelligence(self, business: Business) -> Dict[str, Any]:
        """Generate intelligent business data for AI decision making."""
        current_hour = datetime.now().hour
        current_day = datetime.now().strftime('%A').lower()
        
        # Business category-specific intelligence
        category_intelligence = self._get_category_intelligence(business.category)
        
        # Simulate realistic business intelligence data
        intelligence = {
            "capacity_info": {
                "total_capacity": category_intelligence["base_capacity"],
                "current_utilization": self._calculate_current_utilization(current_hour, current_day),
                "peak_hours": category_intelligence["peak_hours"],
                "off_peak_hours": category_intelligence["off_peak_hours"],
                "average_service_time": category_intelligence["avg_service_time"]
            },
            "demand_patterns": {
                "high_demand_days": ["friday", "saturday", "sunday"],
                "low_demand_days": ["monday", "tuesday"],
                "seasonal_trends": category_intelligence["seasonal_trends"],
                "booking_lead_time": category_intelligence["booking_lead_time"]
            },
            "customer_insights": {
                "average_party_size": category_intelligence["avg_party_size"],
                "popular_services": category_intelligence["popular_services"],
                "customer_preferences": category_intelligence["preferences"],
                "repeat_customer_rate": 0.65
            },
            "operational_status": {
                "staff_availability": self._get_staff_availability(current_hour, current_day),
                "equipment_status": "fully_operational",
                "special_events": [],
                "maintenance_schedule": []
            }
        }
        
        return intelligence
    
    def _generate_business_rules(self, business: Business) -> Dict[str, Any]:
        """Generate business rules and policies for AI to understand."""
        category = business.category or "general"
        
        # Category-specific business rules
        if "food" in category.lower() or "restaurant" in category.lower():
            rules = {
                "booking_rules": {
                    "minimum_notice_hours": 2,
                    "maximum_advance_days": 30,
                    "cancellation_policy": "24_hours_notice",
                    "no_show_policy": "charge_fee",
                    "peak_time_restrictions": True
                },
                "service_rules": {
                    "last_order_time": "30_minutes_before_close",
                    "kitchen_prep_time": 15,
                    "delivery_radius_km": 5,
                    "minimum_order_delivery": 25.0
                },
                "payment_policies": {
                    "accepted_methods": ["cash", "card", "digital"],
                    "deposit_required": False,
                    "group_booking_deposit": True
                }
            }
        elif "beauty" in category.lower() or "salon" in category.lower():
            rules = {
                "booking_rules": {
                    "minimum_notice_hours": 4,
                    "maximum_advance_days": 60,
                    "cancellation_policy": "4_hours_notice",
                    "no_show_policy": "charge_50_percent",
                    "consultation_required": True
                },
                "service_rules": {
                    "service_buffer_time": 15,
                    "consultation_time": 15,
                    "equipment_setup_time": 10,
                    "cleanup_time": 10
                },
                "payment_policies": {
                    "accepted_methods": ["cash", "card"],
                    "deposit_required": True,
                    "deposit_percentage": 50
                }
            }
        elif "automotive" in category.lower():
            rules = {
                "booking_rules": {
                    "minimum_notice_hours": 24,
                    "maximum_advance_days": 90,
                    "cancellation_policy": "24_hours_notice",
                    "vehicle_info_required": True,
                    "diagnostic_time": 30
                },
                "service_rules": {
                    "inspection_time": 15,
                    "parts_availability_check": True,
                    "warranty_period_days": 30,
                    "pickup_delivery_available": True
                },
                "payment_policies": {
                    "accepted_methods": ["cash", "card", "financing"],
                    "estimate_required": True,
                    "deposit_for_parts": True
                }
            }
        elif "health" in category.lower() or "medical" in category.lower():
            rules = {
                "booking_rules": {
                    "minimum_notice_hours": 24,
                    "maximum_advance_days": 180,
                    "cancellation_policy": "24_hours_notice",
                    "insurance_verification": True,
                    "new_patient_forms": True
                },
                "service_rules": {
                    "consultation_time": 30,
                    "follow_up_required": True,
                    "referral_system": True,
                    "emergency_slots": True
                },
                "payment_policies": {
                    "accepted_methods": ["cash", "card", "insurance"],
                    "insurance_copay": True,
                    "payment_plans_available": True
                }
            }
        else:
            # General local services
            rules = {
                "booking_rules": {
                    "minimum_notice_hours": 4,
                    "maximum_advance_days": 30,
                    "cancellation_policy": "2_hours_notice",
                    "site_visit_required": False
                },
                "service_rules": {
                    "travel_time": 15,
                    "setup_time": 10,
                    "cleanup_time": 10,
                    "materials_included": True
                },
                "payment_policies": {
                    "accepted_methods": ["cash", "card"],
                    "deposit_required": False,
                    "payment_on_completion": True
                }
            }
        
        return rules
    
    def _get_category_intelligence(self, category: str) -> Dict[str, Any]:
        """Get category-specific intelligence patterns."""
        category = (category or "").lower()
        
        if "food" in category or "restaurant" in category:
            return {
                "base_capacity": 60,
                "peak_hours": ["12:00-14:00", "18:00-21:00"],
                "off_peak_hours": ["15:00-17:00", "21:30-23:00"],
                "avg_service_time": 90,
                "avg_party_size": 2.5,
                "booking_lead_time": "same_day",
                "seasonal_trends": ["busy_weekends", "holiday_rush"],
                "popular_services": ["dinner", "brunch", "takeout"],
                "preferences": ["outdoor_seating", "quick_service", "dietary_options"]
            }
        elif "beauty" in category or "salon" in category:
            return {
                "base_capacity": 8,
                "peak_hours": ["10:00-12:00", "14:00-18:00"],
                "off_peak_hours": ["09:00-10:00", "18:00-20:00"],
                "avg_service_time": 60,
                "avg_party_size": 1.2,
                "booking_lead_time": "1_week",
                "seasonal_trends": ["wedding_season", "holiday_prep"],
                "popular_services": ["haircut", "color", "manicure"],
                "preferences": ["experienced_stylist", "organic_products", "relaxing_atmosphere"]
            }
        elif "automotive" in category:
            return {
                "base_capacity": 4,
                "peak_hours": ["08:00-10:00", "16:00-18:00"],
                "off_peak_hours": ["10:00-15:00"],
                "avg_service_time": 120,
                "avg_party_size": 1.0,
                "booking_lead_time": "3_days",
                "seasonal_trends": ["winter_maintenance", "summer_ac_service"],
                "popular_services": ["oil_change", "brake_service", "diagnostics"],
                "preferences": ["quick_turnaround", "warranty", "pickup_delivery"]
            }
        elif "health" in category or "medical" in category:
            return {
                "base_capacity": 12,
                "peak_hours": ["09:00-11:00", "14:00-16:00"],
                "off_peak_hours": ["11:00-14:00", "16:00-17:00"],
                "avg_service_time": 30,
                "avg_party_size": 1.0,
                "booking_lead_time": "1_week",
                "seasonal_trends": ["flu_season", "back_to_school"],
                "popular_services": ["checkup", "consultation", "treatment"],
                "preferences": ["short_wait_time", "experienced_provider", "insurance_accepted"]
            }
        else:
            return {
                "base_capacity": 20,
                "peak_hours": ["09:00-12:00", "14:00-17:00"],
                "off_peak_hours": ["12:00-14:00", "17:00-18:00"],
                "avg_service_time": 60,
                "avg_party_size": 1.5,
                "booking_lead_time": "2_days",
                "seasonal_trends": ["spring_cleaning", "holiday_prep"],
                "popular_services": ["consultation", "standard_service", "premium_service"],
                "preferences": ["reliable_service", "fair_pricing", "professional_staff"]
            }
    
    def _calculate_current_utilization(self, hour: int, day: str) -> float:
        """Calculate realistic current capacity utilization."""
        # Base utilization patterns
        if day in ['saturday', 'sunday']:
            base_utilization = 0.8
        elif day in ['friday']:
            base_utilization = 0.7
        else:
            base_utilization = 0.6
        
        # Hour-based adjustments
        if 12 <= hour <= 14 or 18 <= hour <= 20:  # Peak hours
            base_utilization += 0.15
        elif 15 <= hour <= 17:  # Off-peak
            base_utilization -= 0.2
        elif hour < 9 or hour > 21:  # Very off-peak
            base_utilization -= 0.3
        
        # Ensure realistic bounds
        return max(0.1, min(0.95, base_utilization))
    
    def _get_staff_availability(self, hour: int, day: str) -> str:
        """Get current staff availability status."""
        utilization = self._calculate_current_utilization(hour, day)
        
        if utilization > 0.9:
            return "limited"
        elif utilization > 0.7:
            return "moderate"
        else:
            return "good"