"""Message model for chat history."""
from sqlalchemy import Column, String, Integer, ForeignKey, Text, DateTime, JSON
from sqlalchemy.orm import relationship
from app.models.base import BaseModel



class Message(BaseModel):
    """
    Chat messages between customers and bot.
    
    Stores full conversation history for context and analytics.
    """
    __tablename__ = "messages"
    
    # Session tracking
    session_id = Column(String(50), index=True, nullable=False)
    
    # Multi-tenant
    business_id = Column(
        Integer,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Message details
    sender_type = Column(String(20), nullable=False)  # customer, bot, staff
    content = Column(Text, nullable=False)
    message_type = Column(String(20), default="text")  # text, voice, image
    
    # AI tracking
    intent_detected = Column(String(50))  # menu_inquiry, order_placement, etc.
    ai_model_used = Column(String(50))  # qrog, claude, gpt4
    response_time_ms = Column(Integer)
    
    # Additional metadata
    extra_data = Column(JSON, default=dict)
    
    # Relationships
    business = relationship("Business")
    
    def __repr__(self):
        return f"<Message {self.session_id} - {self.sender_type}>"