"""
Voice-Optimized DSPy Modules

Enhanced DSPy modules specifically optimized for voice interactions,
building on the existing DSPy infrastructure in X-Seven.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import asyncio

try:
    import dspy
    from dspy import Module, Signature, Predict, ChainOfThought
    from dspy.teleprompt import BootstrapFewShot, MIPROv2, COPRO
    DSPY_AVAILABLE = True
except ImportError:
    DSPY_AVAILABLE = False
    # Mock classes for development
    class Module: pass
    class Signature: pass
    class Predict: pass
    class ChainOfThought: pass

from app.core.dspy.manager import DSPyManager

logger = logging.getLogger(__name__)


class VoiceIntentSignature(dspy.Signature):
    """Signature for voice intent detection optimized for speech patterns."""
    voice_input = dspy.InputField(desc="User's voice input transcribed to text")
    context = dspy.InputField(desc="Voice conversation context and metadata")
    intent = dspy.OutputField(desc="Detected intent category with confidence")
    confidence = dspy.OutputField(desc="Confidence score between 0 and 1")
    speech_patterns = dspy.OutputField(desc="Identified speech patterns and characteristics")


class VoiceResponseSignature(dspy.Signature):
    """Signature for generating voice-optimized responses."""
    user_message = dspy.InputField(desc="User's message or request")
    context = dspy.InputField(desc="Conversation context and voice metadata")
    intent = dspy.InputField(desc="Detected user intent")
    voice_response = dspy.OutputField(desc="Natural, conversational response optimized for speech")
    tone = dspy.OutputField(desc="Recommended tone for voice synthesis")
    emphasis_points = dspy.OutputField(desc="Key words or phrases to emphasize")


class VoiceSummarySignature(dspy.Signature):
    """Signature for summarizing voice conversations."""
    conversation_history = dspy.InputField(desc="Complete voice conversation transcript")
    context = dspy.InputField(desc="Voice session context and metadata")
    key_points = dspy.OutputField(desc="Key points and decisions from the conversation")
    action_items = dspy.OutputField(desc="Action items or follow-ups identified")
    sentiment = dspy.OutputField(desc="Overall conversation sentiment and user satisfaction")


class VoiceCallIntentSignature(dspy.Signature):
    """Signature for predicting call intent before conversation starts."""
    call_context = dspy.InputField(desc="Call metadata including phone number, time, history")
    business_context = dspy.InputField(desc="Business information and available services")
    predicted_intent = dspy.OutputField(desc="Predicted reason for the call")
    preparation_notes = dspy.OutputField(desc="Suggested preparation for handling the call")
    priority_level = dspy.OutputField(desc="Call priority level (low, medium, high, urgent)")


class VoiceIntentDetectionModule(dspy.Module):
    """
    Voice-optimized intent detection module that handles speech-specific patterns,
    interruptions, and conversational nuances.
    """
    
    def __init__(self):
        super().__init__()
        self.intent_detector = dspy.ChainOfThought(VoiceIntentSignature)
        self.call_intent_predictor = dspy.Predict(VoiceCallIntentSignature)
        self.is_optimized = False
        
        # Voice-specific intent categories
        self.voice_intents = [
            "booking_request", "information_inquiry", "complaint_resolution",
            "service_request", "payment_inquiry", "appointment_scheduling",
            "product_inquiry", "technical_support", "general_conversation",
            "transfer_request", "callback_request", "emergency_assistance"
        ]
        
        logger.info("VoiceIntentDetectionModule initialized")
    
    def forward(self, voice_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Detect intent from voice input with context awareness."""
        try:
            # Enhance context with voice-specific metadata
            voice_context = self._enhance_voice_context(context)
            
            # Run intent detection
            result = self.intent_detector(
                voice_input=voice_input,
                context=str(voice_context)
            )
            
            return {
                "intent": result.intent,
                "confidence": float(result.confidence) if result.confidence.replace('.', '').isdigit() else 0.8,
                "speech_patterns": result.speech_patterns,
                "voice_enhanced": True,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in voice intent detection: {e}")
            return {
                "intent": "general_conversation",
                "confidence": 0.5,
                "speech_patterns": "unknown",
                "voice_enhanced": False,
                "error": str(e)
            }
    
    async def detect_intent(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Async wrapper for intent detection."""
        return self.forward(message, context)
    
    async def detect_call_intent(self, call_context: Dict[str, Any]) -> Dict[str, Any]:
        """Predict call intent before conversation starts."""
        try:
            # Extract business context
            business_context = {
                "services": ["restaurant booking", "customer support", "information"],
                "business_hours": "9 AM - 9 PM",
                "peak_times": ["12-2 PM", "6-8 PM"]
            }
            
            result = self.call_intent_predictor(
                call_context=str(call_context),
                business_context=str(business_context)
            )
            
            return {
                "predicted_intent": result.predicted_intent,
                "preparation_notes": result.preparation_notes,
                "priority_level": result.priority_level,
                "call_context": call_context,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error predicting call intent: {e}")
            return {
                "predicted_intent": "general_inquiry",
                "preparation_notes": "Standard greeting and assistance",
                "priority_level": "medium",
                "error": str(e)
            }
    
    def _enhance_voice_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance context with voice-specific information."""
        enhanced = context.copy()
        enhanced.update({
            "input_modality": "voice",
            "requires_natural_response": True,
            "speech_optimized": True,
            "available_intents": self.voice_intents
        })
        return enhanced
    
    async def optimize(self, training_data: List[Dict[str, Any]], budget: int = 10) -> Dict[str, Any]:
        """Optimize the voice intent detection module."""
        try:
            if not training_data:
                logger.warning("No training data provided for optimization")
                return {"success": False, "error": "No training data"}
            
            # Convert training data to DSPy format
            dspy_examples = []
            for example in training_data:
                if "input" in example and "output" in example:
                    dspy_examples.append(
                        dspy.Example(
                            voice_input=example["input"],
                            context=str(example.get("context", {})),
                            intent=example["output"].get("intent", "unknown"),
                            confidence=str(example["output"].get("confidence", 0.8)),
                            speech_patterns=example["output"].get("speech_patterns", "standard")
                        ).with_inputs("voice_input", "context")
                    )
            
            if not dspy_examples:
                return {"success": False, "error": "No valid examples for training"}
            
            # Use MIPROv2 for optimization
            optimizer = MIPROv2(metric=self._voice_intent_metric, num_candidates=budget)
            optimized_module = optimizer.compile(
                self.intent_detector,
                trainset=dspy_examples[:min(len(dspy_examples), budget)]
            )
            
            # Update the module
            self.intent_detector = optimized_module
            self.is_optimized = True
            
            logger.info("Voice intent detection module optimized successfully")
            return {
                "success": True,
                "examples_used": len(dspy_examples),
                "budget_used": budget,
                "optimization_method": "MIPROv2"
            }
            
        except Exception as e:
            logger.error(f"Error optimizing voice intent module: {e}")
            return {"success": False, "error": str(e)}
    
    def _voice_intent_metric(self, example, prediction, trace=None) -> float:
        """Custom metric for voice intent detection."""
        try:
            # Check if predicted intent matches expected
            intent_match = example.intent.lower() == prediction.intent.lower()
            
            # Check confidence score reasonableness
            try:
                conf_score = float(prediction.confidence)
                conf_reasonable = 0.0 <= conf_score <= 1.0
            except:
                conf_reasonable = False
            
            # Combine metrics
            score = 0.0
            if intent_match:
                score += 0.7
            if conf_reasonable:
                score += 0.3
            
            return score
            
        except Exception as e:
            logger.error(f"Error in voice intent metric: {e}")
            return 0.0


class VoiceResponseGenerationModule(dspy.Module):
    """
    Voice-optimized response generation module that creates natural,
    conversational responses suitable for speech synthesis.
    """
    
    def __init__(self):
        super().__init__()
        self.response_generator = dspy.ChainOfThought(VoiceResponseSignature)
        self.is_optimized = False
        
        logger.info("VoiceResponseGenerationModule initialized")
    
    def forward(self, user_message: str, context: Dict[str, Any], intent: str = "general") -> Dict[str, Any]:
        """Generate voice-optimized response."""
        try:
            # Enhance context for voice generation
            voice_context = self._prepare_voice_context(context)
            
            result = self.response_generator(
                user_message=user_message,
                context=str(voice_context),
                intent=intent
            )
            
            # Post-process response for voice
            optimized_response = self._optimize_for_speech(result.voice_response)
            
            return {
                "response": optimized_response,
                "tone": result.tone,
                "emphasis_points": result.emphasis_points,
                "voice_optimized": True,
                "original_response": result.voice_response,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating voice response: {e}")
            return {
                "response": "I understand your request. Let me help you with that.",
                "tone": "friendly",
                "emphasis_points": "help",
                "voice_optimized": False,
                "error": str(e)
            }
    
    async def generate_voice_response(self, message: str, context: Dict[str, Any]) -> str:
        """Async wrapper for voice response generation."""
        result = self.forward(message, context, context.get("detected_intent", "general"))
        return result.get("response", "I'm here to help you.")
    
    def _prepare_voice_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare context specifically for voice response generation."""
        voice_context = context.copy()
        voice_context.update({
            "output_modality": "voice",
            "natural_speech": True,
            "conversational_tone": True,
            "avoid_technical_jargon": True,
            "use_contractions": True,
            "keep_concise": True
        })
        return voice_context
    
    def _optimize_for_speech(self, response: str) -> str:
        """Optimize response text for natural speech synthesis."""
        if not response:
            return "I'm here to help you."
        
        # Remove or replace elements that don't work well in speech
        optimized = response
        
        # Replace abbreviations with full words
        speech_replacements = {
            "AI": "A I",
            "API": "A P I", 
            "URL": "U R L",
            "HTTP": "H T T P",
            "JSON": "J S O N",
            "&": "and",
            "@": "at",
            "%": "percent",
            "$": "dollars",
            "#": "number"
        }
        
        for abbrev, full in speech_replacements.items():
            optimized = optimized.replace(abbrev, full)
        
        # Ensure proper punctuation for speech pauses
        if not optimized.endswith(('.', '!', '?')):
            optimized += '.'
        
        # Break up very long sentences
        if len(optimized) > 150:
            sentences = optimized.split('. ')
            if len(sentences) > 2:
                optimized = '. '.join(sentences[:2]) + '.'
        
        return optimized
    
    async def optimize(self, training_data: List[Dict[str, Any]], budget: int = 10) -> Dict[str, Any]:
        """Optimize the voice response generation module."""
        try:
            if not training_data:
                return {"success": False, "error": "No training data"}
            
            # Convert to DSPy examples
            dspy_examples = []
            for example in training_data:
                if "input" in example and "output" in example:
                    dspy_examples.append(
                        dspy.Example(
                            user_message=example["input"],
                            context=str(example.get("context", {})),
                            intent=example.get("intent", "general"),
                            voice_response=example["output"].get("response", ""),
                            tone=example["output"].get("tone", "friendly"),
                            emphasis_points=example["output"].get("emphasis_points", "")
                        ).with_inputs("user_message", "context", "intent")
                    )
            
            if not dspy_examples:
                return {"success": False, "error": "No valid examples"}
            
            # Optimize using BootstrapFewShot
            optimizer = BootstrapFewShot(metric=self._voice_response_metric, max_bootstrapped_demos=budget)
            optimized_module = optimizer.compile(
                self.response_generator,
                trainset=dspy_examples[:min(len(dspy_examples), budget)]
            )
            
            self.response_generator = optimized_module
            self.is_optimized = True
            
            return {
                "success": True,
                "examples_used": len(dspy_examples),
                "budget_used": budget,
                "optimization_method": "BootstrapFewShot"
            }
            
        except Exception as e:
            logger.error(f"Error optimizing voice response module: {e}")
            return {"success": False, "error": str(e)}
    
    def _voice_response_metric(self, example, prediction, trace=None) -> float:
        """Custom metric for voice response quality."""
        try:
            response = prediction.voice_response
            
            # Check response quality factors
            score = 0.0
            
            # Length appropriateness (not too long for voice)
            if 10 <= len(response) <= 200:
                score += 0.3
            
            # Natural language patterns
            if any(word in response.lower() for word in ["i", "you", "we", "can", "will", "let's"]):
                score += 0.2
            
            # Proper punctuation
            if response.endswith(('.', '!', '?')):
                score += 0.2
            
            # Conversational tone
            if any(phrase in response.lower() for phrase in ["sure", "of course", "happy to", "glad to"]):
                score += 0.2
            
            # Avoid technical jargon
            technical_terms = ["API", "JSON", "HTTP", "database", "server"]
            if not any(term in response for term in technical_terms):
                score += 0.1
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.error(f"Error in voice response metric: {e}")
            return 0.0


class VoiceConversationSummaryModule(dspy.Module):
    """
    Voice conversation summarization module optimized for capturing
    key information from voice interactions.
    """
    
    def __init__(self):
        super().__init__()
        self.summarizer = dspy.ChainOfThought(VoiceSummarySignature)
        self.is_optimized = False
        
        logger.info("VoiceConversationSummaryModule initialized")
    
    def forward(self, conversation_history: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize voice conversation."""
        try:
            result = self.summarizer(
                conversation_history=conversation_history,
                context=str(context)
            )
            
            return {
                "key_points": result.key_points,
                "action_items": result.action_items,
                "sentiment": result.sentiment,
                "conversation_length": len(conversation_history),
                "summary_timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error summarizing voice conversation: {e}")
            return {
                "key_points": "Conversation completed",
                "action_items": "None identified",
                "sentiment": "neutral",
                "error": str(e)
            }
    
    async def summarize_voice_interaction(self, user_message: str, ai_response: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize a single voice interaction."""
        conversation = f"User: {user_message}\nAssistant: {ai_response}"
        return self.forward(conversation, context)
    
    async def optimize(self, training_data: List[Dict[str, Any]], budget: int = 10) -> Dict[str, Any]:
        """Optimize the voice conversation summary module."""
        try:
            if not training_data:
                return {"success": False, "error": "No training data"}
            
            # Convert to DSPy examples
            dspy_examples = []
            for example in training_data:
                if "conversation" in example and "summary" in example:
                    summary = example["summary"]
                    dspy_examples.append(
                        dspy.Example(
                            conversation_history=example["conversation"],
                            context=str(example.get("context", {})),
                            key_points=summary.get("key_points", ""),
                            action_items=summary.get("action_items", ""),
                            sentiment=summary.get("sentiment", "neutral")
                        ).with_inputs("conversation_history", "context")
                    )
            
            if not dspy_examples:
                return {"success": False, "error": "No valid examples"}
            
            # Use COPRO for optimization
            optimizer = COPRO(metric=self._summary_metric, breadth=budget)
            optimized_module = optimizer.compile(
                self.summarizer,
                trainset=dspy_examples[:min(len(dspy_examples), budget)]
            )
            
            self.summarizer = optimized_module
            self.is_optimized = True
            
            return {
                "success": True,
                "examples_used": len(dspy_examples),
                "budget_used": budget,
                "optimization_method": "COPRO"
            }
            
        except Exception as e:
            logger.error(f"Error optimizing voice summary module: {e}")
            return {"success": False, "error": str(e)}
    
    def _summary_metric(self, example, prediction, trace=None) -> float:
        """Custom metric for voice conversation summary quality."""
        try:
            score = 0.0
            
            # Check if key points are meaningful
            if prediction.key_points and len(prediction.key_points) > 10:
                score += 0.4
            
            # Check if action items are identified
            if prediction.action_items and prediction.action_items.lower() != "none":
                score += 0.3
            
            # Check if sentiment is reasonable
            valid_sentiments = ["positive", "negative", "neutral", "mixed"]
            if any(sentiment in prediction.sentiment.lower() for sentiment in valid_sentiments):
                score += 0.3
            
            return score
            
        except Exception as e:
            logger.error(f"Error in summary metric: {e}")
            return 0.0


# Factory function to create voice modules
def create_voice_modules() -> Dict[str, dspy.Module]:
    """Create all voice-optimized DSPy modules."""
    if not DSPY_AVAILABLE:
        logger.warning("DSPy not available, returning empty modules")
        return {}
    
    modules = {
        "voice_intent_detection": VoiceIntentDetectionModule(),
        "voice_response_generation": VoiceResponseGenerationModule(), 
        "voice_conversation_summary": VoiceConversationSummaryModule()
    }
    
    logger.info(f"Created {len(modules)} voice-optimized DSPy modules")
    return modules


# Integration with existing DSPy manager
async def register_voice_modules_with_dspy_manager():
    """Register voice modules with the existing DSPy manager."""
    try:
        from app.core.dspy.manager import get_dspy_manager
        dspy_manager = get_dspy_manager()
        
        if dspy_manager:
            voice_modules = create_voice_modules()
            for name, module in voice_modules.items():
                await dspy_manager.register_module(name, module)
            
            logger.info("Voice modules registered with DSPy manager")
            return True
        else:
            logger.warning("DSPy manager not available")
            return False
            
    except Exception as e:
        logger.error(f"Error registering voice modules: {e}")
        return False
