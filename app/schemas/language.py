"""Language and localization schemas."""
from typing import Dict, Optional, List
from pydantic import BaseModel
from enum import Enum


class SupportedLanguage(str, Enum):
    """Supported languages."""
    ENGLISH = "en"
    LATVIAN = "lv"
    RUSSIAN = "ru"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    ITALIAN = "it"
    PORTUGUESE = "pt"
    JAPANESE = "ja"
    KOREAN = "ko"
    CHINESE = "zh"
    ARABIC = "ar"
    HINDI = "hi"


class LanguageDetectionResult(BaseModel):
    """Language detection result."""
    detected_language: SupportedLanguage
    confidence: float
    original_text: str


class TranslationRequest(BaseModel):
    """Translation request."""
    text: str
    source_language: Optional[SupportedLanguage] = None
    target_language: SupportedLanguage


class LocalizedContent(BaseModel):
    """Localized content for multiple languages."""
    content: Dict[str, str]  # {language_code: translated_text}

    class Config:
        json_schema_extra = {
            "example": {
                "content": {
                    "en": "Welcome to our café!",
                    "lv": "Laipni lūdzam mūsu kafejnīcā!",
                    "ru": "Добро пожаловать в наше кафе!"
                }
            }
        }


class MenuTranslation(BaseModel):
    """Menu item translation."""
    item_id: int
    translations: Dict[str, Dict[str, str]]  # {lang: {name, description}}

    class Config:
        json_schema_extra = {
            "example": {
                "item_id": 1,
                "translations": {
                    "en": {"name": "Cappuccino", "description": "Rich espresso with foam"},
                    "lv": {"name": "Kapučīno", "description": "Bagāta espresso ar putām"},
                    "ru": {"name": "Капучино", "description": "Насыщенный эспрессо с пенкой"}
                }
            }
        }


class LanguageResponse(BaseModel):
    """Language response."""
    code: str
    name: str
    native_name: str
    is_supported: bool
    is_default: bool = False


class TranslationResponse(BaseModel):
    """Translation response."""
    original_text: str
    translated_text: str
    source_language: str
    target_language: str
    confidence: float