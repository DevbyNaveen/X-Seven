"""
Advanced Memory Management System for Global AI
Handles context memory, semantic understanding, and memory consolidation
"""

from __future__ import annotations
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import numpy as np
from sentence_transformers import SentenceTransformer

class AdvancedMemoryManager:
    """
    Advanced Memory Management System
    Handles context persistence, semantic understanding, and memory consolidation
    """

    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.logger = logging.getLogger(__name__)

        # Initialize embedding model for semantic memory
        try:
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception as e:
            self.logger.warning(f"Could not load embedding model: {e}")
            self.embedding_model = None

        # Memory configuration
        self.short_term_memory_limit = 50
        self.long_term_memory_limit = 200
        self.memory_decay_factor = 0.95
        self.consolidation_threshold = 5

    async def store_conversation_memory(
        self,
        session_id: str,
        user_id: Optional[str],
        memory_type: str,
        context_key: str,
        context_value: Dict[str, Any],
        importance_score: float = 0.5
    ) -> bool:
        """Store conversation memory with automatic cleanup"""
        try:
            # Calculate expiration based on memory type
            expires_at = self._calculate_expiration(memory_type)

            # Store memory
            result = self.supabase.table('conversation_memory').insert({
                'session_id': session_id,
                'user_id': user_id,
                'memory_type': memory_type,
                'context_key': context_key,
                'context_value': json.dumps(context_value),
                'importance_score': importance_score,
                'expires_at': expires_at.isoformat()
            }).execute()

            # Check if we need to consolidate memories
            if memory_type == 'short_term':
                await self._check_consolidation_threshold(session_id)

            # Cleanup old memories
            await self._cleanup_expired_memories()

            return len(result.data) > 0

        except Exception as e:
            self.logger.error(f"Failed to store conversation memory: {e}")
            return False

    async def retrieve_conversation_memory(
        self,
        session_id: str,
        context_key: Optional[str] = None,
        memory_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Retrieve conversation memory with relevance scoring"""
        try:
            query = self.supabase.table('conversation_memory').select('*')

            if context_key:
                query = query.eq('context_key', context_key)

            if memory_type:
                query = query.eq('memory_type', memory_type)

            # Get memories and update access patterns
            result = query.eq('session_id', session_id)\
                         .order('importance_score', desc=True)\
                         .order('last_accessed_at', desc=True)\
                         .limit(limit)\
                         .execute()

            memories = result.data or []

            # Update access patterns for retrieved memories
            for memory in memories:
                await self._update_memory_access(memory['id'])

            return memories

        except Exception as e:
            self.logger.error(f"Failed to retrieve conversation memory: {e}")
            return []

    async def store_business_context_section(
        self,
        business_id: int,
        section_type: str,
        section_name: str,
        section_content: Dict[str, Any],
        section_order: int = 0
    ) -> bool:
        """Store or update business context section"""
        try:
            result = self.supabase.table('business_context_sections').upsert({
                'business_id': business_id,
                'section_type': section_type,
                'section_name': section_name,
                'section_content': json.dumps(section_content),
                'section_order': section_order,
                'last_updated': datetime.now().isoformat()
            }).execute()

            return len(result.data) > 0

        except Exception as e:
            self.logger.error(f"Failed to store business context section: {e}")
            return False

    async def retrieve_business_context_sections(
        self,
        business_id: int,
        section_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve business context sections"""
        try:
            query = self.supabase.table('business_context_sections')\
                               .select('*')\
                               .eq('business_id', business_id)\
                               .eq('is_active', True)\
                               .order('section_order', desc=False)

            if section_type:
                query = query.eq('section_type', section_type)

            result = query.execute()
            return result.data or []

        except Exception as e:
            self.logger.error(f"Failed to retrieve business context sections: {e}")
            return []

    async def store_semantic_memory(
        self,
        session_id: str,
        user_id: Optional[str],
        content_type: str,
        content_text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Store semantic memory with embeddings"""
        try:
            if not self.embedding_model:
                self.logger.warning("Embedding model not available for semantic memory")
                return False

            # Generate embedding
            embedding = self.embedding_model.encode(content_text, convert_to_numpy=True)

            # Store semantic memory
            result = self.supabase.table('semantic_memory').insert({
                'session_id': session_id,
                'user_id': user_id,
                'content_type': content_type,
                'content_text': content_text,
                'embedding_vector': embedding.tolist(),
                'metadata': json.dumps(metadata or {}),
                'relevance_score': 0.5
            }).execute()

            return len(result.data) > 0

        except Exception as e:
            self.logger.error(f"Failed to store semantic memory: {e}")
            return False

    async def search_semantic_memory(
        self,
        session_id: str,
        query_text: str,
        content_type: Optional[str] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Search semantic memory using embeddings"""
        try:
            if not self.embedding_model:
                self.logger.warning("Embedding model not available for semantic search")
                return []

            # Generate query embedding
            query_embedding = self.embedding_model.encode(query_text, convert_to_numpy=True)

            # Build query for semantic search
            query = self.supabase.table('semantic_memory')\
                               .select('*')\
                               .eq('session_id', session_id)

            if content_type:
                query = query.eq('content_type', content_type)

            # Get all semantic memories for this session
            result = query.execute()
            memories = result.data or []

            if not memories:
                return []

            # Calculate similarities
            similarities = []
            for memory in memories:
                emb_val = memory.get('embedding_vector')
                # Handle embeddings stored as JSON text strings
                if isinstance(emb_val, str):
                    try:
                        emb_val = json.loads(emb_val)
                    except Exception:
                        # If parsing fails, skip this memory entry
                        continue
                # Ensure iterable of numbers
                try:
                    memory_embedding = np.array(emb_val, dtype=float)
                except Exception:
                    # Skip malformed embeddings
                    continue
                similarity = np.dot(query_embedding, memory_embedding) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(memory_embedding)
                )
                similarities.append((memory, float(similarity)))

            # Sort by similarity and return top-k
            similarities.sort(key=lambda x: x[1], reverse=True)
            return [memory for memory, _ in similarities[:top_k]]

        except Exception as e:
            self.logger.error(f"Failed to search semantic memory: {e}")
            return []

    async def update_context_relevance(
        self,
        session_id: str,
        context_type: str,
        context_key: str,
        relevance_score: float
    ) -> bool:
        """Update context relevance scores"""
        try:
            result = self.supabase.table('context_relevance').upsert({
                'session_id': session_id,
                'context_type': context_type,
                'context_key': context_key,
                'relevance_score': relevance_score,
                'last_calculated': datetime.now().isoformat()
            }).execute()

            return len(result.data) > 0

        except Exception as e:
            self.logger.error(f"Failed to update context relevance: {e}")
            return False

    async def get_user_context_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve user context profile"""
        try:
            result = self.supabase.table('user_context_profiles')\
                               .select('*')\
                               .eq('user_id', user_id)\
                               .execute()

            return result.data[0] if result.data else None

        except Exception as e:
            self.logger.error(f"Failed to get user context profile: {e}")
            return None

    async def update_user_context_profile(
        self,
        user_id: str,
        profile_data: Dict[str, Any],
        preferences: Optional[Dict[str, Any]] = None,
        behavior_patterns: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update or create user context profile"""
        try:
            existing_profile = await self.get_user_context_profile(user_id)

            if existing_profile:
                # Update existing profile
                update_data = {
                    'profile_data': json.dumps(profile_data),
                    'last_updated': datetime.now().isoformat()
                }

                if preferences:
                    update_data['preferences'] = json.dumps(preferences)

                if behavior_patterns:
                    update_data['behavior_patterns'] = json.dumps(behavior_patterns)

                result = self.supabase.table('user_context_profiles')\
                                   .update(update_data)\
                                   .eq('user_id', user_id)\
                                   .execute()
            else:
                # Create new profile
                result = self.supabase.table('user_context_profiles').insert({
                    'user_id': user_id,
                    'profile_data': json.dumps(profile_data),
                    'preferences': json.dumps(preferences or {}),
                    'behavior_patterns': json.dumps(behavior_patterns or {}),
                    'context_history': json.dumps([])
                }).execute()

            return len(result.data) > 0

        except Exception as e:
            self.logger.error(f"Failed to update user context profile: {e}")
            return False

    async def consolidate_session_memories(self, session_id: str) -> Optional[str]:
        """Consolidate short-term memories into long-term memory"""
        try:
            # Fetch IDs of short-term memories first (to avoid table-wide updates)
            short_term_res = self.supabase.table('conversation_memory')\
                                         .select('id')\
                                         .eq('session_id', session_id)\
                                         .eq('memory_type', 'short_term')\
                                         .execute()

            short_term_ids = [row['id'] for row in (short_term_res.data or []) if row.get('id')]
            memory_count = len(short_term_ids)

            if memory_count >= self.consolidation_threshold:
                # Create consolidated memory
                consolidation_data = {
                    'session_id': session_id,
                    'memory_type': 'long_term',
                    'context_key': f'consolidated_context_{datetime.now().isoformat()}',
                    'context_value': json.dumps({
                        'consolidated_at': datetime.now().isoformat(),
                        'memory_count': memory_count,
                        'session_summary': f'Consolidated from {memory_count} short-term memories'
                    }),
                    'importance_score': 0.8,
                    'expires_at': (datetime.now() + timedelta(days=90)).isoformat()
                }

                insert_res = self.supabase.table('conversation_memory').insert(consolidation_data).execute()

                if insert_res.data:
                    new_memory_id = insert_res.data[0]['id']

                    # Log consolidation with the actual old IDs
                    await self._log_memory_consolidation(
                        session_id,
                        'consolidate',
                        short_term_ids,
                        new_memory_id,
                        f'Automatic consolidation of {memory_count} short-term memories'
                    )

                    # Archive only the fetched short-term IDs using IN filter
                    if short_term_ids:
                        try:
                            self.supabase.table('conversation_memory')\
                                       .update({
                                           'memory_type': 'archived',
                                           'expires_at': (datetime.now() + timedelta(days=90)).isoformat()
                                       })\
                                       .in_('id', short_term_ids)\
                                       .execute()
                        except Exception as e:
                            # Soft-fail archiving to avoid interrupting main flow
                            self.logger.warning(f"Archiving short-term memories failed: {e}")

                    return new_memory_id

            return None

        except Exception as e:
            self.logger.error(f"Failed to consolidate session memories: {e}")
            return None

    async def get_memory_summary(self, session_id: str) -> Dict[str, Any]:
        """Get memory usage summary for a session"""
        try:
            # Get memory counts by type
            result = self.supabase.table('conversation_memory')\
                               .select('memory_type')\
                               .eq('session_id', session_id)\
                               .execute()

            memory_types = {}
            for row in result.data or []:
                memory_type = row['memory_type']
                memory_types[memory_type] = memory_types.get(memory_type, 0) + 1

            # Get semantic memory count
            semantic_result = self.supabase.table('semantic_memory')\
                                         .select('id')\
                                         .eq('session_id', session_id)\
                                         .execute()

            return {
                'conversation_memories': memory_types,
                'semantic_memories': len(semantic_result.data or []),
                'total_memories': sum(memory_types.values()) + len(semantic_result.data or [])
            }

        except Exception as e:
            self.logger.error(f"Failed to get memory summary: {e}")
            return {}

    # Private helper methods

    def _calculate_expiration(self, memory_type: str) -> datetime:
        """Calculate expiration date based on memory type"""
        if memory_type == 'short_term':
            return datetime.now() + timedelta(days=7)
        elif memory_type == 'long_term':
            return datetime.now() + timedelta(days=90)
        elif memory_type == 'archived':
            return datetime.now() + timedelta(days=365)
        else:
            return datetime.now() + timedelta(days=30)

    async def _update_memory_access(self, memory_id: str) -> bool:
        """Update memory access count and timestamp"""
        try:
            # Fetch current access count
            current_result = self.supabase.table('conversation_memory')\
                                           .select('access_count')\
                                           .eq('id', memory_id)\
                                           .execute()
            
            if not current_result.data:
                return False
            
            current_count = current_result.data[0].get('access_count', 0)
            # Ensure it's numeric
            if not isinstance(current_count, (int, float)):
                current_count = 0
            
            # Update with incremented count
            self.supabase.table('conversation_memory')\
                       .update({
                           'access_count': int(current_count) + 1,
                           'last_accessed_at': datetime.now().isoformat()
                       })\
                       .eq('id', memory_id)\
                       .execute()
            return True
        except Exception:
            return False

    async def _cleanup_expired_memories(self) -> int:
        """Clean up expired memories"""
        try:
            result = self.supabase.table('conversation_memory')\
                               .delete()\
                               .lt('expires_at', datetime.now().isoformat())\
                               .execute()
            return len(result.data or [])
        except Exception as e:
            self.logger.error(f"Failed to cleanup expired memories: {e}")
            return 0

    async def _check_consolidation_threshold(self, session_id: str) -> None:
        """Check if memory consolidation is needed"""
        try:
            await self.consolidate_session_memories(session_id)
        except Exception as e:
            self.logger.error(f"Memory consolidation check failed: {e}")

    async def _log_memory_consolidation(
        self,
        session_id: str,
        consolidation_type: str,
        old_memory_ids: List[str],
        new_memory_id: str,
        reason: str
    ) -> bool:
        """Log memory consolidation events"""
        try:
            result = self.supabase.table('memory_consolidation_log').insert({
                'session_id': session_id,
                'consolidation_type': consolidation_type,
                'old_memory_ids': old_memory_ids,
                'new_memory_id': new_memory_id,
                'consolidation_reason': reason
            }).execute()

            return len(result.data) > 0
        except Exception as e:
            self.logger.error(f"Failed to log memory consolidation: {e}")
            return False
