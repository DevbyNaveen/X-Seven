"""
DSPy Optimizers
Handles prompt optimization and model tuning
"""

import logging
import json
import asyncio
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import dspy
from dspy.evaluate import Evaluate
from dspy.teleprompt import BootstrapFewShot, MIPROv2, COPRO

from .metrics import ConversationMetrics, ResponseQualityMetric
from .training_data import TrainingDataManager

logger = logging.getLogger(__name__)


@dataclass
class OptimizationConfig:
    """Configuration for DSPy optimization"""
    optimizer_type: str = "mipro"  # mipro, bootstrap, copro
    max_bootstrapped_demos: int = 4
    max_labeled_demos: int = 8
    num_candidate_programs: int = 10
    num_threads: int = 4
    max_errors: int = 5
    optimization_budget: float = 10.0  # USD
    validation_split: float = 0.2
    min_training_examples: int = 20
    max_training_examples: int = 200
    save_optimized_programs: bool = True
    optimization_cache_dir: str = ".dspy_optimization_cache"


class DSPyOptimizer:
    """Handles DSPy program optimization and tuning"""
    
    def __init__(self, config: OptimizationConfig):
        self.config = config
        self.training_manager = TrainingDataManager()
        self.metrics = ConversationMetrics()
        self.optimization_history: List[Dict[str, Any]] = []
        
        # Create cache directory
        Path(self.config.optimization_cache_dir).mkdir(exist_ok=True)
    
    async def optimize_intent_detection(self, module: dspy.Module, 
                                      training_examples: List[Dict[str, Any]] = None) -> dspy.Module:
        """Optimize intent detection module"""
        logger.info("🔧 Starting intent detection optimization...")
        
        try:
            # Get or generate training data
            if not training_examples:
                training_examples = await self.training_manager.get_intent_training_data()
            
            if len(training_examples) < self.config.min_training_examples:
                logger.warning(f"Insufficient training data: {len(training_examples)} examples")
                return module
            
            # Convert to DSPy format
            trainset = self._convert_to_dspy_examples(training_examples, "intent_detection")
            
            # Split train/validation
            split_idx = int(len(trainset) * (1 - self.config.validation_split))
            train_data = trainset[:split_idx]
            val_data = trainset[split_idx:]
            
            # Define metric
            metric = self.metrics.intent_accuracy_metric
            
            # Choose optimizer
            optimizer = self._get_optimizer(metric)
            
            # Optimize
            optimized_module = optimizer.compile(
                module, 
                trainset=train_data,
                valset=val_data
            )
            
            # Evaluate performance
            evaluator = Evaluate(
                devset=val_data,
                metric=metric,
                num_threads=self.config.num_threads,
                display_progress=True
            )
            
            original_score = evaluator(module)
            optimized_score = evaluator(optimized_module)
            
            # Log results
            improvement = optimized_score - original_score
            logger.info(f"✅ Intent detection optimization complete:")
            logger.info(f"   Original score: {original_score:.3f}")
            logger.info(f"   Optimized score: {optimized_score:.3f}")
            logger.info(f"   Improvement: {improvement:.3f}")
            
            # Save optimization history
            self._save_optimization_result(
                "intent_detection", original_score, optimized_score, 
                len(train_data), improvement
            )
            
            # Save optimized module if configured
            if self.config.save_optimized_programs:
                self._save_optimized_module(optimized_module, "intent_detection")
            
            return optimized_module
            
        except Exception as e:
            logger.error(f"❌ Intent detection optimization failed: {e}")
            return module
    
    async def optimize_agent_routing(self, module: dspy.Module,
                                   training_examples: List[Dict[str, Any]] = None) -> dspy.Module:
        """Optimize agent routing module"""
        logger.info("🔧 Starting agent routing optimization...")
        
        try:
            # Get training data
            if not training_examples:
                training_examples = await self.training_manager.get_routing_training_data()
            
            if len(training_examples) < self.config.min_training_examples:
                logger.warning(f"Insufficient routing training data: {len(training_examples)} examples")
                return module
            
            # Convert and optimize
            trainset = self._convert_to_dspy_examples(training_examples, "agent_routing")
            split_idx = int(len(trainset) * (1 - self.config.validation_split))
            train_data = trainset[:split_idx]
            val_data = trainset[split_idx:]
            
            metric = self.metrics.routing_accuracy_metric
            optimizer = self._get_optimizer(metric)
            
            optimized_module = optimizer.compile(
                module,
                trainset=train_data,
                valset=val_data
            )
            
            # Evaluate
            evaluator = Evaluate(devset=val_data, metric=metric, num_threads=self.config.num_threads)
            original_score = evaluator(module)
            optimized_score = evaluator(optimized_module)
            
            improvement = optimized_score - original_score
            logger.info(f"✅ Agent routing optimization complete:")
            logger.info(f"   Original score: {original_score:.3f}")
            logger.info(f"   Optimized score: {optimized_score:.3f}")
            logger.info(f"   Improvement: {improvement:.3f}")
            
            self._save_optimization_result(
                "agent_routing", original_score, optimized_score,
                len(train_data), improvement
            )
            
            if self.config.save_optimized_programs:
                self._save_optimized_module(optimized_module, "agent_routing")
            
            return optimized_module
            
        except Exception as e:
            logger.error(f"❌ Agent routing optimization failed: {e}")
            return module
    
    async def optimize_response_generation(self, module: dspy.Module,
                                         training_examples: List[Dict[str, Any]] = None) -> dspy.Module:
        """Optimize response generation module"""
        logger.info("🔧 Starting response generation optimization...")
        
        try:
            # Get training data
            if not training_examples:
                training_examples = await self.training_manager.get_response_training_data()
            
            if len(training_examples) < self.config.min_training_examples:
                logger.warning(f"Insufficient response training data: {len(training_examples)} examples")
                return module
            
            # Convert and optimize
            trainset = self._convert_to_dspy_examples(training_examples, "response_generation")
            split_idx = int(len(trainset) * (1 - self.config.validation_split))
            train_data = trainset[:split_idx]
            val_data = trainset[split_idx:]
            
            # Use semantic similarity metric for response quality
            metric = ResponseQualityMetric()
            optimizer = self._get_optimizer(metric.evaluate)
            
            optimized_module = optimizer.compile(
                module,
                trainset=train_data,
                valset=val_data
            )
            
            # Evaluate
            evaluator = Evaluate(devset=val_data, metric=metric.evaluate, num_threads=self.config.num_threads)
            original_score = evaluator(module)
            optimized_score = evaluator(optimized_module)
            
            improvement = optimized_score - original_score
            logger.info(f"✅ Response generation optimization complete:")
            logger.info(f"   Original score: {original_score:.3f}")
            logger.info(f"   Optimized score: {optimized_score:.3f}")
            logger.info(f"   Improvement: {improvement:.3f}")
            
            self._save_optimization_result(
                "response_generation", original_score, optimized_score,
                len(train_data), improvement
            )
            
            if self.config.save_optimized_programs:
                self._save_optimized_module(optimized_module, "response_generation")
            
            return optimized_module
            
        except Exception as e:
            logger.error(f"❌ Response generation optimization failed: {e}")
            return module
    
    async def optimize_full_pipeline(self, modules: Dict[str, dspy.Module]) -> Dict[str, dspy.Module]:
        """Optimize entire conversation pipeline"""
        logger.info("🚀 Starting full pipeline optimization...")
        
        optimized_modules = {}
        
        # Optimize each module sequentially
        for module_name, module in modules.items():
            logger.info(f"Optimizing {module_name}...")
            
            if module_name == "intent_detection":
                optimized_modules[module_name] = await self.optimize_intent_detection(module)
            elif module_name == "agent_routing":
                optimized_modules[module_name] = await self.optimize_agent_routing(module)
            elif module_name == "response_generation":
                optimized_modules[module_name] = await self.optimize_response_generation(module)
            else:
                optimized_modules[module_name] = module
        
        logger.info("✅ Full pipeline optimization complete!")
        return optimized_modules
    
    def _get_optimizer(self, metric: Callable):
        """Get configured optimizer instance"""
        if self.config.optimizer_type == "mipro":
            return MIPROv2(
                metric=metric,
                auto="light",  # Use light mode for cost efficiency
                num_threads=self.config.num_threads
            )
        elif self.config.optimizer_type == "bootstrap":
            return BootstrapFewShot(
                metric=metric,
                max_bootstrapped_demos=self.config.max_bootstrapped_demos,
                max_labeled_demos=self.config.max_labeled_demos,
                max_rounds=3
            )
        elif self.config.optimizer_type == "copro":
            return COPRO(
                metric=metric,
                breadth=self.config.num_candidate_programs,
                depth=3
            )
        else:
            raise ValueError(f"Unknown optimizer type: {self.config.optimizer_type}")
    
    def _convert_to_dspy_examples(self, training_examples: List[Dict[str, Any]], 
                                task_type: str) -> List[dspy.Example]:
        """Convert training data to DSPy examples"""
        dspy_examples = []
        
        for example in training_examples:
            try:
                if task_type == "intent_detection":
                    dspy_example = dspy.Example(
                        message=example["message"],
                        conversation_history=example.get("conversation_history", ""),
                        business_context=example.get("business_context", ""),
                        intent=example["intent"],
                        confidence=example.get("confidence", 1.0),
                        reasoning=example.get("reasoning", ""),
                        requires_booking=example.get("requires_booking", False),
                        business_category=example.get("business_category", "local_services")
                    ).with_inputs("message", "conversation_history", "business_context")
                
                elif task_type == "agent_routing":
                    dspy_example = dspy.Example(
                        intent=example["intent"],
                        business_context=example.get("business_context", ""),
                        conversation_type=example.get("conversation_type", "general"),
                        user_message=example["user_message"],
                        available_agents=example.get("available_agents", ""),
                        selected_agent=example["selected_agent"],
                        routing_reason=example.get("routing_reason", ""),
                        confidence=example.get("confidence", 1.0),
                        fallback_agent=example.get("fallback_agent", "GeneralPurposeAgent")
                    ).with_inputs("intent", "business_context", "conversation_type", "user_message", "available_agents")
                
                elif task_type == "response_generation":
                    dspy_example = dspy.Example(
                        user_message=example["user_message"],
                        conversation_history=example.get("conversation_history", ""),
                        business_context=example.get("business_context", ""),
                        agent_context=example.get("agent_context", ""),
                        intent=example.get("intent", "general"),
                        response=example["response"],
                        action_items=example.get("action_items", ""),
                        confidence=example.get("confidence", 1.0),
                        requires_human=example.get("requires_human", False)
                    ).with_inputs("user_message", "conversation_history", "business_context", "agent_context", "intent")
                
                dspy_examples.append(dspy_example)
                
            except Exception as e:
                logger.warning(f"Failed to convert training example: {e}")
                continue
        
        return dspy_examples
    
    def _save_optimization_result(self, module_name: str, original_score: float,
                                optimized_score: float, training_size: int, improvement: float):
        """Save optimization results to history"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "module_name": module_name,
            "original_score": original_score,
            "optimized_score": optimized_score,
            "improvement": improvement,
            "training_size": training_size,
            "optimizer_type": self.config.optimizer_type,
            "config": {
                "max_bootstrapped_demos": self.config.max_bootstrapped_demos,
                "max_labeled_demos": self.config.max_labeled_demos,
                "num_threads": self.config.num_threads
            }
        }
        
        self.optimization_history.append(result)
        
        # Save to file
        history_file = Path(self.config.optimization_cache_dir) / "optimization_history.json"
        with open(history_file, "w") as f:
            json.dump(self.optimization_history, f, indent=2)
    
    def _save_optimized_module(self, module: dspy.Module, module_name: str):
        """Save optimized module to disk"""
        try:
            module_file = Path(self.config.optimization_cache_dir) / f"{module_name}_optimized.json"
            
            # Extract and save the optimized prompts/demonstrations
            module_data = {
                "module_name": module_name,
                "timestamp": datetime.now().isoformat(),
                "optimizer_type": self.config.optimizer_type,
                "module_state": str(module)  # Basic serialization
            }
            
            with open(module_file, "w") as f:
                json.dump(module_data, f, indent=2)
                
            logger.info(f"💾 Saved optimized {module_name} module")
            
        except Exception as e:
            logger.error(f"Failed to save optimized module {module_name}: {e}")
    
    def get_optimization_history(self) -> List[Dict[str, Any]]:
        """Get optimization history"""
        return self.optimization_history.copy()
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get optimization statistics"""
        if not self.optimization_history:
            return {"total_optimizations": 0}
        
        improvements = [result["improvement"] for result in self.optimization_history]
        
        return {
            "total_optimizations": len(self.optimization_history),
            "average_improvement": sum(improvements) / len(improvements),
            "best_improvement": max(improvements),
            "modules_optimized": list(set(result["module_name"] for result in self.optimization_history)),
            "last_optimization": self.optimization_history[-1]["timestamp"]
        }
