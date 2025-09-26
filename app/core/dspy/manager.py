"""
DSPy Manager Module

Re-exports DSPy management functionality from config module.
This module provides the DSPyManager class and related utilities.
"""

from .config import (
    DSPyManager,
    get_dspy_manager,
    get_dspy_config,
    initialize_dspy,
    DSPyConfig
)

__all__ = [
    "DSPyManager",
    "get_dspy_manager", 
    "get_dspy_config",
    "initialize_dspy",
    "DSPyConfig"
]
