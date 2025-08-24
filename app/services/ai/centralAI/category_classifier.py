"""
Category Classifier for Intelligent Business Discovery
"""
from typing import Dict, Any, List

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