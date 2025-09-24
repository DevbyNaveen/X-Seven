"""
DSPy Metrics
Evaluation metrics for conversation quality and optimization
"""

import logging
import re
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass

import dspy
from sklearn.metrics import accuracy_score, f1_score
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

logger = logging.getLogger(__name__)


class ConversationMetrics:
    """Collection of metrics for conversation evaluation"""
    
    def __init__(self):
        # Load sentence transformer for semantic similarity
        try:
            self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception as e:
            logger.warning(f"Failed to load sentence transformer: {e}")
            self.sentence_model = None
    
    def intent_accuracy_metric(self, example: dspy.Example, pred: dspy.Prediction, trace=None) -> float:
        """Evaluate intent detection accuracy"""
        try:
            # Exact match for intent
            intent_match = example.intent.lower().strip() == pred.intent.lower().strip()
            
            # Confidence threshold (penalize low confidence correct answers)
            confidence_penalty = 0.0
            if hasattr(pred, 'confidence') and pred.confidence < 0.7:
                confidence_penalty = 0.1
            
            # Business category match (partial credit)
            category_match = 0.0
            if hasattr(example, 'business_category') and hasattr(pred, 'business_category'):
                category_match = 0.2 if example.business_category == pred.business_category else 0.0
            
            # Booking requirement match
            booking_match = 0.0
            if hasattr(example, 'requires_booking') and hasattr(pred, 'requires_booking'):
                booking_match = 0.1 if example.requires_booking == pred.requires_booking else 0.0
            
            base_score = 1.0 if intent_match else 0.0
            total_score = base_score + category_match + booking_match - confidence_penalty
            
            return max(0.0, min(1.0, total_score))
            
        except Exception as e:
            logger.error(f"Intent accuracy metric failed: {e}")
            return 0.0
    
    def routing_accuracy_metric(self, example: dspy.Example, pred: dspy.Prediction, trace=None) -> float:
        """Evaluate agent routing accuracy"""
        try:
            # Exact match for selected agent
            agent_match = example.selected_agent == pred.selected_agent
            
            # Confidence consideration
            confidence_bonus = 0.0
            if hasattr(pred, 'confidence') and pred.confidence > 0.8:
                confidence_bonus = 0.1
            
            # Reasoning quality (basic check)
            reasoning_quality = 0.0
            if hasattr(pred, 'routing_reason') and len(pred.routing_reason) > 20:
                reasoning_quality = 0.1
            
            base_score = 1.0 if agent_match else 0.0
            total_score = base_score + confidence_bonus + reasoning_quality
            
            return max(0.0, min(1.0, total_score))
            
        except Exception as e:
            logger.error(f"Routing accuracy metric failed: {e}")
            return 0.0
    
    def response_relevance_metric(self, example: dspy.Example, pred: dspy.Prediction, trace=None) -> float:
        """Evaluate response relevance using semantic similarity"""
        try:
            if not self.sentence_model:
                # Fallback to simple text matching
                return self._simple_text_similarity(example.response, pred.response)
            
            # Encode responses
            expected_embedding = self.sentence_model.encode([example.response])
            predicted_embedding = self.sentence_model.encode([pred.response])
            
            # Calculate cosine similarity
            similarity = cosine_similarity(expected_embedding, predicted_embedding)[0][0]
            
            # Normalize to 0-1 range (cosine similarity is -1 to 1)
            normalized_similarity = (similarity + 1) / 2
            
            # Length penalty for very short responses
            length_penalty = 0.0
            if len(pred.response.strip()) < 20:
                length_penalty = 0.2
            
            return max(0.0, min(1.0, normalized_similarity - length_penalty))
            
        except Exception as e:
            logger.error(f"Response relevance metric failed: {e}")
            return 0.0
    
    def _simple_text_similarity(self, text1: str, text2: str) -> float:
        """Simple text similarity fallback"""
        # Convert to lowercase and split into words
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        # Jaccard similarity
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def conversation_flow_metric(self, example: dspy.Example, pred: dspy.Prediction, trace=None) -> float:
        """Evaluate overall conversation flow quality"""
        try:
            score = 0.0
            
            # Response appropriateness
            if hasattr(pred, 'response') and len(pred.response.strip()) > 10:
                score += 0.3
            
            # Action items clarity
            if hasattr(pred, 'action_items') and pred.action_items.strip():
                score += 0.2
            
            # Confidence calibration
            if hasattr(pred, 'confidence'):
                # Reward well-calibrated confidence
                if 0.6 <= pred.confidence <= 0.9:
                    score += 0.2
            
            # Human escalation appropriateness
            if hasattr(pred, 'requires_human') and hasattr(example, 'requires_human'):
                if pred.requires_human == example.requires_human:
                    score += 0.3
            
            return min(1.0, score)
            
        except Exception as e:
            logger.error(f"Conversation flow metric failed: {e}")
            return 0.0


