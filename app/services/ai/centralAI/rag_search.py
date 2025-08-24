# app/services/ai/rag_search.py
"""
RAG Search Module for Central AI
Implements database search capabilities using Retrieval-Augmented Generation
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func

from app.models import Business, MenuItem, Message, Order


# Category context for intelligent understanding
CATEGORY_CONTEXT = {
    "FOOD & HOSPITALITY": {
        "keywords": ["restaurant", "cafe", "bar", "food", "dining", "eat", "menu", "order", "delivery", "pizza", "burger", "coffee", "dinner", "lunch", "brunch"],
        "description": "Restaurants, cafes, bars, bakeries, food trucks",
        "services": ["QR ordering", "table management", "multi-language menus", "kitchen display"],
        "user_intents": ["hungry", "want to eat", "looking for food", "dinner", "lunch", "brunch", "takeout", "delivery"]
    },
    "BEAUTY & PERSONAL CARE": {
        "keywords": ["salon", "hair", "beauty", "barber", "spa", "nail", "cut", "color", "manicure", "massage", "trim", "style", "treatment"],
        "description": "Hair salons, nail salons, beauty salons, barber shops, spas",
        "services": ["Appointment scheduling", "stylist management", "deposit handling", "reminders"],
        "user_intents": ["haircut", "color", "beauty", "spa", "nail", "manicure", "trim", "facial", "waxing"]
    },
    "AUTOMOTIVE SERVICES": {
        "keywords": ["car", "auto", "repair", "wash", "tire", "oil", "mechanic", "vehicle", "service", "maintenance", "brake"],
        "description": "Auto repair shops, car washes, tire centers, oil change services",
        "services": ["Service bay management", "parts coordination", "progress updates", "emergency service"],
        "user_intents": ["car repair", "oil change", "tire", "car wash", "vehicle service", "maintenance", "brake service"]
    },
    "HEALTH & MEDICAL": {
        "keywords": ["doctor", "clinic", "dental", "health", "medical", "physio", "vet", "appointment", "checkup", "treatment"],
        "description": "Dental clinics, physiotherapy, general practice, veterinary clinics",
        "services": ["Insurance verification", "emergency appointments", "medical history", "HIPAA compliance"],
        "user_intents": ["doctor", "dentist", "health check", "medical", "appointment", "checkup", "treatment", "consultation"]
    },
    "LOCAL SERVICES": {
        "keywords": ["cleaning", "pet", "tutor", "repair", "landscaping", "service", "home", "moving", "plumber", "electrician"],
        "description": "Cleaning services, pet grooming, tutoring, home repair, landscaping",
        "services": ["Mobile service coordination", "location-based scheduling", "recurring services"],
        "user_intents": ["cleaning", "pet grooming", "tutor", "home repair", "landscaping", "service", "plumber", "electrician"]
    }
}


class CategoryClassifier:
    """Intelligent category classification based on user intent"""
    
    @staticmethod
    def classify_user_intent(user_message: str) -> Dict[str, Any]:
        """Let LLM understand user intent naturally"""
        user_message_lower = user_message.lower()
        
        # Find matching categories based on keywords
        matched_categories = []
        confidence_scores = {}
        
        for category, info in CATEGORY_CONTEXT.items():
            score = 0
            matched_keywords = []
            
            # Check keywords (weight: 2)
            for keyword in info["keywords"]:
                if keyword in user_message_lower:
                    score += 2
                    matched_keywords.append(keyword)
            
            # Check user intents (weight: 3)
            for intent in info["user_intents"]:
                if intent in user_message_lower:
                    score += 3
                    matched_keywords.append(f"intent:{intent}")
            
            # Check category name mentions (weight: 4)
            category_variants = [
                category.lower(),
                category.lower().replace("&", "and"),
                category.lower().replace(" & ", " "),
                category.lower().replace("_", " ")
            ]
            
            for variant in category_variants:
                if variant in user_message_lower:
                    score += 4
                    matched_keywords.append(f"category:{category}")
                    break
            
            if score > 0:
                matched_categories.append(category)
                confidence_scores[category] = {
                    "score": score,
                    "matched_terms": matched_keywords
                }
        
        # Sort by confidence
        sorted_categories = sorted(
            confidence_scores.items(), 
            key=lambda x: x[1]["score"], 
            reverse=True
        )
        
        return {
            "primary_category": sorted_categories[0][0] if sorted_categories else None,
            "all_matches": sorted_categories,
            "confidence_scores": confidence_scores
        }
    
    @staticmethod
    def get_category_info(category_name: str) -> Dict[str, Any]:
        """Get detailed information about a category"""
        return CATEGORY_CONTEXT.get(category_name.upper(), {})
    
    @staticmethod
    def get_all_categories() -> List[str]:
        """Get list of all supported categories"""
        return list(CATEGORY_CONTEXT.keys())


class RAGSearch:
    """
    RAG Search class that provides database search capabilities for the AI.
    This helps the AI understand user queries and search the database accordingly.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def search_businesses(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Search for businesses based on a query string and optional filters.
        
        Args:
            query: Search query string
            filters: Optional dictionary of filters (category, location, etc.)
            
        Returns:
            List of matching businesses with relevant information
        """
        try:
            # Start building the query
            db_query = self.db.query(Business).filter(Business.is_active == True)
            
            # Apply text search if query is provided
            if query:
                search_terms = query.split()
                or_conditions = []
                
                for term in search_terms:
                    term_filter = f"%{term}%"
                    or_conditions.append(or_(
                        Business.name.ilike(term_filter),
                        Business.description.ilike(term_filter),
                        Business.category.ilike(term_filter)
                    ))
                
                if or_conditions:
                    db_query = db_query.filter(or_(*or_conditions))
            
            # Apply additional filters
            if filters:
                if 'category' in filters and filters['category']:
                    db_query = db_query.filter(Business.category.ilike(f"%{filters['category']}%"))
                
                # Add more filters as needed
                if 'business_ids' in filters and filters['business_ids']:
                    db_query = db_query.filter(Business.id.in_(filters['business_ids']))
                
                if 'min_rating' in filters and filters['min_rating']:
                    # Assuming Business has rating field
                    if hasattr(Business, 'rating'):
                        db_query = db_query.filter(Business.rating >= filters['min_rating'])
            
            # Execute query and format results
            businesses = db_query.limit(30).all()
            
            results = []
            for business in businesses:
                # Get sample menu items for context
                menu_items = self.db.query(MenuItem).filter(
                    MenuItem.business_id == business.id,
                    MenuItem.is_available == True
                ).limit(5).all()
                
                results.append({
                    "id": business.id,
                    "name": business.name,
                    "category": business.category,
                    "description": business.description,
                    "sample_menu": [
                        {
                            "id": item.id,
                            "name": item.name,
                            "description": item.description,
                            "price": float(item.base_price or 0)
                        } for item in menu_items
                    ]
                })
            
            return results
            
        except Exception as e:
            # Log error but don't crash
            print(f"Error in search_businesses: {str(e)}")
            return []

    def search_menu_items(self, query: str, business_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Search for menu items across businesses or within a specific business.
        
        Args:
            query: Search query string
            business_id: Optional business ID to limit search scope
            
        Returns:
            List of matching menu items
        """
        try:
            # Start building the query
            db_query = self.db.query(MenuItem).filter(MenuItem.is_available == True)
            
            # Limit to specific business if provided
            if business_id:
                db_query = db_query.filter(MenuItem.business_id == business_id)
            
            # Apply text search
            if query:
                search_terms = query.split()
                or_conditions = []
                
                for term in search_terms:
                    term_filter = f"%{term}%"
                    or_conditions.append(or_(
                        MenuItem.name.ilike(term_filter),
                        MenuItem.description.ilike(term_filter),
                        MenuItem.category_id.ilike(term_filter) if hasattr(MenuItem, 'category_id') and MenuItem.category_id else None
                    ))
                
                # Remove None values
                or_conditions = [cond for cond in or_conditions if cond is not None]
                
                if or_conditions:
                    db_query = db_query.filter(or_(*or_conditions))
            
            # Execute query and format results
            menu_items = db_query.limit(20).all()
            
            results = []
            for item in menu_items:
                # Get business info for context
                business = self.db.query(Business).filter(Business.id == item.business_id).first()
                
                results.append({
                    "id": item.id,
                    "name": item.name,
                    "description": item.description,
                    "price": float(item.base_price or 0),
                    "business": {
                        "id": business.id if business else None,
                        "name": business.name if business else "Unknown"
                    } if business else None
                })
            
            return results
            
        except Exception as e:
            print(f"Error in search_menu_items: {str(e)}")
            return []

    def get_business_context(self, business_id: int) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive context information for a specific business.
        
        Args:
            business_id: Business ID
            
        Returns:
            Dictionary with business context or None if not found
        """
        try:
            business = self.db.query(Business).filter(Business.id == business_id).first()
            
            if not business:
                return None
            
            # Get menu items
            menu_items = self.db.query(MenuItem).filter(
                MenuItem.business_id == business_id,
                MenuItem.is_available == True
            ).all()
            
            # Get recent orders (last 5)
            recent_orders = self.db.query(Order).filter(
                Order.business_id == business_id
            ).order_by(Order.created_at.desc()).limit(5).all()
            
            return {
                "business": {
                    "id": business.id,
                    "name": business.name,
                    "category": business.category,
                    "description": business.description,
                    "is_active": business.is_active
                },
                "menu": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "description": item.description,
                        "price": float(item.base_price or 0),
                        "category": item.category_id if hasattr(item, 'category_id') else None
                    } for item in menu_items
                ],
                "recent_orders": [
                    {
                        "id": order.id,
                        "customer_name": order.customer_name,
                        "total_amount": float(order.total_amount or 0),
                        "status": order.status.value if hasattr(order.status, 'value') else str(order.status),
                        "created_at": order.created_at.isoformat() if order.created_at else None
                    } for order in recent_orders
                ]
            }
            
        except Exception as e:
            print(f"Error in get_business_context: {str(e)}")
            return None

    def search_conversation_history(self, session_id: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search through conversation history for relevant context.
        
        Args:
            session_id: Session identifier
            query: Search query string
            limit: Maximum number of results to return
            
        Returns:
            List of relevant conversation messages
        """
        try:
            db_query = self.db.query(Message).filter(Message.session_id == session_id)
            
            # Apply text search if query provided
            if query:
                search_terms = query.split()
                or_conditions = []
                
                for term in search_terms:
                    term_filter = f"%{term}%"
                    or_conditions.append(Message.content.ilike(term_filter))
                
                if or_conditions:
                    db_query = db_query.filter(or_(*or_conditions))
            
            # Order by created time and limit results
            messages = db_query.order_by(Message.created_at.desc()).limit(limit).all()
            
            return [
                {
                    "id": msg.id,
                    "content": msg.content,
                    "sender_type": msg.sender_type,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None
                } for msg in reversed(messages)  # Reverse to show chronological order
            ]
            
        except Exception as e:
            print(f"Error in search_conversation_history: {str(e)}")
            return []

    def extract_entities_from_query(self, query: str) -> Dict[str, Any]:
        """
        Extract potential entities and intent from a user query.
        This is a simple rule-based approach that could be enhanced with ML.
        
        Args:
            query: User query string
            
        Returns:
            Dictionary with extracted entities and intent
        """
        query_lower = query.lower()
        
        # Simple entity extraction based on keywords
        entities = {
            "business_types": [],
            "menu_items": [],
            "actions": [],
            "intent": "general_inquiry"
        }
        
        # Business types
        business_keywords = [
            ("restaurant", ["restaurant", "diner", "cafe", "eatery", "food", "dining"]),
            ("salon", ["salon", "spa", "barber", "beauty", "hair"]),
            ("store", ["store", "shop", "retail", "boutique"]),
            ("service", ["service", "repair", "cleaning", "consulting", "maintenance"]),
            ("medical", ["doctor", "clinic", "hospital", "dentist", "medical"])
        ]
        
        for category, keywords in business_keywords:
            if any(keyword in query_lower for keyword in keywords):
                entities["business_types"].append(category)
        
        # Actions
        action_keywords = [
            "book", "order", "reserve", "schedule", "menu", "price", "cost", 
            "cut", "color", "wash", "repair", "checkup", "clean"
        ]
        for action in action_keywords:
            if action in query_lower:
                entities["actions"].append(action)
        
        # Menu items (simple extraction)
        menu_keywords = [
            "pizza", "coffee", "haircut", "color", "manicure", "burger", 
            "oil change", "tire", "cleaning", "tutoring"
        ]
        for item in menu_keywords:
            if item in query_lower:
                entities["menu_items"].append(item)
        
        # Determine intent based on actions
        if any(action in ["book", "reserve", "schedule"] for action in entities["actions"]):
            entities["intent"] = "booking_request"
        elif any(action in ["order", "menu", "price", "cost"] for action in entities["actions"]):
            entities["intent"] = "order_request"
        elif any(action in ["repair", "wash", "service"] for action in entities["actions"]):
            entities["intent"] = "service_request"
        elif any(action in ["checkup", "doctor", "dentist"] for action in entities["actions"]):
            entities["intent"] = "medical_request"
        
        return entities

    def semantic_business_match(self, user_query: str, business_list: List[Dict]) -> List[Dict]:
        """
        Enhanced semantic matching for business names.
        Prevents hallucination by only returning actual businesses.
        
        Args:
            user_query: User's input query
            business_list: List of actual businesses from database
            
        Returns:
            List of businesses that match the query
        """
        user_query_lower = user_query.strip().lower()
        matched_businesses = []
        
        # Direct name matching
        for business in business_list:
            business_name_lower = business['name'].lower()
            
            # Exact match
            if business_name_lower == user_query_lower:
                matched_businesses.append(business)
                continue
                
            # Partial match
            if user_query_lower in business_name_lower or business_name_lower in user_query_lower:
                matched_businesses.append(business)
                continue
                
            # Category match
            if 'category' in business and user_query_lower in business['category'].lower():
                matched_businesses.append(business)
                continue
        
        return matched_businesses

    def get_category_based_businesses(self, user_query: str, all_businesses: List[Dict], limit: int = 10) -> List[Dict]:
        """
        Get businesses based on category classification of user query.
        
        Args:
            user_query: User's input query
            all_businesses: All available businesses
            limit: Maximum number of businesses to return
            
        Returns:
            List of relevant businesses based on category
        """
        # Classify user intent
        category_analysis = CategoryClassifier.classify_user_intent(user_query)
        primary_category = category_analysis.get("primary_category")
        
        if not primary_category:
            return all_businesses[:limit]  # Return top businesses if no category detected
        
        # Filter businesses by primary category
        relevant_businesses = [
            biz for biz in all_businesses 
            if biz.get('category', '').upper() == primary_category
        ]
        
        # If no businesses in primary category, try secondary categories
        if not relevant_businesses:
            all_matches = category_analysis.get("all_matches", [])
            for category_match in all_matches[1:]:  # Skip primary, try others
                category_name = category_match[0]
                relevant_businesses = [
                    biz for biz in all_businesses 
                    if biz.get('category', '').upper() == category_name
                ]
                if relevant_businesses:
                    break
        
        return relevant_businesses[:limit] if relevant_businesses else all_businesses[:limit]

    def test_search_functionality(self):
        """
        Test method to verify RAGSearch functionality.
        This method demonstrates how the RAGSearch class works.
        """
        try:
            # Test business search with an empty query (should return all businesses)
            all_businesses = self.search_businesses("")
            print(f"Found {len(all_businesses)} businesses in total")
            
            # Test business search with a specific query
            restaurants = self.search_businesses("restaurant")
            print(f"Found {len(restaurants)} restaurants")
            
            # Test menu item search
            menu_items = self.search_menu_items("coffee")
            print(f"Found {len(menu_items)} menu items with 'coffee'")
            
            # Test entity extraction
            sample_query = "I want to book a table at a restaurant for tonight"
            entities = self.extract_entities_from_query(sample_query)
            print(f"Extracted entities from '{sample_query}': {entities}")
            
            # Test category classification
            category_test = "I need a haircut at a salon"
            category_result = CategoryClassifier.classify_user_intent(category_test)
            print(f"Category classification for '{category_test}': {category_result}")
            
            return {
                "all_businesses_count": len(all_businesses),
                "restaurants_count": len(restaurants),
                "menu_items_count": len(menu_items),
                "extracted_entities": entities,
                "category_classification": category_result
            }
            
        except Exception as e:
            print(f"Error in test_search_functionality: {str(e)}")
            return {"error": str(e)}