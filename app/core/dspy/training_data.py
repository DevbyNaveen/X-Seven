"""
DSPy Training Data Management
Handles collection, generation, and management of training data for optimization
"""

import logging
import json
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import random

from app.config.settings import settings

logger = logging.getLogger(__name__)


class TrainingDataManager:
    """Manages training data for DSPy optimization"""
    
    def __init__(self, data_dir: str = ".dspy_training_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Initialize with synthetic data if no real data exists
        self.synthetic_data_generated = False
    
    async def get_intent_training_data(self, min_examples: int = 50) -> List[Dict[str, Any]]:
        """Get training data for intent detection"""
        # Try to load existing data
        existing_data = self._load_training_data("intent_detection")
        
        if len(existing_data) >= min_examples:
            logger.info(f"Loaded {len(existing_data)} intent detection examples")
            return existing_data
        
        # Generate synthetic data if needed
        logger.info("Generating synthetic intent detection data...")
        synthetic_data = self._generate_synthetic_intent_data(min_examples)
        
        # Combine with existing data
        combined_data = existing_data + synthetic_data
        
        # Save combined data
        self._save_training_data("intent_detection", combined_data)
        
        logger.info(f"Created {len(combined_data)} intent detection examples")
        return combined_data
    
    async def get_routing_training_data(self, min_examples: int = 50) -> List[Dict[str, Any]]:
        """Get training data for agent routing"""
        existing_data = self._load_training_data("agent_routing")
        
        if len(existing_data) >= min_examples:
            logger.info(f"Loaded {len(existing_data)} routing examples")
            return existing_data
        
        logger.info("Generating synthetic routing data...")
        synthetic_data = self._generate_synthetic_routing_data(min_examples)
        
        combined_data = existing_data + synthetic_data
        self._save_training_data("agent_routing", combined_data)
        
        logger.info(f"Created {len(combined_data)} routing examples")
        return combined_data
    
    async def get_response_training_data(self, min_examples: int = 50) -> List[Dict[str, Any]]:
        """Get training data for response generation"""
        existing_data = self._load_training_data("response_generation")
        
        if len(existing_data) >= min_examples:
            logger.info(f"Loaded {len(existing_data)} response examples")
            return existing_data
        
        logger.info("Generating synthetic response data...")
        synthetic_data = self._generate_synthetic_response_data(min_examples)
        
        combined_data = existing_data + synthetic_data
        self._save_training_data("response_generation", combined_data)
        
        logger.info(f"Created {len(combined_data)} response examples")
        return combined_data
    
    def _load_training_data(self, data_type: str) -> List[Dict[str, Any]]:
        """Load existing training data from file"""
        file_path = self.data_dir / f"{data_type}.json"
        
        if not file_path.exists():
            return []
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Failed to load training data from {file_path}: {e}")
            return []
    
    def _save_training_data(self, data_type: str, data: List[Dict[str, Any]]):
        """Save training data to file"""
        file_path = self.data_dir / f"{data_type}.json"
        
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(data)} examples to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save training data to {file_path}: {e}")
    
    def _generate_synthetic_intent_data(self, num_examples: int) -> List[Dict[str, Any]]:
        """Generate synthetic intent detection training data"""
        synthetic_data = []
        
        # Define intent patterns and examples
        intent_patterns = {
            "booking": [
                ("I'd like to make a reservation for tonight", "booking", True, "food_hospitality"),
                ("Can I book a table for 4 people?", "booking", True, "food_hospitality"),
                ("I need to schedule an appointment", "booking", True, "beauty_personal_care"),
                ("Book me a haircut for tomorrow", "booking", True, "beauty_personal_care"),
                ("I want to reserve a service slot", "booking", True, "local_services"),
            ],
            "order": [
                ("I'd like to order food for delivery", "order", False, "food_hospitality"),
                ("Can I place an order for pickup?", "order", False, "food_hospitality"),
                ("I want to buy some products", "order", False, "local_services"),
                ("Order me the usual", "order", False, "food_hospitality"),
            ],
            "discovery": [
                ("What restaurants are nearby?", "discovery", False, "food_hospitality"),
                ("Find me a good salon", "discovery", False, "beauty_personal_care"),
                ("I'm looking for auto repair shops", "discovery", False, "automotive_services"),
                ("Recommend a doctor", "discovery", False, "health_medical"),
                ("What services do you offer?", "discovery", False, "local_services"),
            ],
            "support": [
                ("I have a problem with my order", "support", False, "food_hospitality"),
                ("My appointment was cancelled", "support", False, "beauty_personal_care"),
                ("I need help with something", "support", False, "local_services"),
                ("There's an issue with my service", "support", False, "local_services"),
            ],
            "general": [
                ("Hello, how are you?", "general", False, "local_services"),
                ("What are your hours?", "general", False, "local_services"),
                ("Do you accept credit cards?", "general", False, "local_services"),
                ("Tell me about your business", "general", False, "local_services"),
            ]
        }
        
        # Generate examples
        examples_per_intent = num_examples // len(intent_patterns)
        
        for intent, patterns in intent_patterns.items():
            for i in range(examples_per_intent):
                # Select a random pattern and add variations
                base_message, base_intent, requires_booking, category = random.choice(patterns)
                
                # Add some variation to the message
                variations = [
                    base_message,
                    base_message.replace("I'd like to", "I want to"),
                    base_message.replace("Can I", "Could I"),
                    base_message + " please",
                    "Hi, " + base_message.lower(),
                ]
                
                message = random.choice(variations)
                
                synthetic_data.append({
                    "message": message,
                    "conversation_history": "",
                    "business_context": f"Business category: {category}",
                    "intent": base_intent,
                    "confidence": round(random.uniform(0.8, 1.0), 2),
                    "reasoning": f"Message contains keywords indicating {base_intent} intent",
                    "requires_booking": requires_booking,
                    "business_category": category
                })
        
        return synthetic_data
    
    def _generate_synthetic_routing_data(self, num_examples: int) -> List[Dict[str, Any]]:
        """Generate synthetic agent routing training data"""
        synthetic_data = []
        
        # Define routing patterns
        routing_patterns = {
            "booking": ("RestaurantAgent", "food_hospitality"),
            "order": ("RestaurantAgent", "food_hospitality"),
            "discovery": ("GeneralPurposeAgent", "local_services"),
            "support": ("GeneralPurposeAgent", "local_services"),
            "general": ("GeneralPurposeAgent", "local_services")
        }
        
        available_agents = [
            "RestaurantAgent", "BeautyAgent", "AutomotiveAgent",
            "HealthAgent", "LocalServicesAgent", "GeneralPurposeAgent"
        ]
        
        intents = list(routing_patterns.keys())
        examples_per_intent = num_examples // len(intents)
        
        for intent in intents:
            for i in range(examples_per_intent):
                selected_agent, category = routing_patterns[intent]
                
                # Vary conversation types
                conversation_types = ["dedicated", "dashboard", "global"]
                conversation_type = random.choice(conversation_types)
                
                # Adjust agent selection based on conversation type
                if conversation_type == "dashboard":
                    selected_agent = "BusinessAnalyticsAgent"
                elif conversation_type == "dedicated" and category != "local_services":
                    # Use category-specific agent for dedicated conversations
                    category_agents = {
                        "food_hospitality": "RestaurantAgent",
                        "beauty_personal_care": "BeautyAgent",
                        "automotive_services": "AutomotiveAgent",
                        "health_medical": "HealthAgent"
                    }
                    selected_agent = category_agents.get(category, "GeneralPurposeAgent")
                
                synthetic_data.append({
                    "intent": intent,
                    "business_context": f"Business category: {category}",
                    "conversation_type": conversation_type,
                    "user_message": f"Sample {intent} message",
                    "available_agents": ", ".join(available_agents),
                    "selected_agent": selected_agent,
                    "routing_reason": f"Selected {selected_agent} based on {intent} intent and {conversation_type} context",
                    "confidence": round(random.uniform(0.7, 0.95), 2),
                    "fallback_agent": "GeneralPurposeAgent"
                })
        
        return synthetic_data
    
    def _generate_synthetic_response_data(self, num_examples: int) -> List[Dict[str, Any]]:
        """Generate synthetic response generation training data"""
        synthetic_data = []
        
        # Define response templates
        response_templates = {
            "booking": {
                "user_message": "I'd like to make a reservation",
                "response": "I'd be happy to help you make a reservation! To get started, could you please let me know how many people will be dining and what date and time you prefer?",
                "action_items": "Collect party size, date, and time preferences",
                "requires_human": False
            },
            "order": {
                "user_message": "I want to order food",
                "response": "Great! I can help you place an order. Would you like to see our menu, or do you already know what you'd like to order?",
                "action_items": "Show menu or take order details",
                "requires_human": False
            },
            "discovery": {
                "user_message": "What services do you offer?",
                "response": "We offer a variety of services to meet your needs. Let me provide you with information about our main services and help you find exactly what you're looking for.",
                "action_items": "Provide service information",
                "requires_human": False
            },
            "support": {
                "user_message": "I have a problem with my order",
                "response": "I'm sorry to hear you're having an issue with your order. I'd like to help resolve this for you right away. Could you please provide more details about the problem?",
                "action_items": "Gather problem details and provide resolution",
                "requires_human": False
            },
            "general": {
                "user_message": "What are your hours?",
                "response": "Our business hours vary by location and service. Let me provide you with the specific hours for the service you're interested in.",
                "action_items": "Provide business hours information",
                "requires_human": False
            }
        }
        
        # Generate examples
        examples_per_template = num_examples // len(response_templates)
        
        for intent, template in response_templates.items():
            for i in range(examples_per_template):
                # Add variations
                business_contexts = [
                    "Restaurant specializing in Italian cuisine",
                    "Full-service beauty salon",
                    "Auto repair and maintenance shop",
                    "Medical clinic with multiple specialties",
                    "Local services provider"
                ]
                
                agent_contexts = [
                    "Experienced customer service specialist",
                    "Knowledgeable business representative",
                    "Professional service coordinator"
                ]
                
                synthetic_data.append({
                    "user_message": template["user_message"],
                    "conversation_history": "",
                    "business_context": random.choice(business_contexts),
                    "agent_context": random.choice(agent_contexts),
                    "intent": intent,
                    "response": template["response"],
                    "action_items": template["action_items"],
                    "confidence": round(random.uniform(0.8, 0.95), 2),
                    "requires_human": template["requires_human"]
                })
        
        return synthetic_data
    
    async def collect_real_conversation_data(self, limit: int = 100) -> Dict[str, List[Dict[str, Any]]]:
        """Collect real conversation data from database for training"""
        # This would integrate with your actual database
        # For now, return empty dict - implement based on your database schema
        
        logger.info("Real conversation data collection not yet implemented")
        return {
            "intent_detection": [],
            "agent_routing": [],
            "response_generation": []
        }
    
    def add_training_example(self, data_type: str, example: Dict[str, Any]):
        """Add a new training example"""
        existing_data = self._load_training_data(data_type)
        existing_data.append({
            **example,
            "timestamp": datetime.now().isoformat(),
            "source": "manual_addition"
        })
        self._save_training_data(data_type, existing_data)
        logger.info(f"Added new {data_type} training example")
    
    def get_training_stats(self) -> Dict[str, Any]:
        """Get statistics about available training data"""
        stats = {}
        
        for data_type in ["intent_detection", "agent_routing", "response_generation"]:
            data = self._load_training_data(data_type)
            stats[data_type] = {
                "total_examples": len(data),
                "last_updated": max([ex.get("timestamp", "") for ex in data], default="never")
            }
        
        return stats
