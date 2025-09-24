"""
DSPy Integration Module
Core DSPy infrastructure for X-SevenAI
"""

from .config import DSPyConfig, get_dspy_config
from .base_modules import (
    IntentDetectionModule,
    AgentRoutingModule,
    ResponseGenerationModule,
    ConversationSummaryModule
)
from .optimizers import DSPyOptimizer, OptimizationConfig
from .metrics import ConversationMetrics, ResponseQualityMetric
from .training_data import TrainingDataManager

__all__ = [
    "DSPyConfig",
    "get_dspy_config",
    "IntentDetectionModule",
    "AgentRoutingModule", 
    "ResponseGenerationModule",
    "ConversationSummaryModule",
    "DSPyOptimizer",
    "OptimizationConfig",
    "ConversationMetrics",
    "ResponseQualityMetric",
    "TrainingDataManager"
]
