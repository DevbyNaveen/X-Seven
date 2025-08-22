"""Universal Business Functions for AI Tool Calling

Implements the 5 core universal business functions that AI can call naturally:
1. find_businesses - Search businesses by category and criteria
2. get_services - Retrieve service offerings with prices  
3. get_booking_data - Resource availability checking
4. create_booking_record - Book appointments/reservations
5. create_order_record - Handle orders/payments

Supports all business categories: FOOD, BEAUTY, AUTOMOTIVE, HEALTH, LOCAL
"""
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.models import Business, MenuItem


class UniversalBusinessFunctions:
    """Universal business functions that AI can call naturally across all business categories."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def find_businesses(
        self,
        criteria: Optional[str] = None,
        category: Optional[str] = None,
        service_type: Optional[str] = None,
        location: Optional[str] = None,
        features: Optional[List[str]] = None,
        limit: int = 8
    ) -> Dict[str, Any]:
        """Search for businesses based on category and various criteria."""
        try:
            # Build search query
            query_filters = [Business.is_active == True]
            search_terms = []
            
            if criteria:
                search_term = f"%{criteria.strip().lower()}%"
                search_terms.extend([
                    Business.name.ilike(search_term),
                    Business.description.ilike(search_term),
                    Business.category.ilike(search_term)
                ])
            
            if category:
                category_term = f"%{category.strip().lower()}%"
                search_terms.extend([
                    Business.category.ilike(category_term),
                    Business.description.ilike(category_term)
                ])
            
            if service_type:
                service_term = f"%{service_type.strip().lower()}%"
                search_terms.extend([
                    Business.description.ilike(service_term),
                    Business.category.ilike(service_term)
                ])
            
            if location:
                location_term = f"%{location.strip().lower()}%"
                search_terms.extend([
                    Business.name.ilike(location_term),
                    Business.description.ilike(location_term)
                ])
            
            # Combine search terms with OR logic
            if search_terms:
                query_filters.append(or_(*search_terms))
            
            # Execute query
            businesses = self.db.query(Business).filter(
                and_(*query_filters)
            ).order_by(Business.name).limit(limit).all()
            
            # Format results with menu samples
            results = []
            for business in businesses:
                # Get sample menu items
                sample_items = self.db.query(MenuItem).filter(
                    MenuItem.business_id == business.id,
                    MenuItem.is_available == True
                ).order_by(MenuItem.display_order).limit(3).all()
                
                # Extract location from contact_info
                location_info = None
                if isinstance(business.contact_info, dict):
                    location_info = business.contact_info.get("address")
                
                # Extract operating hours from settings
                operating_hours = {}
                if isinstance(business.settings, dict):
                    operating_hours = business.settings.get("operating_hours", {})
                
                results.append({
                    "id": business.id,
                    "name": business.name,
                    "description": business.description,
                    "category": business.category,
                    "location": location_info,
                    "contact_info": business.contact_info,
                    "operating_hours": operating_hours,
                    "sample_menu": [
                        {
                            "name": item.name,
                            "price": float(item.base_price) if item.base_price else None,
                            "description": item.description
                        }
                        for item in sample_items
                    ]
                })
            
            return {
                "function": "find_businesses",
                "success": True,
                "results": results,
                "total_found": len(results),
                "search_criteria": {
                    "criteria": criteria,
                    "category": category,
                    "service_type": service_type,
                    "location": location,
                    "features": features
                }
            }
            
        except Exception as e:
            return {
                "function": "find_businesses",
                "success": False,
                "error": f"Search failed: {str(e)}",
                "results": []
            }
    
    def get_services(
        self,
        business_id: int,
        service_category: Optional[str] = None,
        search_term: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retrieve service offerings with prices for a specific business."""
        try:
            # Verify business exists
            business = self.db.query(Business).filter(
                Business.id == business_id,
                Business.is_active == True
            ).first()
            
            if not business:
                return {
                    "function": "get_services",
                    "success": False,
                    "error": "Business not found or inactive",
                    "business_id": business_id
                }
            
            # Build service query
            query = self.db.query(MenuItem).filter(
                MenuItem.business_id == business_id,
                MenuItem.is_available == True
            )
            
            if service_category:
                query = query.filter(MenuItem.category.ilike(f"%{service_category}%"))
            
            if search_term:
                search_like = f"%{search_term.strip().lower()}%"
                query = query.filter(or_(
                    MenuItem.name.ilike(search_like),
                    MenuItem.description.ilike(search_like),
                    MenuItem.ingredients.ilike(search_like)
                ))
            
            service_items = query.order_by(MenuItem.category, MenuItem.display_order).all()
            
            # Group by service category
            services_by_category = {}
            for item in service_items:
                cat = item.category or "Other"
                if cat not in services_by_category:
                    services_by_category[cat] = []
                
                services_by_category[cat].append({
                    "id": item.id,
                    "name": item.name,
                    "description": item.description,
                    "price": float(item.base_price) if item.base_price else None,
                    "ingredients": item.ingredients,
                    "allergens": item.allergens,
                    "customization_options": item.customization_options,
                    "nutritional_info": item.nutritional_info
                })
            
            return {
                "function": "get_services",
                "success": True,
                "business": {
                    "id": business.id,
                    "name": business.name,
                    "description": business.description,
                    "category": business.category
                },
                "services_by_category": services_by_category,
                "total_items": len(service_items),
                "filters_applied": {
                    "service_category": service_category,
                    "search_term": search_term
                }
            }
            
        except Exception as e:
            return {
                "function": "get_services",
                "success": False,
                "error": f"Failed to retrieve services: {str(e)}",
                "business_id": business_id
            }
    
    def get_booking_data(
        self,
        business_id: int,
        date: str,
        time: str,
        participants: int,
        service_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get all data needed for AI to analyze booking availability."""
        try:
            # Verify business exists
            business = self.db.query(Business).filter(
                Business.id == business_id,
                Business.is_active == True
            ).first()
            
            if not business:
                return {
                    "function": "get_booking_data",
                    "success": False,
                    "error": "Business not found or inactive",
                    "business_id": business_id
                }
            
            # Parse date and time
            try:
                booking_date = datetime.strptime(date, "%Y-%m-%d").date()
                booking_time = datetime.strptime(time, "%H:%M").time()
                booking_datetime = datetime.combine(booking_date, booking_time)
            except ValueError as e:
                return {
                    "function": "get_booking_data",
                    "success": False,
                    "error": f"Invalid date or time format: {str(e)}",
                    "expected_formats": "Date: YYYY-MM-DD, Time: HH:MM"
                }
            
            # Get business rules and settings
            business_settings = business.settings or {}
            operating_hours = business_settings.get("operating_hours", {})
            
            # Get existing bookings for the date (simulated)
            existing_bookings = self._get_existing_bookings(business_id, date)
            
            # Get resource availability (simulated)
            resource_availability = self._get_resource_availability(business_id, date, time)
            
            # Get business capacity info
            capacity_info = business_settings.get("capacity", {
                "total_capacity": 50,
                "max_party_size": 12,
                "peak_hours": ["12:00-14:00", "18:00-20:00"]
            })
            
            # Get booking rules
            booking_rules = business_settings.get("booking_rules", {
                "minimum_notice_hours": 2,
                "maximum_advance_days": 30,
                "last_booking_time": "21:30"
            })
            
            return {
                "function": "get_booking_data",
                "success": True,
                "business": {
                    "id": business.id,
                    "name": business.name,
                    "category": business.category,
                    "description": business.description
                },
                "requested": {
                    "date": date,
                    "time": time,
                    "participants": participants,
                    "service_type": service_type,
                    "datetime": booking_datetime.isoformat()
                },
                "business_rules": {
                    "operating_hours": operating_hours,
                    "capacity": capacity_info,
                    "booking_rules": booking_rules,
                    "peak_hours": capacity_info.get("peak_hours", [])
                },
                "existing_bookings": existing_bookings,
                "resource_availability": resource_availability,
                "current_datetime": datetime.now().isoformat(),
                "is_past_booking": booking_datetime <= datetime.now()
            }
            
        except Exception as e:
            return {
                "function": "get_booking_data",
                "success": False,
                "error": f"Failed to get booking data: {str(e)}",
                "business_id": business_id
            }
    
    def create_booking_record(
        self,
        business_id: int,
        customer_info: Dict[str, str],
        datetime_str: str,
        service_participants: int,
        service_type: Optional[str] = None,
        special_requests: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create booking record and return raw confirmation data."""
        try:
            # Verify business exists
            business = self.db.query(Business).filter(
                Business.id == business_id,
                Business.is_active == True
            ).first()
            
            if not business:
                return {
                    "function": "create_booking_record",
                    "success": False,
                    "error": "Business not found or inactive",
                    "business_id": business_id
                }
            
            # Validate customer info
            if not customer_info.get("name") or not customer_info.get("phone"):
                return {
                    "function": "create_booking_record",
                    "success": False,
                    "error": "Customer name and phone are required",
                    "provided_info": list(customer_info.keys())
                }
            
            # Parse datetime
            try:
                booking_datetime = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
            except ValueError as e:
                return {
                    "function": "create_booking_record",
                    "success": False,
                    "error": f"Invalid datetime format: {str(e)}",
                    "expected_format": "ISO format (YYYY-MM-DDTHH:MM:SS)"
                }
            
            # Generate booking ID and confirmation number
            booking_id = f"BK-{business_id}-{int(datetime.now().timestamp())}"
            confirmation_number = f"CONF-{booking_id[-8:]}"
            
            # Create booking record (simulated database operation)
            booking_data = {
                "id": booking_id,
                "confirmation_number": confirmation_number,
                "business_id": business_id,
                "business_name": business.name,
                "business_category": business.category,
                "business_description": business.description,
                "customer_name": customer_info["name"],
                "customer_phone": customer_info["phone"],
                "customer_email": customer_info.get("email"),
                "booking_datetime": booking_datetime.isoformat(),
                "participants": service_participants,
                "service_type": service_type,
                "special_requests": special_requests,
                "status": "confirmed",
                "created_at": datetime.now().isoformat()
            }
            
            # Get business contact and location info for AI to use
            business_contact = business.contact_info or {}
            business_settings = business.settings or {}
            
            # Extract location from contact_info if it's a dict
            business_location = None
            if isinstance(business_contact, dict):
                business_location = business_contact.get("address")
            
            operating_hours = business_settings.get("operating_hours", {})
            
            return {
                "function": "create_booking_record",
                "success": True,
                "booking": booking_data,
                "business_contact": business_contact,
                "business_location": business_location,
                "business_settings": business_settings,
                "operating_hours": operating_hours
            }
            
        except Exception as e:
            return {
                "function": "create_booking_record",
                "success": False,
                "error": f"Booking creation failed: {str(e)}",
                "business_id": business_id
            }
    
    def create_order_record(
        self,
        business_id: int,
        items: List[Dict[str, Any]],
        customer_info: Dict[str, str],
        payment_method: str = "cash",
        delivery_info: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Create order record and return raw transaction data."""
        try:
            # Verify business exists
            business = self.db.query(Business).filter(
                Business.id == business_id,
                Business.is_active == True
            ).first()
            
            if not business:
                return {
                    "function": "create_order_record",
                    "success": False,
                    "error": "Business not found or inactive",
                    "business_id": business_id
                }
            
            # Validate customer info
            if not customer_info.get("name") or not customer_info.get("phone"):
                return {
                    "function": "create_order_record",
                    "success": False,
                    "error": "Customer name and phone are required",
                    "provided_info": list(customer_info.keys())
                }
            
            # Process each item and calculate total
            order_items = []
            total_amount = 0.0
            
            for item_data in items:
                item_id = item_data.get("id")
                quantity = item_data.get("quantity", 1)
                customizations = item_data.get("customizations", [])
                
                # Get service item details
                service_item = self.db.query(MenuItem).filter(
                    MenuItem.id == item_id,
                    MenuItem.business_id == business_id,
                    MenuItem.is_available == True
                ).first()
                
                if not service_item:
                    return {
                        "function": "create_order_record",
                        "success": False,
                        "error": f"Service item with ID {item_id} not found or unavailable",
                        "business_id": business_id
                    }
                
                item_price = float(service_item.base_price) if service_item.base_price else 0.0
                item_total = item_price * quantity
                total_amount += item_total
                
                order_items.append({
                    "id": service_item.id,
                    "name": service_item.name,
                    "description": service_item.description,
                    "price": item_price,
                    "quantity": quantity,
                    "customizations": customizations,
                    "item_total": item_total,
                    "category": service_item.category
                })
            
            # Generate transaction ID and order number
            transaction_id = f"TXN-{business_id}-{int(datetime.now().timestamp())}"
            order_number = f"ORD-{transaction_id[-8:]}"
            
            # Calculate estimated completion time
            estimated_completion = datetime.now() + timedelta(minutes=30)
            
            # Create transaction record (simulated database operation)
            transaction_data = {
                "id": transaction_id,
                "order_number": order_number,
                "business_id": business_id,
                "business_name": business.name,
                "business_category": business.category,
                "business_description": business.description,
                "customer_name": customer_info["name"],
                "customer_phone": customer_info["phone"],
                "customer_email": customer_info.get("email"),
                "items": order_items,
                "total_amount": total_amount,
                "payment_method": payment_method,
                "delivery_info": delivery_info,
                "status": "confirmed",
                "estimated_completion": estimated_completion.isoformat(),
                "created_at": datetime.now().isoformat()
            }
            
            # Get business info for AI to use in response
            business_contact = business.contact_info or {}
            business_settings = business.settings or {}
            
            # Extract location from contact_info if it's a dict
            business_location = None
            if isinstance(business_contact, dict):
                business_location = business_contact.get("address")
            
            operating_hours = business_settings.get("operating_hours", {})
            
            return {
                "function": "create_order_record",
                "success": True,
                "transaction": transaction_data,
                "business_contact": business_contact,
                "business_location": business_location,
                "business_settings": business_settings,
                "operating_hours": operating_hours
            }
            
        except Exception as e:
            return {
                "function": "create_order_record",
                "success": False,
                "error": f"Order creation failed: {str(e)}",
                "business_id": business_id
            }
    
    # Helper methods for data retrieval
    def _get_existing_bookings(self, business_id: int, date: str) -> List[Dict[str, Any]]:
        """Get existing bookings for a business on a specific date (simulated)."""
        # In real implementation, this would query actual booking database
        import random
        
        # Generate realistic booking data based on business type
        bookings = []
        
        # Simulate peak lunch and dinner times
        peak_times = ["12:00", "12:30", "13:00", "18:30", "19:00", "19:30", "20:00"]
        
        for time_slot in random.sample(peak_times, random.randint(2, 5)):
            bookings.append({
                "time": time_slot,
                "party_size": random.randint(2, 6),
                "service_type": random.choice(["dining", "service", "consultation"]),
                "duration": random.randint(60, 120)
            })
        
        return sorted(bookings, key=lambda x: x["time"])
    
    def _get_resource_availability(self, business_id: int, date: str, time: str) -> Dict[str, Any]:
        """Get resource availability (staff, equipment, etc.) for a business (simulated)."""
        import random
        
        # Calculate time-based availability
        hour = int(time.split(":")[0])
        
        # Peak hours have lower availability
        if 12 <= hour <= 14 or 18 <= hour <= 20:
            staff_available = random.choice([True, False])  # 50% chance during peak
            capacity_utilization = random.uniform(0.7, 0.95)
        else:
            staff_available = True
            capacity_utilization = random.uniform(0.3, 0.7)
        
        return {
            "staff_available": staff_available,
            "equipment_available": True,
            "capacity_utilization": round(capacity_utilization, 2),
            "special_events": [],
            "recommended_alternatives": self._generate_alternative_times(time) if not staff_available else []
        }
    
    def _generate_alternative_times(self, requested_time: str) -> List[str]:
        """Generate alternative time suggestions when requested time is unavailable."""
        try:
            hour = int(requested_time.split(":")[0])
            minute = int(requested_time.split(":")[1])
            
            alternatives = []
            
            # Suggest times 30-60 minutes before and after
            for offset in [-60, -30, 30, 60]:
                new_hour = hour
                new_minute = minute + offset
                
                # Handle minute overflow
                if new_minute >= 60:
                    new_hour += 1
                    new_minute -= 60
                elif new_minute < 0:
                    new_hour -= 1
                    new_minute += 60
                
                # Keep within business hours (9 AM to 9 PM)
                if 9 <= new_hour <= 21:
                    alternatives.append(f"{new_hour:02d}:{new_minute:02d}")
            
            return alternatives[:3]  # Return top 3 alternatives
            
        except Exception:
            # Fallback alternatives
            return ["11:30", "14:30", "16:00"]