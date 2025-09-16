"""
Base AI Handler - Core AI functionality shared across all services
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Dict, Any, Optional, List
from datetime import datetime

try:
    from groq import Groq
except Exception:  # ImportError or missing dependencies
    Groq = None  # type: ignore
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.core.ai.types import RichContext, ChatContext


class BaseAIHandler:
    """Base handler providing common AI functionality"""
    
    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self.client = Groq(api_key=settings.GROQ_API_KEY) if (Groq and settings.GROQ_API_KEY) else None
        self.model = settings.GROQ_MODEL or "llama-3.3-70b-versatile"
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def get_ai_response(self, prompt: str, functions: Optional[List[Dict[str, Any]]] = None) -> str:
        """Get AI response with optional function calling"""
        if not self.client:
            raise RuntimeError("Groq client not initialized")
        
        messages = [{"role": "user", "content": prompt}]
        
        try:
            if functions:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    functions=functions,
                    function_call="auto",
                    max_tokens=2000,
                    temperature=0.7
                )
                
                # Handle function calls
                if response.choices[0].message.function_call:
                    function_call = response.choices[0].message.function_call
                    return await self._execute_function_call(function_call)
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=2000,
                    temperature=0.7
                )
            
            return response.choices[0].message.content or ""
            
        except Exception as e:
            self.logger.exception("AI response generation failed: %s", e)
            raise
    
    async def _execute_function_call(self, function_call) -> str:
        """Execute a function call and return the result"""
        function_name = function_call.name
        arguments = json.loads(function_call.arguments)
        
        result = await self.execute_function(function_name, arguments)
        return json.dumps(result, default=str)
    
    async def execute_function(self, function_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Override in subclasses to handle context-specific functions"""
        return {"error": f"Function {function_name} not implemented", "success": False}
    
    def build_prompt(self, context: RichContext) -> str:
        """Override in subclasses to build context-specific prompts"""
        raise NotImplementedError("Subclasses must implement build_prompt")
    
    async def save_conversation(self, context: RichContext, response: str) -> None:
        """Save conversation to database - override as needed"""
        try:
            from app.models import Message
            
            if self.db:
                message = Message(
                    session_id=context.session_id,
                    business_id=context.business_id,
                    content=context.user_message,
                    sender_type="customer",
                    chat_context=context.chat_context.value
                )
                self.db.add(message)
                
                response_message = Message(
                    session_id=context.session_id,
                    business_id=context.business_id,
                    content=response,
                    sender_type="assistant",
                    chat_context=context.chat_context.value
                )
                self.db.add(response_message)
                self.db.commit()
                
        except Exception as e:
            self.logger.error("Failed to save conversation: %s", e)
    
    def extract_json_from_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Extract JSON blocks from AI response"""
        json_pattern = r'```(?:json)?\s*({[\s\S]*?})\s*```'
        matches = re.findall(json_pattern, response, re.IGNORECASE)
        
        for match in matches:
            try:
                data = json.loads(match)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                continue
        
        return None
