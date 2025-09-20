# app/services/ai/rag_search.py
"""
RAG Search Module for Central AI
Implements database search capabilities using Retrieval-Augmented Generation
"""
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import hashlib
import json

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
    Enhanced with embedding-based semantic search for better results.
    """
    
    def __init__(self, db: Client):
        self.db = db
        # Initialize embedding model for semantic search
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        # Cache for embeddings to improve performance
        self.embedding_cache = {}
        self.max_cache_size = 1000
    
    def _get_embedding(self, text: str) -> np.ndarray:
        """
        Generate or retrieve cached embedding for given text.
        
        Args:
            text: Text to embed
            
        Returns:
            Numpy array of embedding vector
        """
        # Create cache key
        cache_key = hashlib.md5(text.encode()).hexdigest()
        
        # Check cache first
        if cache_key in self.embedding_cache:
            return self.embedding_cache[cache_key]
        
        # Generate new embedding
        embedding = self.embedding_model.encode(text, convert_to_numpy=True)
        
        # Cache the embedding (with size limit)
        if len(self.embedding_cache) < self.max_cache_size:
            self.embedding_cache[cache_key] = embedding
        
        return embedding
    
    def _calculate_similarity(self, query_embedding: np.ndarray, text_embedding: np.ndarray) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Args:
            query_embedding: Embedding of the query
            text_embedding: Embedding of the text to compare
            
        Returns:
            Cosine similarity score (0-1)
        """
        similarity = cosine_similarity([query_embedding], [text_embedding])[0][0]
        return float(similarity)
    
    def _semantic_search(self, query: str, items: List[Dict], text_fields: List[str], top_k: int = 10) -> List[Dict]:
        """
        Perform semantic search on items using embeddings.
        
        Args:
            query: Search query
            items: List of items to search through
            text_fields: List of fields to use for embedding generation
            top_k: Number of top results to return
            
        Returns:
            List of items sorted by semantic similarity
        """
        if not query or not items:
            return items[:top_k] if items else []
        
        # Generate query embedding
        query_embedding = self._get_embedding(query)
        
        # Calculate similarities for each item
        scored_items = []
        for item in items:
            # Combine text from specified fields
            combined_text = " ".join([
                str(item.get(field, "")) for field in text_fields
                if item.get(field)
            ])
            
            if combined_text.strip():
                # Generate embedding for item
                item_embedding = self._get_embedding(combined_text)
                # Calculate similarity
                similarity = self._calculate_similarity(query_embedding, item_embedding)
                
                scored_items.append({
                    **item,
                    "_semantic_score": similarity
                })
        
        # Sort by semantic similarity and return top-k
        scored_items.sort(key=lambda x: x["_semantic_score"], reverse=True)
        return scored_items[:top_k]
    
    def _analyze_query_with_llm(self, query: str, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Modern LLM-powered intent analysis like ChatGPT.
        Extracts entities, preferences, context, and confidence scores.
        """
        try:
            # Use the existing intent agent for LLM analysis
            # Note: Global AI integration removed - using fallback analysis
            # from app.services.ai.global_ai.intent_agent import IntentAgent
            
            # Create a temporary intent agent for analysis
            # Note: In production, this should be passed from the main handler
            # intent_agent = IntentAgent(None)  # We'll use fallback analysis
            pass  # Intent agent removed during integration
            
            # Fallback analysis using the existing logic
            user_message_lower = query.lower()
            
            # Extract entities and preferences
            analysis = {
                "primary_intent": "search_business",
                "confidence": 0.9,
                "entities": {
                    "business_types": [],
                    "cuisine_types": [],
                    "price_range": None,
                    "location": None,
                    "time_preference": None,
                    "group_size": None,
                    "ambiance": [],
                    "dietary_restrictions": []
                },
                "user_preferences": {
                    "budget_level": "medium",
                    "preferred_ambiance": "casual",
                    "time_of_day": "evening",
                    "distance_preference": "walking"
                },
                "context_signals": {
                    "urgency": "normal",
                    "specificity": "general",
                    "social_context": "solo"
                }
            }
            
            # Advanced entity extraction
            if "pizza" in user_message_lower or "italian" in user_message_lower:
                analysis["entities"]["cuisine_types"].append("italian")
                analysis["entities"]["business_types"].append("restaurant")
            
            if "coffee" in user_message_lower or "cafe" in user_message_lower:
                analysis["entities"]["business_types"].append("cafe")
                analysis["entities"]["cuisine_types"].append("coffee")
            
            if "expensive" in user_message_lower or "cheap" in user_message_lower:
                analysis["user_preferences"]["budget_level"] = "low" if "cheap" in user_message_lower else "high"
            
            if "nearby" in user_message_lower or "close" in user_message_lower:
                analysis["user_preferences"]["distance_preference"] = "walking"
            
            # Time-based preferences
            if any(word in user_message_lower for word in ["dinner", "evening", "tonight"]):
                analysis["user_preferences"]["time_of_day"] = "evening"
            elif any(word in user_message_lower for word in ["lunch", "noon", "afternoon"]):
                analysis["user_preferences"]["time_of_day"] = "afternoon"
            elif any(word in user_message_lower for word in ["breakfast", "morning"]):
                analysis["user_preferences"]["time_of_day"] = "morning"
            
            return analysis
            
        except Exception as e:
            print(f"Error in LLM intent analysis: {e}")
            # Return basic analysis
            return {
                "primary_intent": "search_business",
                "confidence": 0.5,
                "entities": {"business_types": ["general"]},
                "user_preferences": {},
                "context_signals": {"specificity": "general"}
            }
    
    def _enhance_query_with_context(self, query: str, intent_analysis: Dict[str, Any]) -> str:
        """
        Enhance user query with multi-modal context like ChatGPT.
        Adds location, time, preferences, and environmental context.
        """
        try:
            enhanced_parts = [query]  # Start with original query
            
            if intent_analysis:
                entities = intent_analysis.get('entities', {})
                preferences = intent_analysis.get('user_preferences', {})
                context_signals = intent_analysis.get('context_signals', {})
                
                # Add cuisine context
                cuisine_types = entities.get('cuisine_types', [])
                if cuisine_types:
                    enhanced_parts.append(f"cuisine: {' '.join(cuisine_types)}")
                
                # Add time context
                time_of_day = preferences.get('time_of_day')
                if time_of_day:
                    enhanced_parts.append(f"time: {time_of_day}")
                
                # Add ambiance preferences
                ambiance = preferences.get('preferred_ambiance')
                if ambiance:
                    enhanced_parts.append(f"ambiance: {ambiance}")
                
                # Add budget context
                budget = preferences.get('budget_level')
                if budget:
                    enhanced_parts.append(f"budget: {budget}")
                
                # Add distance preferences
                distance = preferences.get('distance_preference')
                if distance:
                    enhanced_parts.append(f"distance: {distance}")
                
                # Add social context
                social_context = context_signals.get('social_context')
                if social_context:
                    enhanced_parts.append(f"context: {social_context}")
            
            # Combine all context
            enhanced_query = " | ".join(enhanced_parts)
            
            return enhanced_query
            
        except Exception as e:
            print(f"Error enhancing query with context: {e}")
            return query  # Return original query if enhancement fails
    
    def _original_search_businesses(self, query: str, filters: Optional[Dict[str, Any]] = None, top_k: int = 10, use_semantic: bool = True) -> List[Dict[str, Any]]:
        """
        Original search method as fallback - the one we fixed earlier.
        """
        try:
            # Build efficient database query
            db_query = self.db.table('businesses').select('*').eq('is_active', True)
            
            # Apply text search if query provided
            if query:
                query_lower = query.lower()
                
                # Build all search conditions into a single OR query
                all_conditions = []
                
                # Add category filter conditions if provided
                if filters and 'category' in filters and filters['category']:
                    category_filter = filters['category'].lower()
                    if 'food' in category_filter or 'restaurant' in category_filter:
                        all_conditions.extend([
                            "category.ilike.%food%",
                            "category.ilike.%hospitality%"
                        ])
                    elif 'service' in category_filter or 'repair' in category_filter:
                        all_conditions.extend([
                            "category.ilike.%service%",
                            "category.ilike.%repair%",
                            "category.ilike.%automotive%"
                        ])
                    elif 'health' in category_filter or 'medical' in category_filter:
                        all_conditions.extend([
                            "category.ilike.%health%",
                            "category.ilike.%medical%"
                        ])
                    elif 'beauty' in category_filter or 'personal' in category_filter:
                        all_conditions.extend([
                            "category.ilike.%beauty%",
                            "category.ilike.%personal%",
                            "category.ilike.%care%"
                        ])
                    elif 'local' in category_filter or 'services' in category_filter:
                        all_conditions.extend([
                            "category.ilike.%local%",
                            "category.ilike.%services%"
                        ])
                    else:
                        all_conditions.append(f"category.ilike.%{filters['category']}%")
                
                # Add text search conditions
                all_conditions.extend([
                    f"name.ilike.%{query_lower}%",
                    f"description.ilike.%{query_lower}%", 
                    f"category.ilike.%{query_lower}%"
                ])
                
                # Apply single OR condition with all filters
                db_query = db_query.or_(','.join(all_conditions))
            else:
                # No query, just apply category filter if provided
                if filters and 'category' in filters and filters['category']:
                    category_filter = filters['category'].lower()
                    if 'food' in category_filter or 'restaurant' in category_filter:
                        db_query = db_query.ilike('category', '%food%').or_('category.ilike.%hospitality%')
                    elif 'service' in category_filter or 'repair' in category_filter:
                        db_query = db_query.ilike('category', '%service%').or_('category.ilike.%repair%').or_('category.ilike.%automotive%')
                    elif 'health' in category_filter or 'medical' in category_filter:
                        db_query = db_query.ilike('category', '%health%').or_('category.ilike.%medical%')
                    elif 'beauty' in category_filter or 'personal' in category_filter:
                        db_query = db_query.ilike('category', '%beauty%').or_('category.ilike.%personal%').or_('category.ilike.%care%')
                    elif 'local' in category_filter or 'services' in category_filter:
                        db_query = db_query.ilike('category', '%local%').or_('category.ilike.%services%')
                    else:
                        db_query = db_query.ilike('category', f"%{filters['category']}%")
            
            # Apply additional filters
            if filters:
                if 'business_ids' in filters and filters['business_ids']:
                    db_query = db_query.in_('id', filters['business_ids'])
                
                if 'location' in filters and filters['location']:
                    db_query = db_query.ilike('location', f"%{filters['location']}%")
                    
                if 'min_rating' in filters and filters['min_rating']:
                    db_query = db_query.gte('rating', filters['min_rating'])
            
            # Get filtered results
            response = db_query.limit(top_k * 2).execute()
            businesses = response.data if response.data else []
            
            # Format results
            formatted_businesses = []
            for business in businesses[:top_k]:
                formatted_business = {
                    "id": business['id'],
                    "name": business['name'],
                    "category": business['category'],
                    "description": business.get('description', ''),
                    "location": business.get('location', 'local area'),
                    "rating": business.get('rating', 0),
                    "phone": business.get('phone', ''),
                    "sample_menu": []
                }
                formatted_businesses.append(formatted_business)
            
            # Apply semantic search if enabled and we have results
            if use_semantic and query and len(formatted_businesses) > 1:
                text_fields = ['name', 'description', 'category']
                semantic_results = self._semantic_search(query, formatted_businesses, text_fields, top_k)
                
                # Remove semantic scores from final results
                for result in semantic_results:
                    if "_semantic_score" in result:
                        del result["_semantic_score"]
                
                return semantic_results
            else:
                return formatted_businesses[:top_k]
                
        except Exception as e:
            print(f"Error in original search: {str(e)}")
            return []
    
    def _semantic_search_enhanced(self, query: str, intent_analysis: Dict[str, Any], top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Enhanced semantic search using vector embeddings and intent analysis.
        Like ChatGPT's retrieval system - understands meaning, not just keywords.
        """
        try:
            # Get all businesses for semantic search
            response = self.db.table('businesses').select('*').eq('is_active', True).execute()
            all_businesses = response.data if response.data else []
            
            if not all_businesses:
                return []
            
            # Create enhanced query with context
            enhanced_query = self._enhance_query_with_context(query, intent_analysis)
            
            # Generate query embedding
            query_embedding = self._get_embedding(enhanced_query)
            
            # Calculate semantic similarity for each business
            scored_businesses = []
            
            for business in all_businesses:
                # Create rich business representation
                business_text = self._create_business_representation(business, intent_analysis)
                
                # Handle None values safely
                if business_text is None:
                    business_text = f"Business: {business.get('name', 'Unknown')}"
                    
                business_embedding = self._get_embedding(business_text)
                
                # Calculate semantic similarity
                semantic_score = self._calculate_similarity(query_embedding, business_embedding)
                
                # Calculate contextual relevance score
                context_score = self._calculate_context_relevance(business, intent_analysis)
                
                # Combined relevance score
                combined_score = (semantic_score * 0.7) + (context_score * 0.3)
                
                if combined_score > 0.3:  # Minimum relevance threshold
                    scored_businesses.append({
                        "business": business,
                        "semantic_score": semantic_score,
                        "context_score": context_score,
                        "combined_score": combined_score,
                        "match_reasons": self._get_match_reasons(business, intent_analysis)
                    })
            
            # Sort by combined relevance score
            scored_businesses.sort(key=lambda x: x["combined_score"], reverse=True)
            
            # Format and return top results
            results = []
            for item in scored_businesses[:top_k]:
                business = item["business"]
                formatted_business = {
                    "id": business['id'],
                    "name": business['name'],
                    "category": business['category'],
                    "description": business.get('description', ''),
                    "location": business.get('location', 'local area'),
                    "rating": business.get('rating', 0),
                    "phone": business.get('phone', ''),
                    "relevance_score": item["combined_score"],
                    "match_reasons": item["match_reasons"],
                    "sample_menu": []
                }
                results.append(formatted_business)
            
            return results
            
        except Exception as e:
            print(f"Error in enhanced semantic search: {e}")
            return []
    
    def _create_business_representation(self, business: Dict[str, Any], intent_analysis: Dict[str, Any]) -> str:
        """
        Create rich text representation of business for embedding.
        Includes semantic context like ChatGPT would understand.
        """
        name = business.get('name', '')
        category = business.get('category', '')
        description = business.get('description', '')
        location = business.get('location', '')
        
        # Create multi-faceted representation
        representation_parts = []
        
        # Basic information - handle None values
        if name:
            representation_parts.append(f"Business name: {name}")
        if category:
            representation_parts.append(f"Category: {category}")
        if description:
            representation_parts.append(f"Description: {description}")
        if location:
            representation_parts.append(f"Location: {location}")
        
        # If no parts were added, use a default representation
        if not representation_parts:
            return f"Business: {business.get('name', 'Unknown')}"
        
        # Semantic context based on intent analysis
        if intent_analysis:
            entities = intent_analysis.get('entities', {})
            preferences = intent_analysis.get('user_preferences', {})
            
            # Add cuisine context
            cuisine_types = entities.get('cuisine_types', [])
            if cuisine_types:
                representation_parts.append(f"Cuisine: {' '.join(cuisine_types)}")
            
            # Add ambiance context
            ambiance = preferences.get('preferred_ambiance')
            if ambiance:
                representation_parts.append(f"Ambiance: {ambiance}")
            
            # Add time context
            time_of_day = preferences.get('time_of_day')
            if time_of_day:
                representation_parts.append(f"Best time: {time_of_day}")
        
        # Combine all parts - ensure we always return a string
        if representation_parts:
            return " | ".join(representation_parts)
        else:
            return f"Business: {business.get('name', 'Unknown')}"
    
    def _calculate_context_relevance(self, business: Dict[str, Any], intent_analysis: Dict[str, Any]) -> float:
        """
        Calculate contextual relevance score based on user preferences and entities.
        Like ChatGPT's understanding of user context.
        """
        score = 0.0
        
        if not intent_analysis:
            return score
        
        entities = intent_analysis.get('entities', {})
        preferences = intent_analysis.get('user_preferences', {})
        
        business_name = business.get('name', '').lower() if business.get('name') else ''
        business_desc = business.get('description', '').lower() if business.get('description') else ''
        business_cat = business.get('category', '').lower() if business.get('category') else ''
        
        # Cuisine matching
        for cuisine in entities.get('cuisine_types', []):
            if cuisine.lower() in business_desc or cuisine.lower() in business_name:
                score += 0.4
        
        # Business type matching
        for biz_type in entities.get('business_types', []):
            if biz_type.lower() in business_cat:
                score += 0.3
        
        # Time preference matching
        time_pref = preferences.get('time_of_day', '')
        if time_pref and time_pref.lower() in business_desc:
            score += 0.2
        
        # Budget consideration (if we had price data)
        budget_level = preferences.get('budget_level', '')
        # Could add price range matching here if available
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _get_match_reasons(self, business: Dict[str, Any], intent_analysis: Dict[str, Any]) -> List[str]:
        """
        Generate human-readable reasons why this business matches the query.
        Like ChatGPT explaining its recommendations.
        """
        reasons = []
        
        if not intent_analysis:
            return reasons
        
        entities = intent_analysis.get('entities', {})
        preferences = intent_analysis.get('user_preferences', {})
        
        business_name = business.get('name', '').lower() if business.get('name') else ''
        business_desc = business.get('description', '').lower() if business.get('description') else ''
        
        # Cuisine reasons
        for cuisine in entities.get('cuisine_types', []):
            if cuisine.lower() in business_desc:
                reasons.append(f"Offers {cuisine} cuisine")
        
        # Business type reasons
        for biz_type in entities.get('business_types', []):
            if biz_type.lower() in business.get('category', '').lower():
                reasons.append(f"{biz_type.title()} business")
        
        # Time reasons
        time_pref = preferences.get('time_of_day', '')
        if time_pref and time_pref.lower() in business_desc:
            reasons.append(f"Suitable for {time_pref} visits")
        
        # Location reasons
        if business.get('location'):
            reasons.append(f"Located in {business['location']}")
        
        return reasons[:3]  # Limit to top 3 reasons
    
    def _database_search_with_filters(self, query: str, filters: Optional[Dict[str, Any]] = None, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Traditional database search as fallback for semantic search.
        Uses the improved query structure we fixed earlier.
        """
        try:
            # Build efficient database query
            db_query = self.db.table('businesses').select('*').eq('is_active', True)
            
            # Apply text search if query provided
            if query:
                query_lower = query.lower()
                
                # Build all search conditions into a single OR query
                all_conditions = []
                
                # Add category filter conditions if provided
                if filters and 'category' in filters and filters['category']:
                    category_filter = filters['category'].lower()
                    if 'food' in category_filter or 'restaurant' in category_filter:
                        all_conditions.extend([
                            "category.ilike.%food%",
                            "category.ilike.%hospitality%"
                        ])
                    elif 'service' in category_filter or 'repair' in category_filter:
                        all_conditions.extend([
                            "category.ilike.%service%",
                            "category.ilike.%repair%",
                            "category.ilike.%automotive%"
                        ])
                    elif 'health' in category_filter or 'medical' in category_filter:
                        all_conditions.extend([
                            "category.ilike.%health%",
                            "category.ilike.%medical%"
                        ])
                    elif 'beauty' in category_filter or 'personal' in category_filter:
                        all_conditions.extend([
                            "category.ilike.%beauty%",
                            "category.ilike.%personal%",
                            "category.ilike.%care%"
                        ])
                    elif 'local' in category_filter or 'services' in category_filter:
                        all_conditions.extend([
                            "category.ilike.%local%",
                            "category.ilike.%services%"
                        ])
                    else:
                        all_conditions.append(f"category.ilike.%{filters['category']}%")
                
                # Add text search conditions
                all_conditions.extend([
                    f"name.ilike.%{query_lower}%",
                    f"description.ilike.%{query_lower}%", 
                    f"category.ilike.%{query_lower}%"
                ])
                
                # Apply single OR condition with all filters
                db_query = db_query.or_(','.join(all_conditions))
            else:
                # No query, just apply category filter if provided
                if filters and 'category' in filters and filters['category']:
                    category_filter = filters['category'].lower()
                    if 'food' in category_filter or 'restaurant' in category_filter:
                        db_query = db_query.ilike('category', '%food%').or_('category.ilike.%hospitality%')
                    elif 'service' in category_filter or 'repair' in category_filter:
                        db_query = db_query.ilike('category', '%service%').or_('category.ilike.%repair%').or_('category.ilike.%automotive%')
                    elif 'health' in category_filter or 'medical' in category_filter:
                        db_query = db_query.ilike('category', '%health%').or_('category.ilike.%medical%')
                    elif 'beauty' in category_filter or 'personal' in category_filter:
                        db_query = db_query.ilike('category', '%beauty%').or_('category.ilike.%personal%').or_('category.ilike.%care%')
                    elif 'local' in category_filter or 'services' in category_filter:
                        db_query = db_query.ilike('category', '%local%').or_('category.ilike.%services%')
                    else:
                        db_query = db_query.ilike('category', f"%{filters['category']}%")
            
            # Apply additional filters
            if filters:
                if 'business_ids' in filters and filters['business_ids']:
                    db_query = db_query.in_('id', filters['business_ids'])
                
                if 'location' in filters and filters['location']:
                    db_query = db_query.ilike('location', f"%{filters['location']}%")
                    
                if 'min_rating' in filters and filters['min_rating']:
                    db_query = db_query.gte('rating', filters['min_rating'])
            
            # Get filtered results
            response = db_query.limit(top_k * 2).execute()
            businesses = response.data if response.data else []
            
            # Format results
            formatted_businesses = []
            for business in businesses[:top_k]:
                formatted_business = {
                    "id": business['id'],
                    "name": business['name'],
                    "category": business['category'],
                    "description": business.get('description', ''),
                    "location": business.get('location', 'local area'),
                    "rating": business.get('rating', 0),
                    "phone": business.get('phone', ''),
                    "sample_menu": []
                }
                formatted_businesses.append(formatted_business)
            
            return formatted_businesses
            
        except Exception as e:
            print(f"Error in database search: {e}")
            return []
    
    def _combine_search_results(self, semantic_results: List[Dict[str, Any]], db_results: List[Dict[str, Any]], intent_analysis: Dict[str, Any], top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Combine semantic and database search results with intelligent ranking.
        Like ChatGPT's result synthesis - best of both worlds.
        """
        try:
            # Create a map to avoid duplicates
            combined_map = {}
            
            # Add semantic results with higher priority
            for result in semantic_results:
                business_id = result['id']
                combined_map[business_id] = {
                    'business': result,
                    'source': 'semantic',
                    'score': result.get('relevance_score', 0.5),
                    'priority': 1  # Higher priority for semantic matches
                }
            
            # Add database results (avoid duplicates)
            for result in db_results:
                business_id = result['id']
                if business_id not in combined_map:
                    combined_map[business_id] = {
                        'business': result,
                        'source': 'database',
                        'score': 0.3,  # Lower score for database-only matches
                        'priority': 2
                    }
            
            # Convert to list and sort by priority, then score
            combined_list = list(combined_map.values())
            combined_list.sort(key=lambda x: (x['priority'], x['score']), reverse=True)
            
            # Return top results
            return [item['business'] for item in combined_list[:top_k]]
            
        except Exception as e:
            print(f"Error combining search results: {e}")
            # Fallback: return semantic results or database results
            if semantic_results:
                return semantic_results[:top_k]
            elif db_results:
                return db_results[:top_k]
            else:
                return []
    
    def _format_business_results(self, results: List[Dict[str, Any]], intent_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Format business results with enhanced information like ChatGPT.
        Includes relevance scores, match reasons, and contextual information.
        """
        try:
            formatted_results = []
            
            for result in results:
                # Enhance result with additional context
                enhanced_result = result.copy()
                
                # Add contextual information based on intent analysis
                if intent_analysis:
                    preferences = intent_analysis.get('user_preferences', {})
                    
                    # Add time suitability
                    time_pref = preferences.get('time_of_day')
                    if time_pref:
                        enhanced_result['time_suitability'] = self._check_time_suitability(result, time_pref)
                    
                    # Add distance estimate (if location available)
                    distance_pref = preferences.get('distance_preference')
                    if distance_pref:
                        enhanced_result['distance_estimate'] = self._estimate_distance(result, distance_pref)
                
                formatted_results.append(enhanced_result)
            
            return formatted_results
            
        except Exception as e:
            print(f"Error formatting business results: {e}")
            return results
    
    def _check_time_suitability(self, business: Dict[str, Any], time_preference: str) -> str:
        """
        Check if business is suitable for user's preferred time.
        Like ChatGPT understanding temporal context.
        """
        # Simple heuristic based on business category and time
        category = business.get('category', '').lower()
        
        if time_preference == 'morning':
            if 'cafe' in category or 'coffee' in category:
                return 'Perfect for morning coffee'
            elif 'restaurant' in category:
                return 'Good for breakfast/brunch'
        
        elif time_preference == 'afternoon':
            if 'restaurant' in category:
                return 'Good for lunch'
        
        elif time_preference == 'evening':
            if 'restaurant' in category or 'bar' in category:
                return 'Perfect for dinner/drinks'
        
        return 'Available during business hours'
    
    def _estimate_distance(self, business: Dict[str, Any], distance_preference: str) -> str:
        """
        Estimate distance based on location information.
        Like ChatGPT providing spatial context.
        """
        if distance_preference == 'walking':
            return 'Within walking distance'
        elif distance_preference == 'driving':
            return 'Short drive away'
        else:
            return business.get('location', 'Local area')
    
    def _original_search_businesses(self, query: str, filters: Optional[Dict[str, Any]] = None, top_k: int = 10, use_semantic: bool = True) -> List[Dict[str, Any]]:
        # TO DO: Implement original search method
        pass
    
    def search_businesses(self, query: str, filters: Optional[Dict[str, Any]] = None, top_k: int = 10, use_semantic: bool = True) -> List[Dict[str, Any]]:
        """
        Modern semantic search with vector embeddings and LLM understanding.
        Uses ChatGPT/Claude-style approach with embeddings + RAG + context.
        """
        try:
            # Step 1: LLM-Powered Intent Analysis (like ChatGPT)
            intent_analysis = self._analyze_query_with_llm(query, filters)
            
            # Step 2: Multi-Modal Context Enhancement
            enhanced_query = self._enhance_query_with_context(query, intent_analysis)
            
            # Step 3: Semantic Search with Embeddings
            semantic_results = []
            if use_semantic:
                semantic_results = self._semantic_search_enhanced(
                    enhanced_query, 
                    intent_analysis, 
                    top_k=top_k * 2
                )
            
            # Step 4: Traditional Database Filtering (fallback/combination)
            db_results = []
            if not semantic_results or len(semantic_results) < top_k:
                db_results = self._database_search_with_filters(query, filters, top_k)
            
            # Step 5: Combine and Rank Results (RAG-style)
            combined_results = self._combine_search_results(
                semantic_results, 
                db_results, 
                intent_analysis,
                top_k
            )
            
            # Step 6: Format and Return
            if combined_results:
                return self._format_business_results(combined_results, intent_analysis)
            else:
                return []
                
        except Exception as e:
            print(f"Error in modern search_businesses: {str(e)}")
            # Fallback to original method
            return self._original_search_businesses(query, filters, top_k, use_semantic)

    def search_menu_items(self, query: str, business_id: Optional[int] = None, top_k: int = 10, use_semantic: bool = True) -> List[Dict[str, Any]]:
        try:
            # Start building the query
            db_query = self.db.table('menu_items').select('*').eq('is_available', True)
            
            # Limit to specific business if provided
            if business_id:
                db_query = db_query.eq('business_id', business_id)
            
            # Get menu items from database
            response = db_query.execute()
            menu_items = response.data if response.data else []
            
            if not menu_items:
                return []
            
            # Format menu items with business info
            formatted_items = []
            for item in menu_items:
                # Get business info for context
                business_response = self.db.table('businesses').select('*').eq('id', item['business_id']).execute()
                business = business_response.data[0] if business_response.data else None
                
                formatted_item = {
                    "id": item['id'],
                    "name": item['name'],
                    "description": item['description'],
                    "price": float(item['base_price'] or 0),
                    "business": {
                        "id": business['id'] if business else None,
                        "name": business['name'] if business else "Unknown"
                    } if business else None
                }
                formatted_items.append(formatted_item)
            
            # Apply semantic search if enabled and query provided
            if use_semantic and query:
                text_fields = ['name', 'description']
                semantic_results = self._semantic_search(query, formatted_items, text_fields, top_k)
                
                # Remove semantic scores from final results
                for result in semantic_results:
                    if "_semantic_score" in result:
                        del result["_semantic_score"]
                
                return semantic_results
            else:
                # Fallback to keyword search or return all items
                if query:
                    # Simple keyword filtering as fallback
                    query_lower = query.lower()
                    filtered_results = [
                        item for item in formatted_items
                        if (query_lower in item['name'].lower() or 
                            (item['description'] and query_lower in item['description'].lower()))
                    ]
                    return filtered_results[:top_k]
                else:
                    return formatted_items[:top_k]
            
        except Exception as e:
            print(f"Error in search_menu_items: {str(e)}")
            return []
    
    def hybrid_search_businesses(self, query: str, filters: Optional[Dict[str, Any]] = None, top_k: int = 10, semantic_weight: float = 0.7, keyword_weight: float = 0.3) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining semantic and keyword search for optimal results.
        
        Args:
            query: Search query string
            filters: Optional dictionary of filters
            top_k: Number of top results to return
            semantic_weight: Weight for semantic similarity (0-1)
            keyword_weight: Weight for keyword matching (0-1)
            
        Returns:
            List of businesses sorted by combined score
        """
        try:
            # Get businesses using filters only (no initial query filtering)
            db_query = self.db.table('businesses').select('*')
            
            if filters:
                if 'category' in filters and filters['category']:
                    db_query = db_query.ilike('category', f"%{filters['category']}%")
                if 'business_ids' in filters and filters['business_ids']:
                    db_query = db_query.in_('id', filters['business_ids'])
                if 'min_rating' in filters and filters['min_rating']:
                    db_query = db_query.gte('rating', filters['min_rating'])
            
            response = db_query.execute()
            businesses = response.data if response.data else []
            
            if not businesses:
                return []
            
            # Format businesses
            formatted_businesses = []
            for business in businesses:
                menu_response = self.db.table('menu_items').select('*').eq('business_id', business['id']).eq('is_available', True).execute()
                menu_items = menu_response.data if menu_response.data else []
                
                formatted_business = {
                    "id": business['id'],
                    "name": business['name'],
                    "category": business['category'],
                    "description": business['description'],
                    "sample_menu": [
                        {
                            "id": item['id'],
                            "name": item['name'],
                            "description": item['description'],
                            "price": float(item['base_price'] or 0)
                        } for item in menu_items
                    ]
                }
                formatted_businesses.append(formatted_business)
            
            # Calculate semantic scores
            query_embedding = self._get_embedding(query)
            semantic_scores = {}
            
            for business in formatted_businesses:
                combined_text = f"{business['name']} {business['description']} {business['category']}"
                business_embedding = self._get_embedding(combined_text)
                semantic_scores[business['id']] = self._calculate_similarity(query_embedding, business_embedding)
            
            # Calculate keyword scores
            query_lower = query.lower()
            keyword_scores = {}
            
            for business in formatted_businesses:
                score = 0
                name_lower = business['name'].lower()
                desc_lower = business['description'].lower()
                cat_lower = business['category'].lower()
                
                # Exact matches get higher scores
                if query_lower in name_lower:
                    score += 3
                if query_lower in desc_lower:
                    score += 2
                if query_lower in cat_lower:
                    score += 2
                
                # Partial matches
                for word in query_lower.split():
                    if word in name_lower:
                        score += 1
                    if word in desc_lower:
                        score += 0.5
                    if word in cat_lower:
                        score += 0.5
                
                keyword_scores[business['id']] = score
            
            # Normalize keyword scores (0-1 range)
            if keyword_scores:
                max_keyword = max(keyword_scores.values())
                if max_keyword > 0:
                    keyword_scores = {k: v/max_keyword for k, v in keyword_scores.items()}
            
            # Combine scores
            combined_results = []
            for business in formatted_businesses:
                business_id = business['id']
                semantic_score = semantic_scores.get(business_id, 0)
                keyword_score = keyword_scores.get(business_id, 0)
                
                combined_score = (semantic_weight * semantic_score) + (keyword_weight * keyword_score)
                
                business_copy = business.copy()
                business_copy["_combined_score"] = combined_score
                business_copy["_semantic_score"] = semantic_score
                business_copy["_keyword_score"] = keyword_score
                combined_results.append(business_copy)
            
            # Sort by combined score and return top-k
            combined_results.sort(key=lambda x: x["_combined_score"], reverse=True)
            
            # Remove internal scores from final results
            for result in combined_results[:top_k]:
                for key in ["_combined_score", "_semantic_score", "_keyword_score"]:
                    if key in result:
                        del result[key]
            
            return combined_results[:top_k]
            
        except Exception as e:
            print(f"Error in hybrid_search_businesses: {str(e)}")
            return []

    def get_business_context(self, business_id: int) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive context information for a specific business.
        
        Args:
            business_id: businesses ID
            
        Returns:
            Dictionary with business context or None if not found
        """
        try:
            business_response = self.db.table('businesses').select('*').eq('id', business_id).execute()
            
            if not business_response.data:
                return None
            
            business = business_response.data[0]
            
            # Get menu items
            menu_response = self.db.table('menu_items').select('*').eq('business_id', business_id).eq('is_available', True).execute()
            menu_items = menu_response.data if menu_response.data else []
            
            # Get recent orders (last 5)
            orders_response = self.db.table('orders').select('*').eq('business_id', business_id).order('created_at', desc=True).limit(5).execute()
            recent_orders = orders_response.data if orders_response.data else []
            
            return {
                "business": {
                    "id": business['id'],
                    "name": business['name'],
                    "category": business['category'],
                    "description": business['description'],
                    "is_active": business['is_active']
                },
                "menu": [
                    {
                        "id": item['id'],
                        "name": item['name'],
                        "description": item['description'],
                        "price": float(item['base_price'] or 0),
                        "category": item.get('category_id')
                    } for item in menu_items
                ],
                "recent_orders": [
                    {
                        "id": order['id'],
                        "customer_name": order['customer_name'],
                        "total_amount": float(order['total_amount'] or 0),
                        "status": str(order['status']),
                        "created_at": order['created_at'] if 'created_at' in order else None
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
            db_query = self.db.table('messages').select('*').eq('session_id', session_id)
            
            # Apply text search if query provided
            if query:
                search_terms = query.split()
                or_conditions = []
                
                for term in search_terms:
                    term_filter = f"%{term}%"
                    or_conditions.append(f"content.ilike.{term_filter}")
                
                if or_conditions:
                    db_query = db_query.or_(','.join(or_conditions))
            
            # orders by created time and limit results
            response = db_query.order('created_at', desc=True).limit(limit).execute()
            messages = response.data if response.data else []
            
            return [
                {
                    "id": msg['id'],
                    "content": msg['content'],
                    "sender_type": msg['sender_type'],
                    "created_at": msg['created_at'] if 'created_at' in msg else None
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
        
        # businesses types
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
        This method demonstrates how the enhanced RAGSearch class works with embeddings.
        """
        try:
            # Test business search with an empty query (should return all businesses)
            all_businesses = self.search_businesses("", top_k=5)
            print(f"Found {len(all_businesses)} businesses in total")
            
            # Test semantic business search with different queries
            semantic_queries = [
                "I want Italian food",
                "place for a haircut",
                "coffee shop",
                "car repair service"
            ]
            
            for query in semantic_queries:
                results = self.search_businesses(query, top_k=3, use_semantic=True)
                print(f"Semantic search for '{query}': Found {len(results)} results")
                if results:
                    print(f"  Top result: {results[0]['name']} ({results[0]['category']})")
            
            # Test hybrid search
            hybrid_results = self.hybrid_search_businesses("pizza restaurant", top_k=3)
            print(f"Hybrid search for 'pizza restaurant': Found {len(hybrid_results)} results")
            if hybrid_results:
                print(f"  Top hybrid result: {hybrid_results[0]['name']}")
            
            # Test menu item search with embeddings
            menu_results = self.search_menu_items("coffee", top_k=5)
            print(f"Menu search for 'coffee': Found {len(menu_results)} results")
            
            # Test entity extraction
            sample_query = "I want to book a table at a restaurant for tonight"
            entities = self.extract_entities_from_query(sample_query)
            print(f"Extracted entities from '{sample_query}': {entities}")
            
            # Test category classification
            category_test = "I need a haircut at a salon"
            category_result = CategoryClassifier.classify_user_intent(category_test)
            print(f"Category classification for '{category_test}': {category_result}")
            
            # Test embedding similarity
            test_texts = ["Italian restaurant", "pizza place", "hair salon", "coffee shop"]
            query_emb = self._get_embedding("food place")
            similarities = []
            for text in test_texts:
                text_emb = self._get_embedding(text)
                sim = self._calculate_similarity(query_emb, text_emb)
                similarities.append((text, sim))
            
            print("Embedding similarities for 'food place':")
            for text, sim in sorted(similarities, key=lambda x: x[1], reverse=True):
                print(f"  {text}: {sim:.3f}")
            
            return {
                "all_businesses_count": len(all_businesses),
                "semantic_search_results": len(results) if 'results' in locals() else 0,
                "hybrid_search_results": len(hybrid_results),
                "menu_items_count": len(menu_results),
                "extracted_entities": entities,
                "category_classification": category_result,
                "embedding_similarities": similarities
            }
            
        except Exception as e:
            print(f"Error in test_search_functionality: {str(e)}")
            return {"error": str(e)}