class ResponseQualityMetric:
    """Advanced response quality evaluation"""
    
    def __init__(self):
        try:
            self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception as e:
            logger.warning(f"Failed to load sentence transformer: {e}")
            self.sentence_model = None
    
    def evaluate(self, example: dspy.Example, pred: dspy.Prediction, trace=None) -> float:
        """Comprehensive response quality evaluation"""
        try:
            scores = []
            
            # Semantic similarity
            semantic_score = self._semantic_similarity(example.response, pred.response)
            scores.append(semantic_score * 0.4)  # 40% weight
            
            # Response completeness
            completeness_score = self._response_completeness(pred.response)
            scores.append(completeness_score * 0.2)  # 20% weight
            
            # Professional tone
            tone_score = self._professional_tone(pred.response)
            scores.append(tone_score * 0.2)  # 20% weight
            
            # Actionability
            action_score = self._actionability(pred.response, getattr(pred, 'action_items', ''))
            scores.append(action_score * 0.2)  # 20% weight
            
            return sum(scores)
            
        except Exception as e:
            logger.error(f"Response quality evaluation failed: {e}")
            return 0.0
    
    def _semantic_similarity(self, expected: str, predicted: str) -> float:
        """Calculate semantic similarity between responses"""
        if not self.sentence_model:
            return self._simple_similarity(expected, predicted)
        
        try:
            expected_emb = self.sentence_model.encode([expected])
            predicted_emb = self.sentence_model.encode([predicted])
            
            similarity = cosine_similarity(expected_emb, predicted_emb)[0][0]
            return (similarity + 1) / 2  # Normalize to 0-1
            
        except Exception:
            return self._simple_similarity(expected, predicted)
    
    def _simple_similarity(self, text1: str, text2: str) -> float:
        """Fallback similarity calculation"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def _response_completeness(self, response: str) -> float:
        """Evaluate response completeness"""
        response = response.strip()
        
        if len(response) < 10:
            return 0.0
        elif len(response) < 30:
            return 0.3
        elif len(response) < 100:
            return 0.7
        else:
            return 1.0
    
    def _professional_tone(self, response: str) -> float:
        """Evaluate professional tone"""
        score = 1.0
        
        # Penalize informal language
        informal_patterns = [
            r'\bya\b', r'\bgonna\b', r'\bwanna\b', r'\bkinda\b',
            r'\bsorta\b', r'\bumm\b', r'\buh\b', r'\blike\b.*\blike\b'
        ]
        
        for pattern in informal_patterns:
            if re.search(pattern, response, re.IGNORECASE):
                score -= 0.1
        
        # Reward professional phrases
        professional_patterns = [
            r'\bI\'d be happy to\b', r'\bI can help\b', r'\bplease\b',
            r'\bthank you\b', r'\blet me\b', r'\bI understand\b'
        ]
        
        for pattern in professional_patterns:
            if re.search(pattern, response, re.IGNORECASE):
                score += 0.05
        
        return max(0.0, min(1.0, score))
    
    def _actionability(self, response: str, action_items: str) -> float:
        """Evaluate response actionability"""
        score = 0.0
        
        # Check for action words in response
        action_words = [
            'book', 'schedule', 'call', 'visit', 'contact', 'order',
            'reserve', 'confirm', 'check', 'verify', 'provide'
        ]
        
        response_lower = response.lower()
        for word in action_words:
            if word in response_lower:
                score += 0.1
        
        # Bonus for explicit action items
        if action_items and len(action_items.strip()) > 5:
            score += 0.3
        
        return min(1.0, score)


class BusinessSpecificMetrics:
    """Business category specific metrics"""
    
    @staticmethod
    def restaurant_booking_metric(example: dspy.Example, pred: dspy.Prediction, trace=None) -> float:
        """Metric for restaurant booking conversations"""
        score = 0.0
        
        # Check for booking-related information
        booking_keywords = ['table', 'reservation', 'book', 'party', 'time', 'date']
        response_lower = pred.response.lower()
        
        for keyword in booking_keywords:
            if keyword in response_lower:
                score += 0.15
        
        # Check for appropriate questions
        question_patterns = [
            r'how many', r'what time', r'which date', r'any preferences',
            r'dietary restrictions', r'special occasion'
        ]
        
        for pattern in question_patterns:
            if re.search(pattern, response_lower):
                score += 0.1
        
        return min(1.0, score)
    
    @staticmethod
    def beauty_service_metric(example: dspy.Example, pred: dspy.Prediction, trace=None) -> float:
        """Metric for beauty service conversations"""
        score = 0.0
        
        # Beauty-specific keywords
        beauty_keywords = ['appointment', 'stylist', 'service', 'treatment', 'hair', 'skin']
        response_lower = pred.response.lower()
        
        for keyword in beauty_keywords:
            if keyword in response_lower:
                score += 0.15
        
        # Check for consultation questions
        consultation_patterns = [
            r'hair type', r'skin type', r'previous treatments', r'allergies',
            r'desired look', r'maintenance'
        ]
        
        for pattern in consultation_patterns:
            if re.search(pattern, response_lower):
                score += 0.1
        
        return min(1.0, score)
