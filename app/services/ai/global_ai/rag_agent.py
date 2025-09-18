"""
RAG Agent - Modern Knowledge Retrieval Agent with Self-Healing
Retrieves and synthesizes information from business knowledge base with automatic recovery
"""
import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from .self_healing import with_self_healing, self_healing_manager

@dataclass
class RAGResult:
    """Result from RAG search"""
    relevant_docs: List[Dict[str, Any]]
    synthesized_answer: str
    confidence: float
    sources: List[str]

class RAGAgent:
    """
    AI-powered RAG agent with self-healing capabilities
    Searches business knowledge base and generates natural responses with automatic recovery
    """

    def __init__(self, supabase_client, groq_client):
        self.supabase = supabase_client
        self.groq = groq_client
        self.logger = logging.getLogger(__name__)
        
        # Register with self-healing system
        self_healing_manager.register_agent("rag_agent", self)
        
        # Define fallback strategies
        self._fallback_strategies = self._create_fallback_strategies()
    
    def _create_fallback_strategies(self):
        """Create fallback strategies for self-healing"""
        async def basic_fallback():
            return RAGResult(
                relevant_docs=[],
                synthesized_answer="I'm having trouble retrieving information right now. Could you try asking differently?",
                confidence=0.1,
                sources=[]
            )
        
        return basic_fallback
    
    @with_self_healing("rag_agent")
    async def answer_question(self, query: str, context: Dict[str, Any],
                           conversation_history: List[Dict[str, Any]]) -> RAGResult:
        """
        Answer user question using RAG approach with self-healing protection
        
        Args:
            query: User's question
            context: Business context
            conversation_history: Previous conversation turns
            
        Returns:
            RAGResult with answer and sources
        """
        try:
            # Search for relevant information
            relevant_docs = await self._search_knowledge_base(query, context)

            if not relevant_docs:
                return RAGResult(
                    relevant_docs=[],
                    synthesized_answer="I don't have specific information about that. Let me search our knowledge base...",
                    confidence=0.1,
                    sources=[]
                )

            # Synthesize natural answer from retrieved docs
            answer = await self._synthesize_answer(query, relevant_docs, context, conversation_history)

            # Extract source information
            sources = []
            for doc in relevant_docs:
                source = doc.get("business_name", doc.get("source", "Unknown"))
                if source not in sources:
                    sources.append(source)

            return RAGResult(
                relevant_docs=relevant_docs,
                synthesized_answer=answer,
                confidence=min(0.9, len(relevant_docs) * 0.2),  # Confidence based on docs found
                sources=sources
            )

        except Exception as e:
            self.logger.error(f"RAG answer generation failed: {e}")
            return RAGResult(
                relevant_docs=[],
                synthesized_answer="I'm having trouble retrieving information right now. Could you try asking differently?",
                confidence=0.0,
                sources=[]
            )

    async def _search_knowledge_base(self, query: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search the knowledge base for relevant information"""
        try:
            # First, try searching menu items and business information
            menu_results = await self._search_menu_items(query, context)
            business_results = await self._search_business_info(query, context)

            # Combine and deduplicate results
            all_results = menu_results + business_results

            # Remove duplicates based on content
            seen_content = set()
            unique_results = []
            for result in all_results:
                content_key = f"{result.get('business_name', '')}_{result.get('content', '')}"
                if content_key not in seen_content:
                    seen_content.add(content_key)
                    unique_results.append(result)

            return unique_results[:5]  # Return top 5 results

        except Exception as e:
            self.logger.error(f"Knowledge base search failed: {e}")
            return []

    async def _search_menu_items(self, query: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search menu items using fuzzy matching"""
        results = []

        try:
            # Get all menu items from context
            for business in context.get("businesses", []):
                business_id = business["id"]
                business_name = business["name"]

                # Search menu items for this business
                menu_resp = self.supabase.table("menu_items").select("*").eq("business_id", business_id).eq("is_available", True).execute()
                menu_items = menu_resp.data or []

                for item in menu_items:
                    # Simple fuzzy matching for query terms
                    item_text = f"{item['name']} {item.get('description', '')} {item.get('category', '')}".lower()
                    query_terms = query.lower().split()

                    # Check if any query term matches the item
                    if any(term in item_text for term in query_terms):
                        results.append({
                            "type": "menu_item",
                            "business_name": business_name,
                            "business_id": business_id,
                            "content": f"{item['name']} - {item.get('description', 'No description')}",
                            "price": float(item.get('base_price', 0)),
                            "category": item.get('category', 'General'),
                            "relevance_score": len([term for term in query_terms if term in item_text])
                        })

        except Exception as e:
            self.logger.error(f"Menu search failed: {e}")

        return results

    async def _search_business_info(self, query: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search business information"""
        results = []

        try:
            query_lower = query.lower()

            for business in context.get("businesses", []):
                business_text = f"{business['name']} {business['category']} {business['description']} {business['location']}".lower()

                # Check if query matches business info
                if any(term in business_text for term in query_lower.split()):
                    results.append({
                        "type": "business_info",
                        "business_name": business["name"],
                        "business_id": business["id"],
                        "content": business["description"],
                        "location": business["location"],
                        "category": business["category"],
                        "phone": business.get("phone", ""),
                        "relevance_score": 1
                    })

        except Exception as e:
            self.logger.error(f"Business info search failed: {e}")

        return results

    async def _synthesize_answer(self, query: str, docs: List[Dict[str, Any]],
                               context: Dict[str, Any], conversation_history: List[Dict[str, Any]]) -> str:
        """Synthesize natural answer from retrieved documents"""
        try:
            # Build context from retrieved documents
            doc_context = "\n".join([
                f"Business: {doc['business_name']}\nContent: {doc['content']}\n{'Price: €' + str(doc['price']) if doc.get('price') else ''}\n---"
                for doc in docs
            ])

            # Format conversation history
            history_text = "\n".join([
                f"{'User' if msg.get('role') == 'user' else 'Assistant'}: {msg.get('content', '')}"
                for msg in conversation_history[-3:]
            ])

            synthesis_prompt = f"""You are a knowledgeable restaurant concierge. Answer the user's question naturally using the retrieved information.

USER QUESTION: {query}

RETRIEVED INFORMATION:
{doc_context}

RECENT CONVERSATION:
{history_text}

INSTRUCTIONS:
- Answer naturally and conversationally
- Use the retrieved information to provide accurate details
- Don't mention technical terms like "retrieved" or "database"
- If information is incomplete, be honest about limitations
- Suggest alternatives if relevant
- Keep the answer concise but helpful
- If the question is about menu items, include prices when available

Natural response:"""

            response = self.groq.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "user", "content": synthesis_prompt}
                ],
                temperature=0.6,
                max_tokens=300
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            self.logger.error(f"Answer synthesis failed: {e}")
            # Fallback to simple answer
            return self._create_simple_answer(query, docs)

    def _create_simple_answer(self, query: str, docs: List[Dict[str, Any]]) -> str:
        """Create simple answer when synthesis fails"""
        if not docs:
            return "I don't have specific information about that topic."

        # Group by business
        business_info = {}
        for doc in docs:
            business_name = doc.get("business_name", "Unknown")
            if business_name not in business_info:
                business_info[business_name] = []

            if doc["type"] == "menu_item":
                business_info[business_name].append(f"{doc['content']} (€{doc['price']:.2f})")
            else:
                business_info[business_name].append(doc['content'])

        # Build simple response
        responses = []
        for business, info in business_info.items():
            responses.append(f"At {business}: {', '.join(info[:3])}")

        if responses:
            return "Here's what I found: " + " | ".join(responses)
        else:
            return "I found some information but couldn't process it properly. Could you ask differently?"
