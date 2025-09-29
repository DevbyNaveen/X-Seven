"""
DSPy Configuration Management
Handles DSPy setup and LLM configuration
"""

import os
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from functools import lru_cache

import dspy
from app.config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class DSPyConfig:
    """DSPy configuration settings"""
    primary_model: str = "openai/gpt-4o-mini"
    fallback_model: str = "groq/llama-3.3-70b-versatile"
    optimization_model: str = "openai/gpt-4o-mini"  # For optimization tasks
    max_tokens: int = 2000
    temperature: float = 0.7
    enable_caching: bool = True
    cache_dir: str = ".dspy_cache"
    optimization_budget: float = 10.0  # USD budget for optimization
    max_optimization_examples: int = 100


class DSPyManager:
    """Manages DSPy configuration and LLM setup"""
    
    def __init__(self, config: DSPyConfig):
        self.config = config
        self.primary_lm = None
        self.fallback_lm = None
        self.optimization_lm = None
        self._initialized = False
        # Registry for custom DSPy modules (e.g., voice‑optimized modules)
        self._module_registry: dict[str, Any] = {}

    
    def initialize(self) -> bool:
        """Initialize DSPy with configured LLMs"""
        if self._initialized:
            return True
            
        try:
            # Initialize primary LLM
            self.primary_lm = self._create_llm(self.config.primary_model)
            
            # Initialize fallback LLM
            if self.config.fallback_model != self.config.primary_model:
                self.fallback_lm = self._create_llm(self.config.fallback_model)
            else:
                self.fallback_lm = self.primary_lm
            
            # Initialize optimization LLM
            self.optimization_lm = self._create_llm(self.config.optimization_model)
            
            # Configure DSPy with primary LLM
            dspy.configure(lm=self.primary_lm)
            
            # Setup caching if enabled
            if self.config.enable_caching:
                os.makedirs(self.config.cache_dir, exist_ok=True)
            
            self._initialized = True
            logger.info("✅ DSPy initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ DSPy initialization failed: {e}")
            return False
    
    def _create_llm(self, model_spec: str) -> dspy.LM:
        """Create DSPy LM instance from model specification"""
        try:
            if model_spec.startswith("openai/"):
                model_name = model_spec.replace("openai/", "")
                return dspy.LM(
                    model=f"openai/{model_name}",
                    api_key=settings.OPENAI_API_KEY,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature
                )
            
            elif model_spec.startswith("groq/"):
                model_name = model_spec.replace("groq/", "")
                return dspy.LM(
                    model=f"groq/{model_name}",
                    api_key=settings.GROQ_API_KEY,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature
                )
            
            elif model_spec.startswith("anthropic/"):
                model_name = model_spec.replace("anthropic/", "")
                return dspy.LM(
                    model=f"anthropic/{model_name}",
                    api_key=settings.ANTHROPIC_API_KEY,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature
                )
            
            else:
                raise ValueError(f"Unsupported model specification: {model_spec}")
                
        except Exception as e:
            logger.error(f"Failed to create LLM for {model_spec}: {e}")
            raise
    
    def get_primary_lm(self) -> dspy.LM:
        """Get primary LLM instance"""
        if not self._initialized:
            raise RuntimeError("DSPy not initialized")
        return self.primary_lm
    
    def get_fallback_lm(self) -> dspy.LM:
        """Get fallback LLM instance"""
        if not self._initialized:
            raise RuntimeError("DSPy not initialized")
        return self.fallback_lm
    
    def get_optimization_lm(self) -> dspy.LM:
        """Get optimization LLM instance"""
        if not self._initialized:
            raise RuntimeError("DSPy not initialized")
        return self.optimization_lm
    
    def switch_to_fallback(self):
        """Switch DSPy to use fallback LLM"""
        if not self._initialized:
            raise RuntimeError("DSPy not initialized")
        dspy.configure(lm=self.fallback_lm)
        logger.info("🔄 Switched to fallback LLM")
    
    def switch_to_primary(self):
        """Switch DSPy back to primary LLM"""
        if not self._initialized:
            raise RuntimeError("DSPy not initialized")
        dspy.configure(lm=self.primary_lm)
        logger.info("🔄 Switched to primary LLM")

    async def register_module(self, name: str, module: Any) -> None:
        """Register a custom DSPy module (e.g., voice‑optimized module).
        The method is async to match existing call sites.
        """
        if not self._initialized:
            raise RuntimeError("DSPy not initialized – cannot register modules")
        self._module_registry[name] = module
        logger.info(f"✅ DSPy module registered: {name}")

    def get_registered_module(self, name: str) -> Any:
        """Retrieve a previously registered module by name."""
        return self._module_registry.get(name)



# Global DSPy manager instance
_dspy_manager: Optional[DSPyManager] = None


@lru_cache(maxsize=1)
def get_dspy_config() -> DSPyConfig:
    """Get DSPy configuration from environment"""
    return DSPyConfig(
        primary_model=os.getenv("DSPY_PRIMARY_MODEL", "openai/gpt-4o-mini"),
        fallback_model=os.getenv("DSPY_FALLBACK_MODEL", "groq/llama-3.3-70b-versatile"),
        optimization_model=os.getenv("DSPY_OPTIMIZATION_MODEL", "openai/gpt-4o-mini"),
        max_tokens=int(os.getenv("DSPY_MAX_TOKENS", "2000")),
        temperature=float(os.getenv("DSPY_TEMPERATURE", "0.7")),
        enable_caching=os.getenv("DSPY_ENABLE_CACHING", "true").lower() == "true",
        cache_dir=os.getenv("DSPY_CACHE_DIR", ".dspy_cache"),
        optimization_budget=float(os.getenv("DSPY_OPTIMIZATION_BUDGET", "10.0")),
        max_optimization_examples=int(os.getenv("DSPY_MAX_OPTIMIZATION_EXAMPLES", "100"))
    )


def get_dspy_manager() -> DSPyManager:
    """Get global DSPy manager instance"""
    global _dspy_manager
    if _dspy_manager is None:
        config = get_dspy_config()
        _dspy_manager = DSPyManager(config)
        _dspy_manager.initialize()
    return _dspy_manager


def initialize_dspy() -> bool:
    """Initialize DSPy system"""
    manager = get_dspy_manager()
    
    if not manager._initialized:
        error_msg = "DSPy manager failed to initialize properly"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
        
    return True
