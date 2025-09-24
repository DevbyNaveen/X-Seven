"""
Language and translation schemas for the application.
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class LanguageResponse(BaseModel):
    """Response schema for language information."""
    code: str = Field(..., description="ISO 639-1 language code")
    name: str = Field(..., description="Language name in English")
    native_name: str = Field(..., description="Language name in the language itself")
    direction: str = Field(default="ltr", description="Text direction: 'ltr' or 'rtl'")


class TranslationRequest(BaseModel):
    """Request schema for text translation."""
    text: str = Field(..., description="Text to translate")
    target_language: str = Field(..., description="Target language code")
    source_language: Optional[str] = Field(None, description="Source language code (auto-detect if not provided)")
    context: Optional[str] = Field(None, description="Additional context for better translation")


class TranslationResponse(BaseModel):
    """Response schema for translation results."""
    original_text: str = Field(..., description="Original text")
    translated_text: str = Field(..., description="Translated text")
    source_language: str = Field(..., description="Detected or provided source language code")
    target_language: str = Field(..., description="Target language code")
    confidence: Optional[float] = Field(None, description="Translation confidence score (0-1)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional translation metadata")
