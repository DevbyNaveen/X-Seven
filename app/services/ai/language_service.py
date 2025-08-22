"""Language detection and templating service.

- Detects user language using langdetect
- Provides minimal templates used by WhatsApp universal flow
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Dict

try:
    from langdetect import detect  # type: ignore
except Exception:  # pragma: no cover - optional at runtime
    detect = None  # Fallback when package not available


class Language(str, Enum):
    en = "en"
    es = "es"
    fr = "fr"
    de = "de"
    it = "it"


@dataclass
class DetectionResult:
    detected_language: Language


class LanguageService:
    """Simple language utilities with safe defaults."""

    DEFAULT = Language.en
    SUPPORTED = {l.value for l in Language}

    def detect_language(self, text: str) -> DetectionResult:
        """Return detected language with a stable interface used by endpoints.
        Falls back to English when detection fails or unsupported.
        """
        lang = self.DEFAULT
        try:
            if detect is not None:
                code = detect(text or "") or self.DEFAULT
                code = code.split("-")[0].lower()
                if code in self.SUPPORTED:
                    lang = Language(code)
        except Exception:
            # Keep default language on any failure
            pass
        return DetectionResult(detected_language=lang)

    def get_template(self, language: str | Language, key: str) -> str:
        """Return a localized template string for given key.
        Keys currently used: 'welcome', 'select_cafe'.
        """
        lang = language.value if isinstance(language, Language) else (language or self.DEFAULT)
        lang = str(lang).lower()
        if lang not in self.SUPPORTED:
            lang = self.DEFAULT.value

        templates: Dict[str, Dict[str, str]] = {
            "en": {
                "welcome": "Welcome! How can I help you today?",
                "select_cafe": "Please select a business to continue",
            },
            "es": {
                "welcome": "¡Bienvenido! ¿En qué puedo ayudarte hoy?",
                "select_cafe": "Selecciona un negocio para continuar",
            },
            "fr": {
                "welcome": "Bienvenue ! Comment puis-je vous aider aujourd'hui ?",
                "select_cafe": "Veuillez sélectionner une entreprise pour continuer",
            },
            "de": {
                "welcome": "Willkommen! Wie kann ich Ihnen heute helfen?",
                "select_cafe": "Bitte wählen Sie ein Unternehmen aus, um fortzufahren",
            },
            "it": {
                "welcome": "Benvenuto! Come posso aiutarti oggi?",
                "select_cafe": "Seleziona un'attività per continuare",
            },
        }
        return templates.get(lang, templates[self.DEFAULT.value]).get(key, "")
